"""Faramir — final quality and safety review AI subagent."""

from __future__ import annotations

import json

from src.app.application.agents.base import LLMBackedSubagent, parse_json_object
from src.app.application.agents.config import AgentConfig
from src.app.application.ports import LLMAdapter


async def _retry_review(agent: LLMBackedSubagent, user_message: str) -> dict:
    """Retry review with corrected prompt after parse failure."""
    retry_prompt = (
        "Your previous response was not valid JSON. "
        "Return only a JSON object with keys: approved (boolean), "
        "warnings (array of strings), required_changes (array of strings), "
        "reasoning (string). Do not include any other text."
    )
    raw = await agent.generate(user_message + "\n\n" + retry_prompt)
    return parse_json_object(raw, fallback={})


class FaramirAgent(LLMBackedSubagent):
    """AI subagent responsible for final answer review (safety, quality, groundedness)."""

    def __init__(self, llm: LLMAdapter, config: AgentConfig) -> None:
        super().__init__(name="faramir", llm=llm, config=config)

    async def review(
        self,
        *,
        query: str,
        final_answer: str,
        insights: list[str],
        compliance_status: dict,
        user_context: dict | None = None,
        weather_context: dict | None = None,
    ) -> dict:
        """Review whether a final answer can be returned for safety and quality."""
        if not final_answer or len(final_answer.strip()) < 10:
            return {
                "approved": False,
                "warnings": ["Final answer is too short."],
                "required_changes": ["Bilbo must provide a more useful answer."],
                "reasoning": "The drafted answer is too short to be useful.",
            }

        user_message = json.dumps(
            {
                "query": query,
                "final_answer": final_answer,
                "insights": insights,
                "user_context": user_context or {},
                "weather_context": weather_context or {},
                "compliance_status": compliance_status,
            },
            indent=2,
        )

        raw = await self.generate(user_message)
        result = parse_json_object(
            raw,
            fallback={
                "approved": False,
                "warnings": [],
                "required_changes": ["Faramir returned invalid JSON."],
                "reasoning": "Review output could not be parsed.",
            },
        )

        if not result:
            result = await _retry_review(self, user_message)

        result.setdefault("approved", False)
        result.setdefault("warnings", [])
        result.setdefault("required_changes", [])
        result.setdefault("reasoning", "No reasoning provided by Faramir.")
        return result
