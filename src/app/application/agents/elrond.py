"""Elrond — hotel portfolio analysis AI subagent."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool

from src.app.application.agents.base import LLMBackedSubagent, parse_json_object
from src.app.application.agents.config import AgentConfig
from src.app.application.progress import emit_tool_call
from src.app.application.ports import HotelRepository, LLMAdapter

TOOL_TAG_PREFIX = "tool:"


@dataclass(frozen=True, slots=True)
class AgentTool:
    """Private tool metadata and executor owned by one subagent."""

    name: str
    description: str
    coroutine: Callable[[], Awaitable[Any]]


class ElrondAgent(LLMBackedSubagent):
    """AI subagent responsible for hotel portfolio insights."""

    def __init__(
        self,
        repository: HotelRepository,
        llm: LLMAdapter,
        config: AgentConfig,
    ) -> None:
        self.repository = repository
        self.private_tools = self._build_private_tools()
        if config.tool_selection_prompt is None:
            raise ValueError("Elrond tool_selection_prompt is required in agent config")
        self.tool_selection_prompt = config.tool_selection_prompt
        super().__init__(
            name="elrond",
            llm=llm,
            config=config,
            tools=list(_as_structured_tools(self.private_tools)),
        )

    async def analyze(self, query: str) -> dict:
        """Analyze hotel portfolio data after selecting required private tools."""
        selected = await self._select_tools(query)
        if selected.get("needs_clarification", False):
            return {
                "insights": [],
                "metrics_used": [],
                "confidence": "low",
                "needs_clarification": True,
                "clarifying_question": str(
                    selected.get("clarifying_question")
                    or "Which metric, timeframe, or hotel segment should I analyze?"
                ),
                "answer_options": _answer_options(selected),
            }

        data = await self._run_selected_tools(selected.get("tool_names", []))
        if not data:
            return {
                "insights": [],
                "metrics_used": [],
                "confidence": "low",
                "needs_clarification": True,
                "clarifying_question": "Which hotel metric or comparison should I analyze?",
                "answer_options": [],
            }

        raw = await self.generate(
            "Analyze the approved hotel question using only the tool results below.\n"
            + json.dumps(
                {"question": query, "tool_results": data}, default=str, indent=2
            )
        )
        tool_evidence = _evidence_from_tool_results(data)
        result = parse_json_object(
            raw,
            fallback={
                "insights": tool_evidence,
                "metrics_used": list(data.keys()),
                "confidence": "low",
                "needs_clarification": False,
                "clarifying_question": "",
            },
        )
        insights = _clean_insights(result.get("insights"))
        if not insights:
            insights = tool_evidence
        else:
            insights = _append_missing_evidence(insights, tool_evidence)
        if not insights and raw.strip():
            insights = [raw.strip()]
        if not insights:
            return {
                "insights": [],
                "metrics_used": list(data.keys()),
                "confidence": "low",
                "needs_clarification": True,
                "clarifying_question": "I found no hotel records for that analysis. Which hotel segment or metric should I use instead?",
                "answer_options": [],
            }
        result["insights"] = insights
        result.setdefault("metrics_used", list(data.keys()))
        result["tool_results"] = data
        result.setdefault("confidence", "medium")
        result["needs_clarification"] = False
        result["clarifying_question"] = ""
        return result

    def _build_private_tools(self) -> dict[str, AgentTool]:
        return {
            "get_portfolio_metrics": AgentTool(
                name="get_portfolio_metrics",
                description="Read portfolio count, occupancy, RevPAR, and sentiment averages.",
                coroutine=self._get_portfolio_metrics,
            ),
            "get_top_hotels_by_revpar": AgentTool(
                name="get_top_hotels_by_revpar",
                description="Read the top hotels by RevPAR, the available revenue metric.",
                coroutine=self._get_top_hotels_by_revpar,
            ),
            "get_top_hotels_by_occupancy": AgentTool(
                name="get_top_hotels_by_occupancy",
                description="Read the top hotels by occupancy rate.",
                coroutine=self._get_top_hotels_by_occupancy,
            ),
            "get_top_hotels_by_sentiment": AgentTool(
                name="get_top_hotels_by_sentiment",
                description="Read the top hotels by guest sentiment score.",
                coroutine=self._get_top_hotels_by_sentiment,
            ),
            "get_underperforming_hotels_by_revpar": AgentTool(
                name="get_underperforming_hotels_by_revpar",
                description="Read the weakest hotels by RevPAR, the available revenue metric.",
                coroutine=self._get_underperforming_hotels_by_revpar,
            ),
            "get_underperforming_hotels_by_occupancy": AgentTool(
                name="get_underperforming_hotels_by_occupancy",
                description="Read the weakest hotels by occupancy rate.",
                coroutine=self._get_underperforming_hotels_by_occupancy,
            ),
            "get_underperforming_hotels_by_sentiment": AgentTool(
                name="get_underperforming_hotels_by_sentiment",
                description="Read the weakest hotels by guest sentiment score.",
                coroutine=self._get_underperforming_hotels_by_sentiment,
            ),
            "get_hotels_by_trend": AgentTool(
                name="get_hotels_by_trend",
                description="Read hotels filtered by guest sentiment trend such as declining, rising, stable, or softening.",
                coroutine=self._get_hotels_by_trend,
            ),
        }

    async def _select_tools(self, query: str) -> dict[str, Any]:
        """Ask the agent (via its configured tool_selection_prompt) to choose private tools.

        This function enforces config-only behavior: there is no local heuristic fallback.
        If the model fails to return a valid JSON object with "tool_names", the agent
        must ask the user to clarify.
        """
        raw = await self.generate(
            _format_tool_selection_prompt(
                self.tool_selection_prompt,
                query=query,
                tool_descriptions=_tool_descriptions(self.private_tools),
            )
        )
        selected = parse_json_object(
            raw,
            fallback={
                "tool_names": [],
                "needs_clarification": True,
                "clarifying_question": "I couldn't determine which tools are needed. Which metric, timeframe, or hotel segment should I analyze?",
                "answer_options": [],
            },
        )
        tool_names = selected.get("tool_names", [])
        if not isinstance(tool_names, list):
            # Model returned an unexpected schema; require clarification.
            return {
                "tool_names": [],
                "needs_clarification": True,
                "clarifying_question": str(
                    selected.get("clarifying_question")
                    or "Please clarify which metrics, timeframe, or hotel segment to analyze."
                ),
                "answer_options": _answer_options(selected),
            }
        # Normalize and filter tool names strictly to the agent's private tools
        selected_names = [
            name
            for name in tool_names
            if isinstance(name, str) and name in self.private_tools
        ]
        if not selected_names:
            return {
                "tool_names": [],
                "needs_clarification": True,
                "clarifying_question": str(
                    selected.get("clarifying_question")
                    or "No valid private tools were selected. Which metric, timeframe, or segment should I analyze?"
                ),
                "answer_options": _answer_options(selected),
            }
        return {
            "tool_names": selected_names,
            "needs_clarification": False,
            "clarifying_question": "",
            "answer_options": [],
        }

    async def _run_selected_tools(self, tool_names: list[str]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for tool_name in dict.fromkeys(tool_names):
            tool = self.private_tools.get(tool_name)
            if tool is None:
                continue
            emit_tool_call(tool.name)
            results[tool.name] = await tool.coroutine()
        return results

    async def _get_portfolio_metrics(self) -> dict[str, Any]:
        return {
            "hotel_count": await self.repository.get_hotel_count(),
            "average_occupancy_rate": await self.repository.get_average_occupancy(),
            "average_revpar": await self.repository.get_average_revpar(),
            "average_sentiment": await self.repository.get_average_sentiment(),
        }

    async def _get_top_hotels_by_revpar(self) -> list[dict[str, Any]]:
        top_hotels = await self.repository.get_top_hotels("revpar", 3)
        return [_serialize_hotel(h) for h in top_hotels]

    async def _get_top_hotels_by_occupancy(self) -> list[dict[str, Any]]:
        top_hotels = await self.repository.get_top_hotels("occupancy", 3)
        return [_serialize_hotel(h) for h in top_hotels]

    async def _get_top_hotels_by_sentiment(self) -> list[dict[str, Any]]:
        top_hotels = await self.repository.get_top_hotels("sentiment", 3)
        return [_serialize_hotel(h) for h in top_hotels]

    async def _get_underperforming_hotels_by_revpar(self) -> list[dict[str, Any]]:
        bottom_hotels = await self.repository.get_bottom_hotels("revpar", 3)
        return [_serialize_hotel(h) for h in bottom_hotels]

    async def _get_underperforming_hotels_by_occupancy(self) -> list[dict[str, Any]]:
        bottom_hotels = await self.repository.get_bottom_hotels("occupancy", 3)
        return [_serialize_hotel(h) for h in bottom_hotels]

    async def _get_underperforming_hotels_by_sentiment(self) -> list[dict[str, Any]]:
        bottom_hotels = await self.repository.get_bottom_hotels("sentiment", 3)
        return [_serialize_hotel(h) for h in bottom_hotels]

    async def _get_hotels_by_trend(self) -> list[dict[str, Any]]:
        hotels = await self.repository.get_hotels_by_trend("softening", 5)
        return [_serialize_hotel(h) for h in hotels]


def _tool_descriptions(tools: dict[str, AgentTool]) -> str:
    return "\n".join(f"- {tool.name}: {tool.description}" for tool in tools.values())


def _clean_insights(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    insights: list[str] = []
    for item in value:
        text = _fact_text(item)
        if text:
            insights.append(text)
    return insights


def _evidence_from_tool_results(data: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    for tool_name, result in data.items():
        if isinstance(result, list):
            evidence.extend(_ranked_hotel_evidence(tool_name=tool_name, rows=result))
            continue
        if isinstance(result, dict):
            text = _portfolio_metrics_evidence(result)
            if text:
                evidence.append(text)
            continue
        text = _fact_text(result)
        if text:
            evidence.append(f"{tool_name}: {text}")
    return evidence


def _append_missing_evidence(insights: list[str], evidence: list[str]) -> list[str]:
    existing = set(insights)
    return [*insights, *(item for item in evidence if item not in existing)]


def _ranked_hotel_evidence(*, tool_name: str, rows: list[Any]) -> list[str]:
    label = _tool_result_label(tool_name)
    if not rows:
        return [f"{label} returned no hotel records."]
    evidence: list[str] = []
    for index, row in enumerate(rows, start=1):
        hotel = row if isinstance(row, dict) else _serialize_hotel(row)
        name = _fact_text(hotel.get("name")) or f"Hotel {hotel.get('id', index)}"
        facts = _hotel_metric_facts(hotel)
        suffix = f": {', '.join(facts)}" if facts else ""
        evidence.append(f"{label} #{index}: {name}{suffix}.")
    return evidence


def _portfolio_metrics_evidence(result: dict[str, Any]) -> str:
    facts: list[str] = []
    hotel_count = result.get("hotel_count")
    if hotel_count is not None:
        facts.append(f"{hotel_count} hotels")
    occupancy = _format_percent(result.get("average_occupancy_rate"))
    if occupancy:
        facts.append(f"average occupancy {occupancy}")
    revpar = _format_money(result.get("average_revpar"))
    if revpar:
        facts.append(f"average RevPAR {revpar}")
    sentiment = _format_number(result.get("average_sentiment"))
    if sentiment:
        facts.append(f"average sentiment {sentiment}")
    if facts:
        return "Portfolio metrics: " + ", ".join(facts) + "."
    return _fact_text(result)


def _hotel_metric_facts(hotel: dict[str, Any]) -> list[str]:
    facts: list[str] = []
    revpar = _format_money(hotel.get("revpar"))
    if revpar:
        facts.append(f"RevPAR {revpar}")
    occupancy = _format_percent(hotel.get("occupancy_rate"))
    if occupancy:
        facts.append(f"occupancy {occupancy}")
    adr = _format_money(hotel.get("average_daily_rate"))
    if adr:
        facts.append(f"ADR {adr}")
    sentiment = _format_number(hotel.get("sentiment_score", hotel.get("avg_sentiment")))
    if sentiment:
        facts.append(f"sentiment {sentiment}")
    return facts


def _tool_result_label(tool_name: str) -> str:
    labels = {
        "get_top_hotels_by_revpar": "Top hotels by RevPAR",
        "get_top_hotels_by_occupancy": "Top hotels by occupancy",
        "get_top_hotels_by_sentiment": "Top hotels by guest sentiment",
        "get_underperforming_hotels_by_revpar": "Underperforming hotels by RevPAR",
        "get_underperforming_hotels_by_occupancy": "Underperforming hotels by occupancy",
        "get_underperforming_hotels_by_sentiment": "Underperforming hotels by guest sentiment",
        "get_hotels_by_trend": "Hotels by guest sentiment trend",
    }
    return labels.get(tool_name, tool_name)


def _fact_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str, sort_keys=True)
    return str(value).strip()


def _format_money(value: Any) -> str:
    number = _number(value)
    if number is None:
        return ""
    return f"${number:.2f}"


def _format_percent(value: Any) -> str:
    number = _number(value)
    if number is None:
        return ""
    if abs(number) <= 1:
        number *= 100
    return f"{number:.1f}%"


def _format_number(value: Any) -> str:
    number = _number(value)
    if number is None:
        return ""
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def _answer_options(result: dict[str, Any]) -> list[str]:
    raw_options = result.get("answer_options", [])
    if not isinstance(raw_options, list):
        return []
    return [option for option in raw_options if isinstance(option, str) and option]


def _format_tool_selection_prompt(
    template: str, *, query: str, tool_descriptions: str
) -> str:
    try:
        return template.format(query=query, tool_descriptions=tool_descriptions)
    except KeyError as exc:
        raise ValueError(
            "Elrond tool_selection_prompt contains unescaped literal braces. "
            'Escape JSON examples with doubled braces, e.g. {{"tool_names": []}}.'
        ) from exc


def _fallback_tool_selection(query: str) -> list[str]:
    raise RuntimeError(
        "Fallback tool selection is banned. Agent must provide tool_names via its tool_selection_prompt in config."
    )


def _as_structured_tools(tools: dict[str, AgentTool]) -> Sequence[StructuredTool]:
    return tuple(
        StructuredTool.from_function(
            coroutine=tool.coroutine,
            name=tool.name,
            description=tool.description,
            tags=[_tool_tag(tool.name)],
            metadata={"tool_name": tool.name, "langfuse_tags": [_tool_tag(tool.name)]},
        )
        for tool in tools.values()
    )


def _tool_tag(tool_name: str) -> str:
    return f"{TOOL_TAG_PREFIX}{tool_name}"


def _serialize_hotel(hotel: Any) -> dict[str, Any]:
    return {
        "id": getattr(hotel, "id", None),
        "name": getattr(hotel, "name", None),
        "brand": getattr(hotel, "brand", None),
        "city": getattr(hotel, "city", getattr(hotel, "region", None)),
        "country": getattr(hotel, "country", None),
        "occupancy_rate": getattr(hotel, "occupancy_rate", None),
        "average_daily_rate": getattr(hotel, "average_daily_rate", None),
        "revpar": getattr(hotel, "revpar", None),
        "sentiment_score": getattr(
            hotel, "sentiment_score", getattr(hotel, "avg_sentiment", None)
        ),
    }
