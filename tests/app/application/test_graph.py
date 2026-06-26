from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from src.app.application.agents.config import (
    AgentConfig,
    AgentConfigRegistry,
    AgentLLMConfig,
)
from src.app.application.agents.gandalf import GandalfAgent
from src.app.application.agents.tools import (
    build_fellowship_subagents,
    create_subagent_tools,
)
from src.app.application.graph import build_graph
from src.app.application.models.agent_state import create_initial_state


class FakeRepository:
    async def get_hotel_count(self) -> int:
        return 0

    async def get_average_occupancy(self) -> float:
        return 0.0

    async def get_average_revpar(self) -> float:
        return 0.0

    async def get_average_sentiment(self) -> float:
        return 0.0

    async def get_top_hotels(self, metric: str, limit: int):
        return []

    async def get_bottom_hotels(self, metric: str, limit: int):
        return []

    async def get_hotels_by_trend(self, trend: str, limit: int):
        return []

    async def list_hotels(self):
        return []

    async def list_reviews(self):
        return []


class CountingRepository(FakeRepository):
    def __init__(self) -> None:
        self.hotel_count_calls = 0
        self.top_hotel_calls = 0
        self.bottom_hotel_calls = 0

    async def get_hotel_count(self) -> int:
        self.hotel_count_calls += 1
        return 0

    async def get_top_hotels(self, metric: str, limit: int):
        self.top_hotel_calls += 1
        return []

    async def get_bottom_hotels(self, metric: str, limit: int):
        self.bottom_hotel_calls += 1
        return []


class FakeWeatherProvider:
    async def get_current_weather(self, location: str) -> dict:
        return {
            "temperature_c": 21.0,
            "condition": "clear",
            "humidity": 0.55,
            "wind_kph": 8.0,
        }


def _agent_config(agent_name: str) -> AgentConfig:
    return AgentConfig(
        name=agent_name,
        llm=AgentLLMConfig(
            provider="openrouter",
            model=f"test-{agent_name}-model",
            temperature=0.2,
        ),
        prompt=f"test prompt for {agent_name}",
        tool_selection_prompt=(
            "test tool selector {tool_descriptions} {query}"
            if agent_name == "elrond"
            else None
        ),
        plan_prompt=("test plan selector {query}" if agent_name == "gandalf" else None),
    )


def _agent_configs() -> AgentConfigRegistry:
    return AgentConfigRegistry(
        configs={
            name: _agent_config(name)
            for name in (
                "gandalf",
                "aragorn",
                "samwise",
                "elrond",
                "bilbo",
                "faramir",
                "radagast",
            )
        }
    )


def _supervisor(llm: "FakeLLM", repository: FakeRepository) -> GandalfAgent:
    agent_configs = _agent_configs()
    fellowship = build_fellowship_subagents(
        repository=repository,
        llm=llm,
        weather_provider=FakeWeatherProvider(),
        store=None,
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
    return GandalfAgent(
        llm=llm,
        store=None,
        tools=list(tools),
        config=agent_configs.require("gandalf"),
    )


class FakeLLM:
    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float,
        model: str,
        provider: str,
    ) -> str:
        return "ok"


class RevenueToolSelectionLLM:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float,
        model: str,
        provider: str,
    ) -> str:
        self.calls.append(
            {"system_prompt": system_prompt, "user_message": user_message}
        )
        if "Choose the user's intent" in user_message:
            return (
                '{"intent": "hotel_analytics", "response_format": "insight_report", '
                '"agent_plan": ["aragorn", "samwise", "elrond", "bilbo", "faramir"]}'
            )
        if "guardian of a read-only hotel insights system" in system_prompt:
            return (
                '{"is_compliant": true, "violations": [], "warnings": [], '
                '"reasoning": "in scope"}'
            )
        if "Select Elrond private tools" in user_message:
            return (
                '{"tool_names": ["get_top_hotels_by_revpar"], '
                '"needs_clarification": false, "clarifying_question": "", '
                '"answer_options": []}'
            )
        if "Analyze the approved hotel question" in user_message:
            return (
                '{"insights": ["Alpine Retreat leads RevPAR."], '
                '"metrics_used": ["get_top_hotels_by_revpar"], '
                '"confidence": "medium"}'
            )
        if '"response_format"' in user_message:
            return (
                '{"final_answer": "Alpine Retreat leads RevPAR.", '
                '"summary_style": "insight_report", "assumptions": []}'
            )
        if '"final_answer"' in user_message:
            return (
                '{"approved": true, "warnings": [], "required_changes": [], '
                '"reasoning": "Answer is grounded."}'
            )
        raise AssertionError(f"Unexpected LLM call: {user_message}")


