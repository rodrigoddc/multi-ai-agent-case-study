"""Typed application dependency container."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.app.infrastructure.persistence import LangGraphPersistence


@dataclass(slots=True)
class ApplicationContainer:
    """Runtime-owned dependencies shared by FastAPI dependency providers."""

    settings: Any
    graph: Any
    repository: Any
    llm: Any
    chat_service: Any
    sse_chat_service: Any
    hotel_query_service: Any
    insight_summary_service: Any
    tracing_service: Any
    management_report_service: Any | None = None
    engine: Any | None = None
    session_maker: Any | None = None
    persistence: LangGraphPersistence | None = None

    @property
    def checkpointer(self) -> Any | None:
        """Legacy accessor for the LangGraph checkpointer."""
        if self.persistence is None:
            return None
        return self.persistence.checkpointer

    @property
    def store(self) -> Any | None:
        """Legacy accessor for the LangGraph store."""
        if self.persistence is None:
            return None
        return self.persistence.store

    async def shutdown(self) -> None:
        """Release owned infrastructure resources in reverse creation order."""
        if self.persistence is not None:
            await self.persistence.close()
        if self.engine is not None:
            await self.engine.dispose()
