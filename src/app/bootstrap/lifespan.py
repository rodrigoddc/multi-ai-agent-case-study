"""Application bootstrap and lifespan wiring."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI

from src.app.application.graph import build_graph
from src.app.application.services.chat_service import ChatService
from src.app.application.services.hotel_query_service import HotelQueryService
from src.app.application.services.insight_summary_service import InsightSummaryService
from src.app.application.services.hotel_management_report_service import (
    HotelManagementReportService,
)
from src.app.application.services.sse_chat_service import SSEChatService
from src.app.bootstrap.container import ApplicationContainer
from src.app.bootstrap.strategy import AppStrategy
from src.app.application.ports import LLMAdapter
from src.app.infrastructure.adapters import (
    LLMProviderRouter,
    LlamaCppAdapter,
    OpenRouterAdapter,
)
from src.app.infrastructure.config import database, llm, llama_cpp, features, settings
from src.app.infrastructure.database import (
    create_engine,
    create_session_maker,
    create_tables,
)
from src.app.infrastructure.observability import LangfuseTracingService
from src.app.infrastructure.persistence import create_persistence
from src.app.infrastructure.repositories.hotel_repository import (
    SqlAlchemyHotelRepository,
)
from src.app.infrastructure.repositories.reporting_repository import (
    SqlAlchemyReportingRepository,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.app.application.agents.config import AgentConfigRegistry


class NoOpTracingService:
    """Tracing provider that disables optional tracing."""

    def build_config(
        self,
        user_id: str,
        session_id: str,
        thread_id: str,
        trace_id: str | None = None,
    ) -> dict | None:
        return None


def _required_llm_providers(agent_configs: AgentConfigRegistry) -> set[str]:
    return {config.llm.provider for config in agent_configs.configs.values()}


def _build_llm_adapter(agent_configs: AgentConfigRegistry) -> LLMAdapter:
    required_providers = _required_llm_providers(agent_configs)
    logger.info("Building LLM adapters for providers: %s", sorted(required_providers))
    adapters: dict[str, LLMAdapter] = {}

    if "llamacpp" in required_providers:
        adapters["llamacpp"] = LlamaCppAdapter(settings=llama_cpp)
    if "openrouter" in required_providers:
        if llm.LLM_PROVIDER_API_KEY is None:
            raise RuntimeError("LLM_PROVIDER_API_KEY is required for OpenRouter")
        adapters["openrouter"] = OpenRouterAdapter(
            api_key=llm.LLM_PROVIDER_API_KEY,
            model=llm.LLM_PROVIDER_MODEL,
            timeout_seconds=llm.LLM_TIMEOUT_SECONDS,
        )

    unsupported = required_providers - adapters.keys()
    if unsupported:
        raise RuntimeError(
            f"Unsupported LLM provider(s) in agent config: {sorted(unsupported)}"
        )
    return LLMProviderRouter(adapters)


def _build_tracing_service() -> object:
    if features.langfuse_required:
        logger.info("Langfuse tracing is enabled")
        return LangfuseTracingService()
    logger.info("Langfuse tracing is disabled; using NoOpTracingService")
    return NoOpTracingService()


async def build_container(strategy: AppStrategy) -> ApplicationContainer:
    """Build all runtime resources according to the environment strategy."""
    logging.debug("build_container starting")
    engine = create_engine(database)
    logging.debug("engine created, about to create tables")
    session_maker = create_session_maker(engine)

    if features.auto_create_tables:
        await create_tables(engine)

    repository = SqlAlchemyHotelRepository(session_maker=session_maker)
    reporting_repository = SqlAlchemyReportingRepository(session_maker=session_maker)

    persistence = None
    if features.persistence_enabled:
        persistence = await create_persistence(database)

    from src.app.application.agents.config import AgentConfigRegistry
    from src.app.application.agents.gandalf import GandalfAgent
    from src.app.application.agents.tools import (
        build_fellowship_subagents,
        create_subagent_tools,
    )
    from src.app.infrastructure.adapters import OpenMeteoAdapter

    agent_configs = AgentConfigRegistry.load(
        config_root=Path("config/agents"),
        environment=settings.APP_ENV.value,
        provider=llm.LLM_PROVIDER,
        model=llm.LLM_PROVIDER_MODEL,
    )
    for name, config in sorted(agent_configs.configs.items()):
        logger.info(
            "Agent %s using LLM provider=%s model=%s temperature=%s",
            name,
            config.llm.provider,
            config.llm.model,
            config.llm.temperature,
        )
    llm_adapter: LLMAdapter = _build_llm_adapter(agent_configs)
    fellowship = build_fellowship_subagents(
        repository=repository,
        llm=llm_adapter,
        weather_provider=OpenMeteoAdapter(),
        store=persistence.store if persistence else None,
        agent_configs=agent_configs,
    )
    tools = create_subagent_tools(
        aragorn=fellowship.aragorn,
        samwise=fellowship.samwise,
        elrond=fellowship.elrond,
        bilbo=fellowship.bilbo,
        faramir=fellowship.faramir,
        radagast=fellowship.radagast,
    )
    supervisor = GandalfAgent(
        llm=llm_adapter,
        store=persistence.store if persistence else None,
        tools=list(tools),
        config=agent_configs.require("gandalf"),
    )

    graph = await build_graph(
        checkpointer=persistence.checkpointer if persistence else None,
        store=persistence.store if persistence else None,
        supervisor=supervisor,
        supervisor_node_name="gandalf",
    )

    chat_service = ChatService(graph)
    sse_chat_service = SSEChatService(graph)
    hotel_query_service = HotelQueryService(repository=repository)
    insight_summary_service = InsightSummaryService(
        repository=repository, llm=llm_adapter
    )
    management_report_service = HotelManagementReportService(
        repository=reporting_repository
    )

    return ApplicationContainer(
        settings=settings,
        graph=graph,
        repository=repository,
        llm=llm_adapter,
        chat_service=chat_service,
        sse_chat_service=sse_chat_service,
        hotel_query_service=hotel_query_service,
        insight_summary_service=insight_summary_service,
        management_report_service=management_report_service,
        tracing_service=_build_tracing_service(),
        engine=engine,
        session_maker=session_maker,
        persistence=persistence,
    )


@asynccontextmanager
async def lifespan_for_strategy(
    app: FastAPI,
    strategy: AppStrategy,
) -> AsyncGenerator[None, None]:
    """FastAPI lifespan that delegates startup/shutdown to bootstrap services."""
    container = await build_container(strategy)
    app.state.container = container
    try:
        yield
    finally:
        await container.shutdown()