class FakeSupervisor:
    def __init__(self, update: dict[str, Any] | None = None) -> None:
        self.update = update
        self.states: list[dict[str, Any]] = []

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        self.states.append(state)
        if self.update is not None:
            return self.update
        return {
            "active_agent": "fake-supervisor",
            "final_answer": f"handled: {state['query']}",
        }


class ResumableSupervisor:
    def __init__(self) -> None:
        self.states: list[dict[str, Any]] = []

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        self.states.append(state)
        if state.get("user_feedback"):
            return {
                "active_agent": "gandalf",
                "final_answer": f"resumed with {state['query']}",
                "requires_approval": False,
                "approval_context": None,
            }
        return {
            "active_agent": "gandalf",
            "final_answer": "Please confirm scope, timeframe, and metric.",
            "requires_approval": True,
            "approval_context": {
                "agent": "elrond",
                "question": "Please confirm scope, timeframe, and metric.",
                "reason": "additional_user_input_required",
            },
        }


class ReinterruptingSupervisor:
    def __init__(self) -> None:
        self.states: list[dict[str, Any]] = []

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        self.states.append(state)
        query = str(state.get("query", ""))
        if "current portfolio by revpar" in query.casefold():
            return {
                "active_agent": "gandalf",
                "final_answer": f"answered with {query}",
                "requires_approval": False,
                "approval_context": None,
            }
        if state.get("user_feedback"):
            return {
                "active_agent": "gandalf",
                "final_answer": "Which timeframe should I use?",
                "requires_approval": True,
                "approval_context": {
                    "agent": "elrond",
                    "question": "Which timeframe should I use?",
                    "reason": "additional_user_input_required",
                },
            }
        return {
            "active_agent": "gandalf",
            "final_answer": "Please confirm scope, timeframe, and metric.",
            "requires_approval": True,
            "approval_context": {
                "agent": "elrond",
                "question": "Please confirm scope, timeframe, and metric.",
                "options": ["Current portfolio by RevPAR"],
                "reason": "additional_user_input_required",
            },
        }


@pytest.mark.asyncio
async def test_graph_compiles_with_injected_ports():
    llm = FakeLLM()
    repository = FakeRepository()
    graph = await build_graph(
        checkpointer=None,
        store=None,
        supervisor=_supervisor(llm, repository),
    )

    assert graph is not None
    assert hasattr(graph, "invoke") or hasattr(graph, "ainvoke")


@pytest.mark.asyncio
async def test_graph_compiles_with_protocol_supervisor():
    graph = await build_graph(
        checkpointer=None,
        store=None,
        supervisor=FakeSupervisor(),
    )

    result = await graph.ainvoke(
        {
            "query": "hello",
            "user_id": "user-1",
            "thread_id": "thread-1",
            "messages": [],
            "route_decision": "",
            "active_agent": "",
            "agent_transcript": [],
            "tool_results": {},
            "insights": [],
            "user_context": {},
            "weather_context": {},
            "compliance_status": {},
            "review_status": {},
            "final_answer": "",
            "reasoning_trace": "",
            "requires_approval": False,
            "approval_context": None,
            "user_feedback": None,
        }
    )

    assert result["active_agent"] == "fake-supervisor"
    assert result["final_answer"] == "handled: hello"


