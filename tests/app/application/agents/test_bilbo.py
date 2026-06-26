import json
from unittest.mock import AsyncMock

import pytest

from src.app.application.agents.bilbo import BilboAgent, _missing_data_instruction
from src.app.application.agents.config import AgentConfig, AgentLLMConfig


def _config() -> AgentConfig:
    return AgentConfig(
        name="bilbo",
        llm=AgentLLMConfig(
            provider="openrouter",
            model="test-bilbo-model",
            temperature=0.2,
        ),
        prompt="test bilbo prompt",
    )


@pytest.mark.asyncio
async def test_bilbo_receives_structured_evidence_without_disabling_clarification():
    llm = AsyncMock()
    llm.generate.return_value = json.dumps(
        {
            "final_answer": "Please specify which hotel or period you want compared.",
            "summary_style": "clarification",
            "assumptions": [],
        }
    )
    agent = BilboAgent(llm=llm, config=_config())

    result = await agent.write_answer(
        query="Compare hotel A and hotel B by revenue.",
        insights=["Hotel A has incomplete revenue context."],
        evidence={"tool_results": {"get_top_hotels_by_revpar": [{"name": "Hotel A"}]}},
        user_context={},
        compliance_status={"is_compliant": True},
        response_format="short_simple",
    )

    assert (
        result["final_answer"]
        == "Please specify which hotel or period you want compared."
    )
    user_message = llm.generate.call_args.kwargs["user_message"]
    assert '"evidence"' in user_message
    assert "Do not invent filters" in user_message


def test_bilbo_treats_identity_questions_as_memory_requests() -> None:
    instruction = _missing_data_instruction("What is my name?")

    assert "memory request" in instruction
    assert "user_context.preferences" in instruction
    assert "not saved yet" in instruction


def test_bilbo_treats_preference_setting_as_memory_request() -> None:
    instruction = _missing_data_instruction(
        "I like emojis, please include them in all your responses"
    )

    assert "memory request" in instruction
    assert "user_context.preferences" in instruction


def test_bilbo_asks_clarifying_question_when_not_memory_or_preference() -> None:
    instruction = _missing_data_instruction("What is the average RevPAR?")

    assert "clarifying question" in instruction
    assert "what you can help with" in instruction
