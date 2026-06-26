"""Tool wrappers that expose LOTR subagents to Gandalf via single dispatch tool pattern.

Subagents are wrapped as callable handles and exposed via two tools:
- list_agents: discovers available subagents
- call_agent: dispatches a request to one subagent by name
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.tools import StructuredTool
from langgraph.types import Command

from src.app.application.agents.aragorn import AragornAgent
from src.app.application.agents.bilbo import BilboAgent
from src.app.application.agents.elrond import ElrondAgent
from src.app.application.agents.faramir import FaramirAgent
from src.app.application.agents.radagast import RadagastAgent
from src.app.application.agents.samwise import SamwiseAgent
from src.app.application.agents.config import AgentConfig, AgentConfigRegistry
from src.app.application.ports import HotelRepository, LLMAdapter, WeatherProvider

TOOL_TAG_PREFIX = "tool:"


@dataclass(frozen=True, slots=True)
class SubagentSpec:
    """Public contract Gandalf uses to discover a subagent."""

    name: str
    agent_name: str
    description: str
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    private_tools: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FellowshipSubagents:
    """All subagents available to Gandalf."""

    aragorn: AragornAgent
    samwise: SamwiseAgent
    elrond: ElrondAgent
    bilbo: BilboAgent
    faramir: FaramirAgent
    radagast: RadagastAgent


class SubagentHandle(Protocol):
    """Pluggable public wrapper around one specialist subagent."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def input_schema(self) -> dict[str, str]: ...

    @property
    def output_schema(self) -> dict[str, str]: ...

    @property
    def private_tools(self) -> tuple[str, ...]: ...

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class FunctionSubagentHandle:
    """Subagent handle backed by an async callable."""

    name: str
    description: str
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    private_tools: tuple[str, ...]
    invoke_payload: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.invoke_payload(payload)


SUBAGENT_SPECS: tuple[SubagentSpec, ...] = (
    SubagentSpec(
        name="aragorn",
        agent_name="aragorn",
        description="Checks request safety, policy, and hotel-analytics scope before data access.",
        input_schema={"query": "Original user request."},
        output_schema={
            "is_compliant": "Whether the fellowship may continue.",
            "violations": "Blocking policy or scope violations.",
            "warnings": "Non-blocking cautions.",
            "reasoning": "Short compliance rationale.",
        },
        private_tools=(),
    ),
    SubagentSpec(
        name="samwise",
        agent_name="samwise",
        description="Loads user preferences and conversation context from fellowship memory.",
        input_schema={"state": "Supervisor state needed for memory lookup."},
        output_schema={
            "user_id": "Resolved user id.",
            "preferences": "Known user preferences.",
            "message_count": "Conversation message count.",
        },
        private_tools=("load_user_preferences", "remember_user_preference"),
    ),
    SubagentSpec(
        name="elrond",
        agent_name="elrond",
        description=(
            "Analyzes read-only hotel portfolio performance, including occupancy, "
            "RevPAR, guest sentiment, top performers, underperformers, trends, "
            "rankings, and comparisons."
        ),
        input_schema={"query": "Approved hotel analytics question."},
        output_schema={
            "insights": "Grounded hotel portfolio insights.",
            "metrics_used": "Metrics or private tools used in the answer.",
            "confidence": "low, medium, or high.",
            "needs_clarification": "Whether Elrond needs the user to narrow metric, timeframe, or segment.",
            "clarifying_question": "Question to ask the user before analysis can continue.",
            "answer_options": "Optional concise user-selectable clarification answers.",
        },
        private_tools=(
            "get_portfolio_metrics",
            "get_top_hotels_by_revpar",
            "get_top_hotels_by_occupancy",
            "get_top_hotels_by_sentiment",
            "get_underperforming_hotels_by_revpar",
            "get_underperforming_hotels_by_occupancy",
            "get_underperforming_hotels_by_sentiment",
            "get_hotels_by_trend",
        ),
    ),
    SubagentSpec(
        name="radagast",
        agent_name="radagast",
        description=(
            "Answers current weather and location-condition questions for hotel "
            "operations, including practical context for staffing, guest messaging, "
            "outdoor amenities, and events."
        ),
        input_schema={
            "location": "Location name or coordinates.",
            "query": "Optional weather intent.",
        },
        output_schema={
            "text": "Human-facing weather answer.",
            "data": "Provider weather facts.",
            "meta": "Rendering metadata and assumptions.",
            "needs_clarification": "Whether Radagast needs the user to provide or disambiguate location context.",
            "clarifying_question": "Question to ask the user before weather data can be used.",
            "answer_options": "Optional concise user-selectable clarification answers.",
        },
        private_tools=("get_current_weather",),
    ),
    SubagentSpec(
        name="bilbo",
        agent_name="bilbo",
        description="Writes the concise user-facing answer from approved evidence and context.",
        input_schema={
            "query": "Original request.",
            "insights": "Evidence from prior subagents.",
            "user_context": "Memory context.",
            "compliance_status": "Aragorn output.",
            "weather_context": "Optional Radagast output.",
        },
        output_schema={
            "final_answer": "User-facing answer.",
            "summary_style": "concise, refusal, or analytical.",
            "assumptions": "Explicit assumptions.",
        },
        private_tools=(),
    ),
    SubagentSpec(
        name="faramir",
        agent_name="faramir",
        description="Reviews groundedness, safety, and final answer quality before return.",
        input_schema={
            "query": "Original request.",
            "final_answer": "Bilbo draft.",
            "insights": "Evidence from prior subagents.",
            "compliance_status": "Aragorn output.",
            "weather_context": "Optional Radagast output.",
        },
        output_schema={
            "approved": "Whether the final answer can be returned.",
            "warnings": "Non-blocking review notes.",
            "required_changes": "Blocking required changes.",
            "reasoning": "Short review rationale.",
        },
        private_tools=(),
    ),
)