@pytest.mark.asyncio
async def test_graph_interrupts_when_supervisor_requires_more_user_input():
    graph = await build_graph(
        checkpointer=None,
        store=None,
        supervisor=FakeSupervisor(
            {
                "active_agent": "gandalf",
                "final_answer": "Which metric should I analyze?",
                "requires_approval": True,
                "approval_context": {
                    "agent": "elrond",
                    "question": "Which metric should I analyze?",
                    "reason": "additional_user_input_required",
                },
            }
        ),
    )

    chunks = []
    async for chunk in graph.astream(
        {
            "query": "Tell me about hotels",
            "user_id": "user-1",
            "thread_id": "thread-1",
            "messages": [],
            "route_decision": "",
            "active_agent": "",
            "agent_transcript": [],
            "tool_results": {},
            "insights": [],
            "user_context": {},
            "weather_context": {},
            "compliance_status": {},
            "review_status": {},
            "final_answer": "",
            "reasoning_trace": "",
            "requires_approval": False,
            "approval_context": None,
            "user_feedback": None,
        }
    ):
        chunks.append(chunk)

    assert (
        chunks[-1]["__interrupt__"][0].value["question"]
        == "Which metric should I analyze?"
    )


@pytest.mark.asyncio
async def test_graph_resumes_interrupted_node_with_user_feedback():
    supervisor = ResumableSupervisor()
    graph = await build_graph(
        checkpointer=InMemorySaver(), store=None, supervisor=supervisor
    )
    initial_state = {
        "query": "Which hotels are performing best by revenue?",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "messages": [],
        "route_decision": "",
        "active_agent": "",
        "agent_transcript": [],
        "tool_results": {},
        "insights": [],
        "user_context": {},
        "weather_context": {},
        "compliance_status": {},
        "review_status": {},
        "final_answer": "",
        "reasoning_trace": "",
        "requires_approval": False,
        "approval_context": None,
        "user_feedback": None,
    }

    config = {"configurable": {"thread_id": "thread-1"}}
    chunks = []
    async for chunk in graph.astream(initial_state, config):
        chunks.append(chunk)
        break

    assert chunks[-1]["__interrupt__"][0].value["question"] == (
        "Please confirm scope, timeframe, and metric."
    )
    result = await graph.ainvoke(Command(resume="current portfolio by RevPAR"), config)

    assert (
        "resumed with Which hotels are performing best by revenue?"
        in result["final_answer"]
    )
    assert "User clarification: current portfolio by RevPAR" in result["final_answer"]
    assert supervisor.states[-1]["query"].startswith(
        "Which hotels are performing best by revenue?"
    )
    assert (
        "User clarification: current portfolio by RevPAR"
        in supervisor.states[-1]["query"]
    )
    assert supervisor.states[-1]["user_feedback"] == "current portfolio by RevPAR"
    assert supervisor.states[-1]["requires_approval"] is False


@pytest.mark.asyncio
async def test_graph_interrupts_again_when_resumed_feedback_is_incomplete():
    supervisor = ReinterruptingSupervisor()
    graph = await build_graph(
        checkpointer=InMemorySaver(), store=None, supervisor=supervisor
    )
    config = {"configurable": {"thread_id": "thread-1"}}
    initial_state = create_initial_state(
        query="Which hotels are performing best by revenue?",
        user_id="user-1",
        thread_id="thread-1",
    )

    first_chunks = [chunk async for chunk in graph.astream(initial_state, config)]

    assert first_chunks[-1]["__interrupt__"][0].value["question"] == (
        "Please confirm scope, timeframe, and metric."
    )

    second_chunks = [
        chunk async for chunk in graph.astream(Command(resume="RevPAR only"), config)
    ]

    assert second_chunks[-1]["__interrupt__"][0].value["question"] == (
        "Which timeframe should I use?"
    )


@pytest.mark.asyncio
async def test_graph_normalizes_partial_feedback_to_available_interrupt_option():
    supervisor = ReinterruptingSupervisor()
    graph = await build_graph(
        checkpointer=InMemorySaver(), store=None, supervisor=supervisor
    )
    config = {"configurable": {"thread_id": "thread-1"}}
    initial_state = create_initial_state(
        query="Which hotels are performing best by revenue?",
        user_id="user-1",
        thread_id="thread-1",
    )

    first_chunks = [chunk async for chunk in graph.astream(initial_state, config)]

    assert first_chunks[-1]["__interrupt__"][0].value["options"] == [
        "Current portfolio by RevPAR"
    ]

    result = await graph.ainvoke(Command(resume="portfolio by RevPAR"), config)

    assert (
        "answered with Which hotels are performing best by revenue?"
        in result["final_answer"]
    )
    assert supervisor.states[-1]["user_feedback"] == "Current portfolio by RevPAR"
    assert (
        "User clarification: Current portfolio by RevPAR"
        in supervisor.states[-1]["query"]
    )


