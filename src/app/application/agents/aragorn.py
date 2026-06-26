"""Aragorn — safety and scope AI subagent."""

from __future__ import annotations

from src.app.application.agents.base import LLMBackedSubagent, parse_json_object
from src.app.application.agents.config import AgentConfig
from src.app.application.ports import LLMAdapter


def _blocked_parse_result() -> dict:
    return {
        "is_compliant": False,
        "violations": ["Aragorn returned invalid JSON"],
        "warnings": [],
        "reasoning": "Compliance output could not be parsed, so the request was blocked.",
    }


class AragornAgent(LLMBackedSubagent):
    """AI subagent responsible for pre-flight compliance checks."""

    def __init__(self, llm: LLMAdapter, config: AgentConfig) -> None:
        super().__init__(name="aragorn", llm=llm, config=config)

    async def check_query(self, query: str) -> dict:
        """Check whether a query can safely proceed to analysis."""
        raw = await self.generate(f"Query: {query}")
        result = parse_json_object(raw, fallback=_blocked_parse_result())
        result.setdefault("is_compliant", False)
        result.setdefault("violations", [])
        result.setdefault("warnings", [])
        result.setdefault("reasoning", "No reasoning provided by Aragorn.")
        return result