def build_fellowship_subagents(
    *,
    repository: HotelRepository,
    llm: LLMAdapter,
    weather_provider: WeatherProvider,
    store: Any | None = None,
    agent_configs: AgentConfigRegistry,
) -> FellowshipSubagents:
    """Build the complete LOTR fellowship with each subagent's dependencies."""
    return FellowshipSubagents(
        aragorn=AragornAgent(llm, config=_agent_config(agent_configs, "aragorn")),
        samwise=SamwiseAgent(
            llm, config=_agent_config(agent_configs, "samwise"), store=store
        ),
        elrond=ElrondAgent(
            repository, llm, config=_agent_config(agent_configs, "elrond")
        ),
        bilbo=BilboAgent(llm, config=_agent_config(agent_configs, "bilbo")),
        faramir=FaramirAgent(llm, config=_agent_config(agent_configs, "faramir")),
        radagast=RadagastAgent(
            llm=llm,
            weather_provider=weather_provider,
            config=_agent_config(agent_configs, "radagast"),
        ),
    )


def _agent_config(registry: AgentConfigRegistry, agent_name: str) -> AgentConfig:
    return registry.require(agent_name)


def create_subagent_handles(
    *,
    aragorn: AragornAgent,
    samwise: SamwiseAgent,
    elrond: ElrondAgent,
    bilbo: BilboAgent,
    faramir: FaramirAgent,
    radagast: RadagastAgent,
) -> tuple[SubagentHandle, ...]:
    """Create pluggable handles for all LOTR subagents."""
    specs = {spec.name: spec for spec in SUBAGENT_SPECS}
    callables = _subagent_callables(
        aragorn=aragorn,
        samwise=samwise,
        elrond=elrond,
        bilbo=bilbo,
        faramir=faramir,
        radagast=radagast,
    )
    return tuple(
        FunctionSubagentHandle(
            name=spec.name,
            description=spec.description,
            input_schema=spec.input_schema,
            output_schema=spec.output_schema,
            private_tools=spec.private_tools,
            invoke_payload=callables[spec.name],
        )
        for spec in specs.values()
    )


