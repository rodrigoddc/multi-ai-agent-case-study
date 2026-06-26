"""Radagast — nature-focused LOTR-style subagent that answers weather questions."""

from __future__ import annotations

from typing import Any

import json

from src.app.application.agents.base import LLMBackedSubagent, parse_json_object
from src.app.application.agents.config import AgentConfig
from src.app.application.ports import LLMAdapter, WeatherProvider


class RadagastAgent(LLMBackedSubagent):
    """LOTR-named agent that composes weather facts and an LLM to answer queries."""

    def __init__(
        self,
        *,
        llm: LLMAdapter,
        weather_provider: WeatherProvider,
        config: AgentConfig,
    ) -> None:
        super().__init__(name="radagast", llm=llm, config=config)
        self.weather_provider = weather_provider

    async def answer(
        self, location: str, *, query: str | None = None
    ) -> dict[str, Any]:
        """Return a dict with a rendered human-facing answer and raw data."""
        selected_location = location.strip()
        if not selected_location:
            selected = await self._select_weather_request(query or "")
            if selected.get("needs_clarification", False):
                return _clarification_response(selected)
            selected_location = str(selected.get("location", "")).strip()
            if not selected_location:
                return _clarification_response(selected)

        data = await self.weather_provider.get_current_weather(selected_location)
        user_message = (
            json.dumps(
                {"location": selected_location, "data": data}, default=str, indent=2
            )
            + "\nQuestion: "
            + (query or "Provide a short summary of current conditions.")
        )
        raw = await self.generate(user_message)
        # Try to parse LLM output as JSON; if it fails, wrap plain text into schema
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {
                "final_answer": raw.strip(),
                "summary_style": "concise",
                "assumptions": [],
            }
        parsed.setdefault("final_answer", "")
        parsed.setdefault("summary_style", "concise")
        parsed.setdefault("assumptions", [])
        return {
            "text": str(parsed.get("final_answer")),
            "data": data,
            "meta": parsed,
            "needs_clarification": False,
            "clarifying_question": "",
            "answer_options": [],
        }

    async def _select_weather_request(self, query: str) -> dict[str, Any]:
        raw = await self.generate(
            "Decide whether this weather or location-condition request has enough "
            "location context to call weather data. Return JSON only with keys: "
            "location, needs_clarification, clarifying_question, answer_options.\n"
            + json.dumps({"query": query}, default=str, indent=2)
        )
        return parse_json_object(
            raw,
            fallback={
                "location": "",
                "needs_clarification": True,
                "clarifying_question": raw.strip(),
                "answer_options": [],
            },
        )


def _clarification_response(result: dict[str, Any]) -> dict[str, Any]:
    question = str(result.get("clarifying_question") or "").strip()
    if not question:
        question = "Which location should I check weather for?"
    return {
        "text": "",
        "data": {},
        "meta": {},
        "needs_clarification": True,
        "clarifying_question": question,
        "answer_options": _answer_options(result),
    }


def _answer_options(result: dict[str, Any]) -> list[str]:
    raw_options = result.get("answer_options", [])
    if not isinstance(raw_options, list):
        return []
    return [option for option in raw_options if isinstance(option, str) and option]
