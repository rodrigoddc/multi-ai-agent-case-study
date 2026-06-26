"""Tests for common LLM-backed agent helpers."""

from src.app.application.agents.base import parse_json_object


def test_parse_json_object_accepts_fenced_json():
    parsed = parse_json_object(
        '```json\n{"is_compliant": true, "violations": []}\n```',
        fallback={"is_compliant": False},
    )

    assert parsed == {"is_compliant": True, "violations": []}


def test_parse_json_object_extracts_json_from_surrounding_text():
    parsed = parse_json_object(
        'Here is the result: {"approved": true, "warnings": []}',
        fallback={"approved": False},
    )

    assert parsed == {"approved": True, "warnings": []}


def test_parse_json_object_returns_fallback_for_non_object_json():
    parsed = parse_json_object('["not", "object"]', fallback={"ok": False})

    assert parsed == {"ok": False}


def test_parse_json_object_extracts_last_json_after_reasoning_trace():
    parsed = parse_json_object(
        """
* The request is hotel analytics.
* Plan: {not valid json, just reasoning text}

{"intent": "hotel_analytics", "agent_plan": ["aragorn", "elrond", "bilbo", "faramir"]}
The user wants a narrative analysis.
""",
        fallback={"intent": "invalid"},
    )

    assert parsed == {
        "intent": "hotel_analytics",
        "agent_plan": ["aragorn", "elrond", "bilbo", "faramir"],
    }


def test_parse_json_object_ignores_thinking_block_before_json():
    parsed = parse_json_object(
        """
<think>
I should call the portfolio tools first.
</think>
```json
{"tool_names": ["get_portfolio_metrics"], "needs_clarification": false}
```
""",
        fallback={"needs_clarification": True},
    )

    assert parsed == {
        "tool_names": ["get_portfolio_metrics"],
        "needs_clarification": False,
    }