def _subagent_callables(
    *,
    aragorn: AragornAgent,
    samwise: SamwiseAgent,
    elrond: ElrondAgent,
    bilbo: BilboAgent,
    faramir: FaramirAgent,
    radagast: RadagastAgent,
) -> dict[str, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]]:
    async def call_aragorn(payload: dict[str, Any]) -> dict[str, Any]:
        return await aragorn.check_query(str(payload.get("query", "")))

    async def call_samwise(payload: dict[str, Any]) -> dict[str, Any]:
        state = payload.get("state", {})
        if not isinstance(state, dict):
            state = {}
        query = str(state.get("query", "")).strip()
        user_id = state.get("user_id", "anonymous")
        thread_id = state.get("thread_id", "")
        display_name = state.get("display_name") or ""

        # Store display_name in the store before the AI agent runs so
        # load_user_preferences finds it immediately.
        if display_name and samwise.store is not None:
            namespace = (user_id, "preferences")
            key = "display_name"
            await samwise.store.aput(
                namespace,
                key,
                {"preference": display_name, "source": "login"},
            )

        if query and getattr(samwise, "agent", None) is not None:
            try:
                await samwise.agent.ainvoke(
                    {
                        "messages": [{"role": "user", "content": query}],
                        "user_id": user_id,
                        "thread_id": thread_id,
                    }
                )
            except Exception:
                pass

        context = await samwise.load_context(state)
        return context

    async def call_elrond(payload: dict[str, Any]) -> dict[str, Any]:
        return await elrond.analyze(str(payload.get("query", "")))

    async def call_radagast(payload: dict[str, Any]) -> dict[str, Any]:
        return await radagast.answer(
            str(payload.get("location", "")).strip(),
            query=payload.get("query"),
        )

    async def call_bilbo(payload: dict[str, Any]) -> dict[str, Any]:
        return await bilbo.write_answer(
            query=str(payload.get("query", "")),
            insights=list(payload.get("insights", [])),
            user_context=dict(payload.get("user_context", {})),
            compliance_status=dict(payload.get("compliance_status", {})),
            weather_context=dict(payload.get("weather_context", {})),
            evidence=dict(payload.get("evidence", {})),
            response_format=str(payload.get("response_format", "detailed")),
            reviewer_feedback=list(payload.get("reviewer_feedback", [])),
        )

    async def call_faramir(payload: dict[str, Any]) -> dict[str, Any]:
        return await faramir.review(
            query=str(payload.get("query", "")),
            final_answer=str(payload.get("final_answer", "")),
            insights=list(payload.get("insights", [])),
            user_context=dict(payload.get("user_context", {})),
            compliance_status=dict(payload.get("compliance_status", {})),
            weather_context=dict(payload.get("weather_context", {})),
        )

    return {
        "aragorn": call_aragorn,
        "samwise": call_samwise,
        "elrond": call_elrond,
        "radagast": call_radagast,
        "bilbo": call_bilbo,
        "faramir": call_faramir,
    }


def create_subagent_tools(
    *,
    subagents: Sequence[SubagentHandle] | None = None,
    aragorn: AragornAgent | None = None,
    samwise: SamwiseAgent | None = None,
    elrond: ElrondAgent | None = None,
    bilbo: BilboAgent | None = None,
    faramir: FaramirAgent | None = None,
    radagast: RadagastAgent | None = None,
) -> Sequence[StructuredTool]:
    """Create LangChain tools from already-wired LOTR subagents.

    Returns one discovery tool (list_agents) and one tool per subagent (call_agent_{name}).
    """
    handles = _resolve_handles(
        subagents=subagents,
        aragorn=aragorn,
        samwise=samwise,
        elrond=elrond,
        bilbo=bilbo,
        faramir=faramir,
        radagast=radagast,
    )
    handles_by_name = {handle.name: handle for handle in handles}

    async def list_agents(query: str = "") -> str:
        """List available subagents, optionally filtered by text query."""
        terms = query.lower().split()
        selected = handles
        if terms:
            selected = tuple(
                handle
                for handle in handles
                if all(
                    term in f"{handle.name} {handle.description}".lower()
                    for term in terms
                )
            )
        return json.dumps([_handle_to_dict(handle) for handle in selected])

    async def call_agent(agent_name: str, payload_json: str) -> Command:
        """Dispatch a request to one discovered subagent by name."""
        payload = _loads_object(payload_json)
        handle = handles_by_name.get(agent_name)
        if handle is None:
            result = {"error": f"unknown subagent: {agent_name}"}
            return _command(agent_name, result, {})
        result = await handle.invoke(payload)
        return _command(agent_name, result, _state_update(agent_name, result))

    return [
        StructuredTool.from_function(
            coroutine=list_agents,
            name="list_agents",
            description=(
                "Discover available LOTR subagents. Returns each agent name, "
                "responsibility, input schema, output schema, and private tools."
            ),
            tags=[_tool_tag("list_agents")],
            metadata={
                "tool_name": "list_agents",
                "langfuse_tags": [_tool_tag("list_agents")],
            },
        ),
        *[
            StructuredTool.from_function(
                coroutine=_make_call_agent_fn(handle, handles_by_name),
                name=f"call_agent_{handle.name}",
                description=(
                    f"Dispatch a request to the {handle.name} subagent. "
                    f"{handle.description}"
                ),
                tags=[_tool_tag(f"call_agent_{handle.name}")],
                metadata={
                    "tool_name": f"call_agent_{handle.name}",
                    "langfuse_tags": [_tool_tag(f"call_agent_{handle.name}")],
                },
            )
            for handle in handles
        ],
    ]