@pytest.mark.asyncio
async def test_real_gandalf_revenue_quick_question_selects_revpar_without_interrupt():
    repository = CountingRepository()
    llm = RevenueToolSelectionLLM()
    agent_configs = AgentConfigRegistry.load(
        config_root=Path("config/agents"),
        environment="local",
        provider="openrouter",
        model="test-model",
    )
    fellowship = build_fellowship_subagents(
        repository=repository,
        llm=llm,
        weather_provider=FakeWeatherProvider(),
        store=None,
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
        llm=llm,
        store=None,
        tools=list(tools),
        config=agent_configs.require("gandalf"),
    )
    graph = await build_graph(
        checkpointer=InMemorySaver(),
        store=None,
        supervisor=supervisor,
        supervisor_node_name="gandalf",
    )

    chunks = []
    async for chunk in graph.astream(
        create_initial_state(
            query="Which hotels are performing best by revenue?",
            user_id="user-1",
            thread_id="thread-1",
        ),
        {"configurable": {"thread_id": "thread-1"}},
    ):
        chunks.append(chunk)

    assert "__interrupt__" not in chunks[-1]
    assert chunks[-1]["gandalf"]["requires_approval"] is False
    assert "Alpine Retreat leads RevPAR." in chunks[-1]["gandalf"]["final_answer"]
    assert repository.hotel_count_calls == 0
    assert repository.top_hotel_calls == 1
    assert repository.bottom_hotel_calls == 0


@pytest.mark.asyncio
async def test_graph_can_keep_runtime_node_name_for_gandalf():
    llm = FakeLLM()
    repository = FakeRepository()
    graph = await build_graph(
        checkpointer=None,
        store=None,
        supervisor=_supervisor(llm, repository),
        supervisor_node_name="gandalf",
    )

    expected_nodes = ["gandalf"]
    node_names = list(graph.nodes.keys())
    for node in expected_nodes:
        assert node in node_names
    removed_nodes = ["router", "insight_generator", "ditto", "mike", "clovis"]
    for removed_node in removed_nodes:
        assert removed_node not in node_names


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Requires valid LLM_PROVIDER_API_KEY and DB — set env var to enable"
)
async def test_graph_invocation():
    """Test graph invocation with simple query.

    This test requires valid LLM_PROVIDER_API_KEY and database connectivity.
    """
    import os

    from src.app.infrastructure.adapters import OpenRouterAdapter
    from src.app.infrastructure.config import DatabaseSettings
    from src.app.infrastructure.database import create_engine, create_session_maker
    from src.app.infrastructure.repositories.hotel_repository import (
        SqlAlchemyHotelRepository,
    )

    api_key = os.environ.get("LLM_PROVIDER_API_KEY", "sk-fake-key")
    database_settings = DatabaseSettings()
    engine = create_engine(database_settings)
    repository = SqlAlchemyHotelRepository(create_session_maker(engine))
    llm = OpenRouterAdapter(api_key=api_key)

    try:
        graph = await build_graph(
            checkpointer=None,
            store=None,
            supervisor=_supervisor(llm, repository),
        )
    except Exception as e:
        pytest.skip(f"Graph not available: {e}")

    config = {
        "configurable": {
            "thread_id": "test-graph-1",
            "user_id": "graph-test-user",
        }
    }
    initial_state = {
        "query": "How are things?",
        "user_id": "graph-test-user",
        "thread_id": "test-graph-1",
        "messages": [],
        "route_decision": "",
        "active_agent": "gandalf",
        "agent_transcript": [],
        "tool_results": {},
        "insights": [],
        "user_context": {},
        "weather_context": {},
        "compliance_status": {},
        "review_status": {},
        "final_answer": "",
        "reasoning_trace": "",
        "requires_approval": False,
        "approval_context": None,
        "user_feedback": None,
    }

    try:
        result = await graph.ainvoke(initial_state, config)
    except Exception as e:
        pytest.skip(
            f"Graph invocation failed (needs DB + API): {type(e).__name__}: {e}"
        )

    assert "final_answer" in result
    assert "reasoning_trace" in result
