from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.app.application.agents.config import (
    AgentConfig,
    AgentConfigRegistry,
    AgentLLMConfig,
)
from src.app.application.agents.radagast import RadagastAgent
from src.app.application.agents.elrond import _as_structured_tools
from src.app.application.agents.tools import (
    build_fellowship_subagents,
    create_subagent_tools,
)


class FakeRepository:
    def __init__(self) -> None:
        self.hotel_count_calls = 0
        self.top_hotel_calls = 0
        self.bottom_hotel_calls = 0
        self.last_top_metric = ""
        self.last_bottom_metric = ""

    async def get_hotel_count(self) -> int:
        self.hotel_count_calls += 1
        return 3

    async def get_average_occupancy(self) -> float:
        return 0.81

    async def get_average_revpar(self) -> float:
        return 144.0

    async def get_average_sentiment(self) -> float:
        return 0.77

    async def get_top_hotels(self, metric: str, limit: int):
        self.top_hotel_calls += 1
        self.last_top_metric = metric
        return []

    async def get_bottom_hotels(self, metric: str, limit: int):
        self.bottom_hotel_calls += 1
        self.last_bottom_metric = metric
        return []

    async def get_hotels_by_trend(self, trend: str, limit: int):
        return []

    async def list_hotels(self):
        return []

    async def list_reviews(self):
        return []


class TopHotelsRepository(FakeRepository):
    async def get_top_hotels(self, metric: str, limit: int):
        await super().get_top_hotels(metric, limit)
        return [
            SimpleNamespace(
                id=1,
                name="Alpine Retreat",
                brand="Summit",
                city="Aspen",
                country="US",
                occupancy_rate=0.82,
                average_daily_rate=242.38,
                revpar=198.75,
                sentiment_score=0.91,
            ),
            SimpleNamespace(
                id=2,
                name="Skyline Plaza",
                brand="Urban",
                city="New York",
                country="US",
                occupancy_rate=0.79,
                average_daily_rate=218.1,
                revpar=172.3,
                sentiment_score=0.84,
            ),
        ]


class FakeLLM:
    def __init__(self) -> None:
        self.generate = AsyncMock(return_value='{"insights": ["ok"]}')


class FakeWeatherProvider:
    async def get_current_weather(self, location: str) -> dict:
        return {
            "temperature_c": 21.0,
            "condition": "clear",
            "humidity": 0.55,
            "wind_kph": 8.0,
        }


