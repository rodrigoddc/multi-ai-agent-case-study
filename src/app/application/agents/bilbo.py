"""Bilbo — final answer writing AI subagent."""

from __future__ import annotations

import json

from src.app.application.agents.base import LLMBackedSubagent, parse_json_object
from src.app.application.agents.config import AgentConfig
from src.app.application.ports import LLMAdapter


_IDENTITY_QUERY_TERMS = (
    "my name",
    "do you know my name",
    "who am i",
    "who i am",
    "my identity",
    "saved preference",
    "saved preferences",
    "i like",
    "i prefer",
    "i love",
    "please include",
    "please use",
    "remember that",
    "remember my",
    "save my",
    "store my",
)


class BilboAgent(LLMBackedSubagent):
    """AI subagent responsible for user-facing answer writing."""

    def __init__(self, llm: LLMAdapter, config: AgentConfig) -> None:
        super().__init__(name="bilbo", llm=llm, config=config)

    async def write_answer(
        self,
        *,
        query: str,
        insights: list[str],
        user_context: dict,
        compliance_status: dict,
        weather_context: dict | None = None,
        evidence: dict | None = None,
        response_format: str = "detailed",
        reviewer_feedback: list[str] | None = None,
    ) -> dict:
        """Write a final answer from approved analysis context."""
        weather_context = weather_context or {}
        evidence = evidence or {}

        format_instructions = {
            "short_simple": (
                "Write a single paragraph with a direct, concise answer. "
                "No markdown, no bullet points, no formatting. Just plain text."
            ),
            "detailed": (
                "Write a clear, structured explanation. Use short paragraphs. "
                "Bullet points acceptable for clarity but keep minimal. "
                "No markdown headings or tables."
            ),
            "insight_report": (
                "Write a full analytical report in Markdown format. "
                "Use ## headings for sections, **bold** for key metrics, "
                "Markdown tables for data, bullet points for findings. "
                "Include sections: Executive Summary, Key Metrics, Analysis, Recommendations. "
                "Be comprehensive and professional."
            ),
            "capability": (
                "Write a conversational explanation of what this system can do. "
                "Do not mention internal agent names. Give concrete examples. "
                "Plain text, no markdown formatting."
            ),
        }
        format_instruction = format_instructions.get(
            response_format, format_instructions["detailed"]
        )

        if not compliance_status.get("is_compliant", True):
            user_message = json.dumps(
                {
                    "query": query,
                    "insights": insights,
                    "evidence": evidence,
                    "weather_context": weather_context,
                    "user_context": user_context,
                    "compliance_status": compliance_status,
                    "response_format": response_format,
                    "reviewer_feedback": reviewer_feedback or [],
                    "instruction": (
                        "The request failed compliance checks. Write a brief, courteous "
                        "explanation and offer to help with a different question."
                    ),
                },
                indent=2,
            )
        elif not insights and not weather_context and not evidence:
            instruction = _missing_data_instruction(query)
            user_message = json.dumps(
                {
                    "query": query,
                    "insights": [],
                    "evidence": evidence,
                    "weather_context": weather_context,
                    "user_context": user_context,
                    "compliance_status": compliance_status,
                    "response_format": response_format,
                    "reviewer_feedback": reviewer_feedback or [],
                    "instruction": instruction,
                },
                indent=2,
            )
        else:
            user_message = json.dumps(
                {
                    "query": query,
                    "insights": insights,
                    "evidence": evidence,
                    "weather_context": weather_context,
                    "user_context": user_context,
                    "compliance_status": compliance_status,
                    "response_format": response_format,
                    "instruction": (
                        f"Write a clear, helpful answer using only the provided context. "
                        f"{format_instruction} "
                        "If upstream analysis says clarification is required, ask that "
                        "clarifying question. Otherwise, answer from provided insights "
                        "and evidence. If tool evidence is empty, say no matching hotel "
                        "performance data was returned. Do not invent filters, values, "
                        "or hotel records."
                    ),
                    "reviewer_feedback": reviewer_feedback or [],
                },
                indent=2,
            )

        raw = await self.generate(user_message)
        result = self._parse_final_answer(raw)
        if result is None:
            # ponytail: model output didn't parse as JSON but may contain useful text.
            # Use raw output directly rather than crashing.
            return {
                "final_answer": raw.strip() or "I couldn't generate a response.",
                "summary_style": "detailed",
                "assumptions": [],
            }

        return result

    def _parse_final_answer(self, raw: str) -> dict[str, object] | None:
        """Parse Bilbo output and validate final_answer is present."""
        result = parse_json_object(raw, fallback={})
        if not isinstance(result, dict):
            return None

        final_answer = result.get("final_answer")
        if not isinstance(final_answer, str) or not final_answer.strip():
            return None

        return {
            "final_answer": final_answer.strip(),
            "summary_style": result.get("summary_style", "detailed"),
            "assumptions": result.get("assumptions") or [],
        }


def _missing_data_instruction(query: str) -> str:
    normalized_query = query.lower()
    if any(term in normalized_query for term in _IDENTITY_QUERY_TERMS):
        return (
            "No analysis results or weather data are available because this is a "
            "memory request. Answer directly from user_context.preferences when "
            "available. If no matching preference is present, say it is not saved yet."
        )
    return (
        "No analysis results or weather data are available. Ask the user a "
        "clarifying question to understand what information they need, and explain "
        "what you can help with."
    )