def _resolve_handles(
    *,
    subagents: Sequence[SubagentHandle] | None,
    aragorn: AragornAgent | None,
    samwise: SamwiseAgent | None,
    elrond: ElrondAgent | None,
    bilbo: BilboAgent | None,
    faramir: FaramirAgent | None,
    radagast: RadagastAgent | None,
) -> tuple[SubagentHandle, ...]:
    if subagents is not None:
        return tuple(subagents)
    if not all((aragorn, samwise, elrond, bilbo, faramir, radagast)):
        raise ValueError("create_subagent_tools requires subagents or all LOTR agents")
    assert aragorn is not None
    assert samwise is not None
    assert elrond is not None
    assert bilbo is not None
    assert faramir is not None
    assert radagast is not None
    return create_subagent_handles(
        aragorn=aragorn,
        samwise=samwise,
        elrond=elrond,
        bilbo=bilbo,
        faramir=faramir,
        radagast=radagast,
    )


def _tool_tag(tool_name: str) -> str:
    return f"{TOOL_TAG_PREFIX}{tool_name}"


def _make_call_agent_fn(
    handle: SubagentHandle,
    handles_by_name: dict[str, SubagentHandle],
) -> Callable[..., Awaitable[Command]]:
    """Create a callable that dispatches to one specific subagent."""

    async def _call(payload_json: str = "{}") -> Command:
        payload = _loads_object(payload_json)
        result = await handle.invoke(payload)
        return _command(handle.name, result, _state_update(handle.name, result))

    return _call


def _command(tool_name: str, result: dict[str, Any], update: dict[str, Any]) -> Command:
    return Command(update={"tool_results": {tool_name: result}, **update})


def _state_update(agent_name: str, result: dict[str, Any]) -> dict[str, Any]:
    update: dict[str, Any] = {
        "requires_approval": False,
        "requires_user_input": False,
        "approval_context": None,
        "user_input_context": None,
    }
    if "is_compliant" in result:
        update["compliance_status"] = result
    if "preferences" in result or "message_count" in result:
        update["user_context"] = result
    if "insights" in result:
        update["insights"] = result.get("insights", [])
    if {"text", "data", "meta"}.intersection(result):
        update["weather_context"] = (
            {} if result.get("needs_clarification", False) else result
        )
    if "final_answer" in result:
        update["final_answer"] = result.get("final_answer", "")
    if "approved" in result:
        update["review_status"] = result
    if result.get("needs_clarification", False):
        context = _clarification_context(agent_name, result)
        update["requires_approval"] = True
        update["requires_user_input"] = True
        update["approval_context"] = context
        update["user_input_context"] = context
    return update


def _clarification_context(
    agent_name: str, result: dict[str, Any]
) -> dict[str, Any] | None:
    if not result.get("needs_clarification", False):
        return None
    return {
        "agent": agent_name,
        "question": str(result.get("clarifying_question", "")),
        "options": _clarification_options(result),
        "reason": "additional_user_input_required",
    }


def _clarification_options(result: dict[str, Any]) -> list[str]:
    raw_options = result.get("answer_options", [])
    if not isinstance(raw_options, list):
        return []
    return [option for option in raw_options if isinstance(option, str) and option]


def _spec_to_dict(spec: SubagentSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "agent_name": spec.agent_name,
        "description": spec.description,
        "input_schema": spec.input_schema,
        "output_schema": spec.output_schema,
        "private_tools": list(spec.private_tools),
    }


def _handle_to_dict(handle: SubagentHandle) -> dict[str, Any]:
    return {
        "name": handle.name,
        "agent_name": handle.name,
        "description": handle.description,
        "input_schema": handle.input_schema,
        "output_schema": handle.output_schema,
        "private_tools": list(handle.private_tools),
    }


def _loads_object(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}