class CountingWeatherProvider(FakeWeatherProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def get_current_weather(self, location: str) -> dict:
        self.calls += 1
        return await super().get_current_weather(location)


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


def _tools():
    llm = FakeLLM()
    agent_configs = _agent_configs()
    fellowship = build_fellowship_subagents(
        repository=FakeRepository(),
        llm=llm,
        store=None,
        agent_configs=agent_configs,
        radagast=RadagastAgent(
            llm=llm,
            weather_provider=FakeWeatherProvider(),
            config=agent_configs.require("radagast"),
        ),
    )
    return create_subagent_tools(
        aragorn=fellowship.aragorn,
        samwise=fellowship.samwise,
        elrond=fellowship.elrond,
        bilbo=fellowship.bilbo,
        faramir=fellowship.faramir,
        radagast=fellowship.radagast,
    )


def test_lotr_subagent_tools_are_named_for_characters():
    tools = _tools()

    names = {tool.name for tool in tools}

    assert names == {"list_agents", "call_agent"}


def test_subagent_tools_include_langfuse_tool_name_metadata_tags():
    tools = _tools()

    for tool in tools:
        assert tool.tags == [f"tool:{tool.name}"]
        assert tool.metadata == {
            "tool_name": tool.name,
            "langfuse_tags": [f"tool:{tool.name}"],
        }


def test_elrond_private_tools_include_langfuse_tool_name_metadata_tags():
    llm = FakeLLM()
    agent_configs = _agent_configs()
    elrond = build_fellowship_subagents(
        repository=FakeRepository(),
        llm=llm,
        store=None,
        agent_configs=agent_configs,
        radagast=RadagastAgent(
            llm=llm,
            weather_provider=FakeWeatherProvider(),
            config=agent_configs.require("radagast"),
        ),
    ).elrond

    for tool in _as_structured_tools(elrond.private_tools):
        assert tool.tags == [f"tool:{tool.name}"]
        assert tool.metadata == {
            "tool_name": tool.name,
            "langfuse_tags": [f"tool:{tool.name}"],
        }


def test_lotr_subagent_tool_descriptions_do_not_use_old_agent_names():
    tools = _tools()
    forbidden = [
        "Clovis",
        "Mike",
        "Ditto",
        "InsightGenerator",
        "Supervisor",
        "Router",
        "Compliance",
    ]

    for tool in tools:
        assert all(name not in tool.description for name in forbidden)


@pytest.mark.asyncio
async def test_list_agents_exposes_subagent_specs_and_private_tools():
    tools = _tools()
    list_agents = next(tool for tool in tools if tool.name == "list_agents")

    result = await list_agents.ainvoke({"query": "weather"})

    assert "radagast" in result
    assert "get_current_weather" in result
    assert "input_schema" in result
    assert "output_schema" in result


@pytest.mark.asyncio
async def test_elrond_selects_only_required_private_repository_tools():
    repository = FakeRepository()
    llm = FakeLLM()
    llm.generate.side_effect = [
        '{"tool_names": ["get_underperforming_hotels_by_sentiment"], "needs_clarification": false, "clarifying_question": ""}',
        '{"insights": ["ok"], "metrics_used": ["get_underperforming_hotels_by_sentiment"], "confidence": "medium"}',
    ]
    agent_configs = _agent_configs()
    fellowship = build_fellowship_subagents(
        repository=repository,
        llm=llm,
        store=None,
        agent_configs=agent_configs,
        radagast=RadagastAgent(
            llm=llm,
            weather_provider=FakeWeatherProvider(),
            config=agent_configs.require("radagast"),
        ),
    )
    tools = create_subagent_tools(
        aragorn=fellowship.aragorn,
        samwise=fellowship.samwise,
        elrond=fellowship.elrond,
        bilbo=fellowship.bilbo,
        faramir=fellowship.faramir,
        radagast=fellowship.radagast,
    )
    call_agent = next(tool for tool in tools if tool.name == "call_agent")

    await call_agent.ainvoke(
        {
            "agent_name": "elrond",
            "payload_json": '{"query": "Current portfolio hotels need attention by sentiment"}',
        }
    )

    assert repository.hotel_count_calls == 0
    assert repository.top_hotel_calls == 0
    assert repository.bottom_hotel_calls == 1


@pytest.mark.asyncio
async def test_elrond_selects_revenue_tool_for_quick_question_without_interrupt():
    repository = FakeRepository()
    llm = FakeLLM()
    llm.generate.side_effect = [
        '{"tool_names": ["get_top_hotels_by_revpar"], "needs_clarification": false, "clarifying_question": "", "answer_options": []}',
        '{"insights": ["Alpine Retreat leads RevPAR."], "metrics_used": ["get_top_hotels_by_revpar"], "confidence": "medium"}',
    ]
    agent_configs = _agent_configs()
    fellowship = build_fellowship_subagents(
        repository=repository,
        llm=llm,
        store=None,
        agent_configs=agent_configs,
        radagast=RadagastAgent(
            llm=llm,
            weather_provider=FakeWeatherProvider(),
            config=agent_configs.require("radagast"),
        ),
    )
    tools = create_subagent_tools(
        aragorn=fellowship.aragorn,
        samwise=fellowship.samwise,
        elrond=fellowship.elrond,
        bilbo=fellowship.bilbo,
        faramir=fellowship.faramir,
        radagast=fellowship.radagast,
    )
    call_agent = next(tool for tool in tools if tool.name == "call_agent")

    result = await call_agent.ainvoke(
        {
            "agent_name": "elrond",
            "payload_json": '{"query": "Which hotels are performing best by revenue?"}',
        }
    )

    assert result.update["requires_approval"] is False
    assert result.update["approval_context"] is None
    assert repository.hotel_count_calls == 0
    assert repository.top_hotel_calls == 1
    assert repository.last_top_metric == "revpar"
    assert repository.bottom_hotel_calls == 0


@pytest.mark.asyncio
async def test_elrond_preserves_tool_evidence_when_analysis_returns_empty_insights():
    repository = TopHotelsRepository()
    llm = FakeLLM()
    llm.generate.side_effect = [
        '{"tool_names": ["get_top_hotels_by_revpar"], "needs_clarification": false, "clarifying_question": "", "answer_options": []}',
        '{"insights": [], "metrics_used": ["get_top_hotels_by_revpar"], "confidence": "low"}',
    ]
    agent_configs = _agent_configs()
    fellowship = build_fellowship_subagents(
        repository=repository,
        llm=llm,
        store=None,
        agent_configs=agent_configs,
        radagast=RadagastAgent(
            llm=llm,
            weather_provider=FakeWeatherProvider(),
            config=agent_configs.require("radagast"),
        ),
    )
    tools = create_subagent_tools(
        aragorn=fellowship.aragorn,
        samwise=fellowship.samwise,
        elrond=fellowship.elrond,
        bilbo=fellowship.bilbo,
        faramir=fellowship.faramir,
        radagast=fellowship.radagast,
    )
    call_agent = next(tool for tool in tools if tool.name == "call_agent")

    result = await call_agent.ainvoke(
        {
            "agent_name": "elrond",
            "payload_json": '{"query": "Which hotels are performing best by RevPAR?"}',
        }
    )

    insights = result.update["insights"]
    assert repository.top_hotel_calls == 1
    assert insights
    assert "Alpine Retreat" in insights[0]
    assert "RevPAR $198.75" in insights[0]
    assert "Skyline Plaza" in insights[1]


@pytest.mark.asyncio
async def test_elrond_selects_revenue_tool_after_user_confirms_slots():
    repository = FakeRepository()
    llm = FakeLLM()
    llm.generate.side_effect = [
        '{"tool_names": ["get_top_hotels_by_revpar"], "needs_clarification": false, "clarifying_question": ""}',
        '{"insights": ["Alpine Retreat leads RevPAR."], "metrics_used": ["get_top_hotels_by_revpar"], "confidence": "medium"}',
    ]
    agent_configs = _agent_configs()
    fellowship = build_fellowship_subagents(
        repository=repository,
        llm=llm,
        store=None,
        agent_configs=agent_configs,
        radagast=RadagastAgent(
            llm=llm,
            weather_provider=FakeWeatherProvider(),
            config=agent_configs.require("radagast"),
        ),
    )
    tools = create_subagent_tools(
        aragorn=fellowship.aragorn,
        samwise=fellowship.samwise,
        elrond=fellowship.elrond,
        bilbo=fellowship.bilbo,
        faramir=fellowship.faramir,
        radagast=fellowship.radagast,
    )
    call_agent = next(tool for tool in tools if tool.name == "call_agent")

    result = await call_agent.ainvoke(
        {
            "agent_name": "elrond",
            "payload_json": '{"query": "Current portfolio hotels performing best by RevPAR"}',
        }
    )

    assert repository.top_hotel_calls == 1
    assert repository.last_top_metric == "revpar"
    assert "Alpine Retreat leads RevPAR." in result.update["insights"]


@pytest.mark.asyncio
async def test_elrond_can_interrupt_for_clarification_before_data_access():
    repository = FakeRepository()
    llm = FakeLLM()
    llm.generate.return_value = (
        '{"tool_names": [], "needs_clarification": true, '
        '"clarifying_question": "Which metric should I analyze?", '
        '"answer_options": ["Occupancy", "RevPAR", "Guest sentiment"]}'
    )
    agent_configs = _agent_configs()
    fellowship = build_fellowship_subagents(
        repository=repository,
        llm=llm,
        store=None,
        agent_configs=agent_configs,
        radagast=RadagastAgent(
            llm=llm,
            weather_provider=FakeWeatherProvider(),
            config=agent_configs.require("radagast"),
        ),
    )
    tools = create_subagent_tools(
        aragorn=fellowship.aragorn,
        samwise=fellowship.samwise,
        elrond=fellowship.elrond,
        bilbo=fellowship.bilbo,
        faramir=fellowship.faramir,
        radagast=fellowship.radagast,
    )
    call_agent = next(tool for tool in tools if tool.name == "call_agent")

    result = await call_agent.ainvoke(
        {
            "agent_name": "elrond",
            "payload_json": '{"query": "Tell me about hotels"}',
        }
    )

    update = result.update
    assert update["requires_approval"] is True
    assert update["approval_context"]["question"] == "Which metric should I analyze?"
    assert update["approval_context"]["options"] == [
        "Occupancy",
        "RevPAR",
        "Guest sentiment",
    ]
    assert repository.hotel_count_calls == 0
    assert repository.top_hotel_calls == 0
    assert repository.bottom_hotel_calls == 0


@pytest.mark.asyncio
async def test_bilbo_receives_response_format_and_reviewer_feedback():
    llm = FakeLLM()
    llm.generate.return_value = (
        '{"final_answer": "Alpine Retreat leads RevPAR at 184.20.", '
        '"summary_style": "insight_report", "assumptions": []}'
    )
    agent_configs = _agent_configs()
    fellowship = build_fellowship_subagents(
        repository=FakeRepository(),
        llm=llm,
        store=None,
        agent_configs=agent_configs,
        radagast=RadagastAgent(
            llm=llm,
            weather_provider=FakeWeatherProvider(),
            config=agent_configs.require("radagast"),
        ),
    )
    tools = create_subagent_tools(
        aragorn=fellowship.aragorn,
        samwise=fellowship.samwise,
        elrond=fellowship.elrond,
        bilbo=fellowship.bilbo,
        faramir=fellowship.faramir,
        radagast=fellowship.radagast,
    )
    call_agent = next(tool for tool in tools if tool.name == "call_agent")

    await call_agent.ainvoke(
        {
            "agent_name": "bilbo",
            "payload_json": (
                '{"query": "Rank revenue performers", '
                '"insights": ["Alpine Retreat RevPAR 184.20"], '
                '"response_format": "insight_report", '
                '"reviewer_feedback": ["include specific hotel names"]}'
            ),
        }
    )

    user_message = llm.generate.call_args.kwargs["user_message"]
    assert '"response_format": "insight_report"' in user_message
    assert "include specific hotel names" in user_message


@pytest.mark.asyncio
async def test_radagast_tool_is_always_wired():
    tools = _tools()
    call_agent = next(tool for tool in tools if tool.name == "call_agent")

    result = await call_agent.ainvoke(
        {
            "agent_name": "radagast",
            "payload_json": '{"location": "London", "query": "weather?"}',
        }
    )

    assert result.update["tool_results"]["radagast"]["data"]["condition"] == "clear"


@pytest.mark.asyncio
async def test_radagast_can_interrupt_for_location_clarification_before_weather():
    llm = FakeLLM()
    llm.generate.return_value = (
        '{"location": "", "needs_clarification": true, '
        '"clarifying_question": "Which city or hotel location should I check?", '
        '"answer_options": ["London", "Lisbon"]}'
    )
    agent_configs = _agent_configs()
    weather_provider = CountingWeatherProvider()
    fellowship = build_fellowship_subagents(
        repository=FakeRepository(),
        llm=llm,
        store=None,
        agent_configs=agent_configs,
        radagast=RadagastAgent(
            llm=llm,
            weather_provider=weather_provider,
            config=agent_configs.require("radagast"),
        ),
    )
    tools = create_subagent_tools(
        aragorn=fellowship.aragorn,
        samwise=fellowship.samwise,
        elrond=fellowship.elrond,
        bilbo=fellowship.bilbo,
        faramir=fellowship.faramir,
        radagast=fellowship.radagast,
    )
    call_agent = next(tool for tool in tools if tool.name == "call_agent")

    result = await call_agent.ainvoke(
        {
            "agent_name": "radagast",
            "payload_json": '{"query": "How is the weather for operations?"}',
        }
    )

    update = result.update
    assert update["requires_approval"] is True
    assert update["approval_context"] == {
        "agent": "radagast",
        "question": "Which city or hotel location should I check?",
        "options": ["London", "Lisbon"],
        "reason": "additional_user_input_required",
    }
    assert update["weather_context"] == {}
    assert weather_provider.calls == 0
