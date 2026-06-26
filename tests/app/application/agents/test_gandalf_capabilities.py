"""Tests for Gandalf capability discovery conversations."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.app.application.agents import gandalf as gandalf_module
from src.app.application.agents.config import AgentConfig, AgentLLMConfig
from src.app.application.agents.gandalf import GandalfAgent


class FakeTool:
    def __init__(self, name: str, result) -> None:
        self.name = name
        self.description = name
        self.result = result
        self.calls = []

    async def ainvoke(self, payload):
        self.calls.append(payload)
        if callable(self.result):
            return self.result(payload)
        return self.result


class PlanningLLM:
    def __init__(self, plan_response: str) -> None:
        self.plan_response = plan_response
        self.generate = AsyncMock(side_effect=self._generate_response)

    async def _generate_response(
        self, system_prompt: str, user_message: str, **kwargs
    ) -> str:
        # For capability questions, return a proper answer
        if (
            "capabilities" in user_message.lower()
            or "specialist agents" in user_message.lower()
        ):
            return (
                "This system provides hotel portfolio analytics including occupancy, RevPAR, "
                "revenue, sentiment, and trends. You can also get weather context for hotel "
                "locations. The system maintains conversation continuity and checks safety "
                "before accessing data."
            )
        return self.plan_response


class FakePlanningAgent:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = []

    async def ainvoke(self, payload):
        self.calls.append(payload)
        return {"messages": [SimpleNamespace(content=self.response)]}


def _agent_config() -> AgentConfig:
    return AgentConfig(
        name="gandalf",
        llm=AgentLLMConfig(
            provider="openrouter",
            model="test-gandalf-model",
            temperature=0.2,
        ),
        prompt="test prompt for gandalf",
        plan_prompt="test plan selector {query}",
    )


@pytest.mark.asyncio
async def test_gandalf_answers_capability_questions_from_discovered_agent_specs(
    monkeypatch,
):
    specs = [
        {
            "agent_name": "aragorn",
            "description": "Checks safety and hotel analytics scope before data access.",
            "input_schema": {"query": "Original user request."},
            "output_schema": {"is_compliant": "Whether the request may continue."},
            "private_tools": [],
        },
        {
            "agent_name": "samwise",
            "description": "Loads user preferences and conversation context.",
            "input_schema": {"state": "Supervisor state."},
            "output_schema": {"preferences": "Known user preferences."},
            "private_tools": ["load_user_preferences"],
        },
        {
            "agent_name": "elrond",
            "description": "Analyzes hotel portfolio performance, occupancy, RevPAR, guest sentiment, trends, and comparisons.",
            "input_schema": {"query": "Approved hotel analytics question."},
            "output_schema": {"insights": "Grounded hotel portfolio insights."},
            "private_tools": ["get_portfolio_metrics"],
        },
        {
            "agent_name": "radagast",
            "description": "Answers weather and nature-condition questions for a location.",
            "input_schema": {"location": "Location name.", "query": "Weather intent."},
            "output_schema": {"text": "Human-facing weather answer."},
            "private_tools": ["get_current_weather"],
        },
    ]
    list_agents = FakeTool("list_agents", json.dumps(specs))
    call_agent_bilbo = FakeTool(
        "call_agent_bilbo",
        _capability_call_agent_answer(
            "I can help you explore hotel portfolio performance, including RevPAR, occupancy, sentiment, and weather context."
        ),
    )
    call_agent_faramir = FakeTool(
        "call_agent_faramir",
        _capability_call_agent_answer(
            "I can help you explore hotel portfolio performance, including RevPAR, occupancy, sentiment, and weather context."
        ),
    )
    plan_response = json.dumps(
        {
            "intent": "capability",
            "response_format": "capability",
            "agent_plan": [],
        }
    )
    monkeypatch.setattr(
        gandalf_module,
        "create_agent",
        lambda **_: FakePlanningAgent(plan_response),
    )
    gandalf = GandalfAgent(
        llm=PlanningLLM(plan_response),
        tools=[list_agents, call_agent_bilbo, call_agent_faramir],
        config=_agent_config(),
    )

    result = await gandalf.run({"query": "what can you do"})

    assert result["final_answer"]
    assert "hotel portfolio" in result["final_answer"].lower()
    assert "weather" in result["final_answer"].lower()
    assert "aragorn" not in result["final_answer"].lower()
    assert "elrond" not in result["final_answer"].lower()
    assert "radagast" not in result["final_answer"].lower()
    assert len(call_agent_bilbo.calls) == 1
    assert len(call_agent_faramir.calls) == 1
    assert list_agents.calls == [{"query": ""}]


@pytest.mark.asyncio
async def test_gandalf_answers_follow_up_exploration_question_as_capabilities(
    monkeypatch,
):
    specs = [
        {
            "agent_name": "elrond",
            "description": "Analyzes hotel portfolio performance, occupancy, RevPAR, guest sentiment, trends, and comparisons.",
            "input_schema": {"query": "Approved hotel analytics question."},
            "output_schema": {"insights": "Grounded hotel portfolio insights."},
            "private_tools": ["get_top_hotels_by_revpar"],
        },
        {
            "agent_name": "radagast",
            "description": "Answers weather and nature-condition questions for a location.",
            "input_schema": {"location": "Location name.", "query": "Weather intent."},
            "output_schema": {"text": "Human-facing weather answer."},
            "private_tools": ["get_current_weather"],
        },
    ]
    list_agents = FakeTool("list_agents", json.dumps(specs))
    call_agent_bilbo = FakeTool(
        "call_agent_bilbo",
        _capability_call_agent_answer(
            "You could next ask for underperforming RevPAR hotels, strongest occupancy, weakest sentiment, or weather context."
        ),
    )
    call_agent_faramir = FakeTool(
        "call_agent_faramir",
        _capability_call_agent_answer(
            "You could next ask for underperforming RevPAR hotels, strongest occupancy, weakest sentiment, or weather context."
        ),
    )
    plan_response = json.dumps(
        {
            "intent": "capability",
            "response_format": "capability",
            "agent_plan": [],
        }
    )
    monkeypatch.setattr(
        gandalf_module,
        "create_agent",
        lambda **_: FakePlanningAgent(plan_response),
    )
    progress_events: list[str] = []
    monkeypatch.setattr(gandalf_module, "emit_progress", progress_events.append)
    gandalf = GandalfAgent(
        llm=PlanningLLM(plan_response),
        tools=[list_agents, call_agent_bilbo, call_agent_faramir],
        config=_agent_config(),
    )

    result = await gandalf.run({"query": "what else could you help me to see?"})

    answer = result["final_answer"].lower()
    assert "i need more information" not in answer
    assert "revpar" in answer
    assert "occupancy" in answer
    assert "sentiment" in answer
    assert len(call_agent_bilbo.calls) == 1
    assert len(call_agent_faramir.calls) == 1
    assert progress_events[0].startswith("Gandalf is ")
    assert progress_events[1].startswith("Bilbo is ")
    assert progress_events[2].startswith("Faramir is ")


def _capability_call_agent_answer(final_answer: str):
    def dispatch(payload):
        payload_json = json.loads(payload["payload_json"])
        # Faramir payload contains "final_answer" key
        if "final_answer" in payload_json and "response_format" not in payload_json:
            return json.dumps(
                {
                    "approved": True,
                    "warnings": [],
                    "required_changes": [],
                    "reasoning": "Capability answer is grounded in discovered specs.",
                }
            )
        assert payload_json["response_format"] == "capability"
        assert payload_json["insights"]
        insights_text = json.dumps(payload_json["insights"])
        assert "Checks safety" not in insights_text
        assert "Loads user preferences" not in insights_text
        assert "private_tools" not in insights_text
        assert "get_portfolio_metrics" not in insights_text
        assert "get_top_hotels_by_revpar" not in insights_text
        assert "load_user_preferences" not in insights_text
        assert "RevPAR" in insights_text
        assert "weather" in insights_text.lower()
        return json.dumps(
            {
                "final_answer": final_answer,
                "summary_style": "capability",
                "assumptions": [],
            }
        )

    return dispatch
