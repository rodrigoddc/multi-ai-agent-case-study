"""Gandalf — AI supervisor agent for the hotel insights fellowship."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langgraph.store.base import BaseStore
from langgraph.types import Command

from src.app.application.agents.base import PortBackedChatModel, parse_json_object
from src.app.application.agents.config import AgentConfig
from src.app.application.agents.identities import AGENT_IDENTITIES, AgentName
from src.app.application.progress import emit_progress
from src.app.application.ports import LLMAdapter

SAFE_FAILURE_ANSWER = (
    "I cannot provide a reliable answer because the supervisor did not return "
    "a valid fellowship plan."
)


@dataclass(frozen=True, slots=True)
class SupervisorPlan:
    """Model-selected intent, delegation plan, and answer format."""

    intent: str
    agent_plan: list[str]
    response_format: str
    agent_specs: list[dict[str, Any]] | None = None


class GandalfAgent:
    """AI supervisor that delegates to LOTR specialist subagents."""

    def __init__(
        self,
        *,
        llm: LLMAdapter,
        store: BaseStore | None = None,
        tools: list | None = None,
        config: AgentConfig,
    ) -> None:
        self.llm = llm
        self.store = store
        self.config = config
        self.system_prompt = config.prompt
        self.temperature = config.llm.temperature
        self.model_name = config.llm.model
        self.provider = config.llm.provider
        if config.plan_prompt is None:
            raise ValueError("Gandalf plan_prompt is required in agent config")
        self.plan_prompt = config.plan_prompt
        # Tools are provided by the bootstrap code. Gandalf should not know about
        # providers or how tools are constructed — it only consumes a list of tools.
        self.tools = list(tools or [])

        self.agent = create_agent(
            model=PortBackedChatModel(
                llm=llm,
                system_prompt=self.system_prompt,
                temperature=self.temperature,
                model_name=self.model_name,
                provider=self.provider,
                name=self.model_name,
            ),
            tools=list(self.tools),
            system_prompt=self.system_prompt,
            name=AgentName.GANDALF.value,
        )
        self.tools_by_name = {tool.name: tool for tool in self.tools}

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run the supervisor workflow and return LangGraph state updates."""
        query = _query_with_feedback(state)
        emit_progress(AGENT_IDENTITIES[AgentName.GANDALF].progress_label)
        supervisor_plan = await self._build_supervisor_plan(query)
        if supervisor_plan.intent == "capability":
            return await self._answer_capability_question(
                query, specs=supervisor_plan.agent_specs
            )

        agent_plan = supervisor_plan.agent_plan
        if not agent_plan:
            return _safe_supervisor_failure_update()

        result = await self._execute_tool_plan(
            agent_plan=agent_plan,
            query=query,
            state=state,
            response_format=supervisor_plan.response_format,
        )
        final_answer = result["final_answer"]
        review_status = result["review_status"]

        if not review_status.get("approved", False) and not result.get(
            "requires_approval", False
        ):
            final_answer = _safe_review_failure_answer(review_status)

        return {
            "active_agent": AgentName.GANDALF.value,
            "agent_transcript": result["transcript"],
            "tool_results": _tool_results(
                compliance_status=result["compliance_status"],
                user_context=result["user_context"],
                weather_context=result["weather_context"],
                insights=result["insights"],
                final_answer=final_answer,
                review_status=review_status,
            ),
            "route_decision": AgentName.GANDALF.value,
            "compliance_status": result["compliance_status"],
            "user_context": result["user_context"],
            "weather_context": result["weather_context"],
            "insights": result["insights"],
            "final_answer": final_answer,
            "review_status": review_status,
            "requires_approval": bool(result.get("requires_approval", False)),
            "requires_user_input": bool(result.get("requires_user_input", False)),
            "approval_context": result.get("approval_context"),
            "user_input_context": result.get("user_input_context"),
            "reasoning_trace": "Gandalf delegated to the LOTR hotel insights fellowship.",
        }

    async def _answer_capability_question(
        self, query: str, specs: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Explain system capabilities from discovered subagent specs."""
        specs = specs if specs is not None else await self._list_agent_specs(query="")
        compliance_status = {
            "is_compliant": True,
            "violations": [],
            "warnings": [],
            "reasoning": "Capability/help request; no hotel data access required.",
        }
        insights = _capability_context(specs)
        transcript: list[dict[str, Any]] = [
            {"agent": AgentName.GANDALF.value, "output": {"capabilities": specs}}
        ]

        emit_progress(AGENT_IDENTITIES[AgentName.BILBO].progress_label)
        draft = await self._ask_bilbo(
            query=query,
            insights=insights,
            user_context={},
            compliance_status=compliance_status,
            weather_context={},
            response_format="capability",
        )
        final_answer = str(draft.get("final_answer", ""))
        transcript.append({"agent": AgentName.BILBO.value, "output": draft})

        emit_progress(AGENT_IDENTITIES[AgentName.FARAMIR].progress_label)
        review_status = await self._ask_faramir(
            query=query,
            final_answer=final_answer,
            insights=insights,
            user_context={},
            compliance_status=compliance_status,
            weather_context={},
        )
        transcript.append({"agent": AgentName.FARAMIR.value, "output": review_status})

        revision_count = 0
        while (
            not review_status.get("approved", False)
            and review_status.get("required_changes")
            and revision_count < 2
        ):
            revision_count += 1
            emit_progress(AGENT_IDENTITIES[AgentName.BILBO].progress_label)
            draft = await self._ask_bilbo(
                query=query,
                insights=insights,
                user_context={},
                compliance_status=compliance_status,
                weather_context={},
                response_format="capability",
                reviewer_feedback=[
                    str(item) for item in review_status.get("required_changes", [])
                ],
            )
            final_answer = str(draft.get("final_answer", ""))
            transcript.append({"agent": AgentName.BILBO.value, "output": draft})
            emit_progress(AGENT_IDENTITIES[AgentName.FARAMIR].progress_label)
            review_status = await self._ask_faramir(
                query=query,
                final_answer=final_answer,
                insights=insights,
                user_context={},
                compliance_status=compliance_status,
                weather_context={},
            )
            transcript.append(
                {"agent": AgentName.FARAMIR.value, "output": review_status}
            )

        if not review_status.get("approved", False):
            final_answer = _safe_review_failure_answer(review_status)

        return {
            "active_agent": AgentName.GANDALF.value,
            "agent_transcript": transcript,
            "tool_results": {
                "list_agents": specs,
                "bilbo": {"final_answer": final_answer},
                "faramir": review_status,
            },
            "route_decision": AgentName.GANDALF.value,
            "compliance_status": compliance_status,
            "user_context": {},
            "weather_context": {},
            "insights": insights,
            "final_answer": final_answer,
            "review_status": review_status,
            "requires_approval": False,
            "requires_user_input": False,
            "approval_context": None,
            "user_input_context": None,
            "reasoning_trace": "Gandalf answered a system-capability question without exposing internal agent names.",
        }

    async def _build_supervisor_plan(self, query: str) -> SupervisorPlan:
        """Ask Gandalf for the next discovered subagent plan."""
        specs = await self._list_agent_specs()
        if not specs:
            return _invalid_supervisor_plan()
        content = self.plan_prompt.format(
            query=query,
            agent_specs=json.dumps(specs, indent=2),
        )
        result = await self.agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    }
                ]
            }
        )
        messages = result.get("messages", []) if isinstance(result, dict) else []
        if not messages:
            return _invalid_supervisor_plan()
        content = str(getattr(messages[-1], "content", ""))
        parsed = _parse_plan_json(content)
        if not isinstance(parsed, dict):
            return _invalid_supervisor_plan()
        intent = _plan_intent(parsed)
        response_format = _plan_response_format(parsed, intent=intent)
        if intent == "capability":
            return SupervisorPlan(
                intent=intent,
                agent_plan=[],
                response_format=response_format,
                agent_specs=specs,
            )
        raw_plan = parsed.get("agent_plan")
        if not isinstance(raw_plan, list):
            return _invalid_supervisor_plan()
        allowed = {str(spec.get("agent_name", "")) for spec in specs}
        agent_plan = [
            item for item in raw_plan if isinstance(item, str) and item in allowed
        ]
        if not agent_plan or agent_plan[0] != "aragorn":
            return _invalid_supervisor_plan()
        if any(
            required_agent not in agent_plan
            for required_agent in _required_agents_for_intent(intent)
        ):
            return _invalid_supervisor_plan()
        return SupervisorPlan(
            intent=intent,
            agent_plan=agent_plan,
            response_format=response_format,
            agent_specs=specs,
        )

    async def _execute_tool_plan(
        self,
        *,
        agent_plan: list[str],
        query: str,
        state: dict[str, Any],
        response_format: str,
    ) -> dict[str, Any]:
        """Execute a validated supervisor-selected subagent plan generically."""
        context = _empty_execution_context()

        for agent_name in agent_plan:
            if _should_skip_agent(agent_name=agent_name, context=context):
                continue
            emit_progress(_progress_label(agent_name))
            result = await self._call_agent(
                agent_name,
                _payload_for_agent(
                    agent_name=agent_name,
                    query=query,
                    state=state,
                    response_format=response_format,
                    context=context,
                ),
            )
            context = _apply_agent_result(
                context=context,
                agent_name=agent_name,
                result=result,
            )
            if context["requires_approval"]:
                break

        if context["requires_approval"]:
            return _clarification_execution_result(context)

        if not context["final_answer"]:
            emit_progress(AGENT_IDENTITIES[AgentName.BILBO].progress_label)
            draft = await self._ask_bilbo(
                query=query,
                insights=context["insights"],
                evidence=context["analysis_evidence"],
                user_context=context["user_context"],
                compliance_status=context["compliance_status"],
                weather_context=context["weather_context"],
                response_format=response_format,
            )
            context = _apply_agent_result(
                context=context, agent_name=AgentName.BILBO.value, result=draft
            )

        if not context["review_status"]:
            emit_progress(AGENT_IDENTITIES[AgentName.FARAMIR].progress_label)
            review = await self._ask_faramir(
                query=query,
                final_answer=context["final_answer"],
                insights=context["insights"],
                user_context=context["user_context"],
                compliance_status=context["compliance_status"],
                weather_context=context["weather_context"],
            )
            context = _apply_agent_result(
                context=context, agent_name=AgentName.FARAMIR.value, result=review
            )

        revision_count = 0
        while (
            not context["review_status"].get("approved", False)
            and context["review_status"].get("required_changes")
            and revision_count < 2
        ):
            revision_count += 1
            reviewer_feedback = [
                str(item)
                for item in context["review_status"].get("required_changes", [])
            ]
            emit_progress(AGENT_IDENTITIES[AgentName.BILBO].progress_label)
            draft = await self._ask_bilbo(
                query=query,
                insights=context["insights"],
                evidence=context["analysis_evidence"],
                user_context=context["user_context"],
                compliance_status=context["compliance_status"],
                weather_context=context["weather_context"],
                response_format=response_format,
                reviewer_feedback=reviewer_feedback,
            )
            context = _apply_agent_result(
                context=context, agent_name=AgentName.BILBO.value, result=draft
            )
            emit_progress(AGENT_IDENTITIES[AgentName.FARAMIR].progress_label)
            review = await self._ask_faramir(
                query=query,
                final_answer=context["final_answer"],
                insights=context["insights"],
                user_context=context["user_context"],
                compliance_status=context["compliance_status"],
                weather_context=context["weather_context"],
            )
            context = _apply_agent_result(
                context=context, agent_name=AgentName.FARAMIR.value, result=review
            )

        return _execution_result(context)

    async def _ask_bilbo(
        self,
        *,
        query: str,
        insights: list[str],
        user_context: dict[str, Any],
        compliance_status: dict[str, Any],
        weather_context: dict[str, Any],
        response_format: str,
        evidence: dict[str, Any] | None = None,
        reviewer_feedback: list[str] | None = None,
    ) -> dict[str, Any]:
        return await self._call_agent(
            "bilbo",
            {
                "query": query,
                "insights": insights,
                "evidence": evidence or {},
                "user_context": user_context,
                "compliance_status": compliance_status,
                "weather_context": weather_context,
                "response_format": response_format,
                "reviewer_feedback": reviewer_feedback or [],
            },
        )

    async def _ask_faramir(
        self,
        *,
        query: str,
        final_answer: str,
        insights: list[str],
        user_context: dict[str, Any],
        compliance_status: dict[str, Any],
        weather_context: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._call_agent(
            "faramir",
            {
                "query": query,
                "final_answer": final_answer,
                "insights": insights,
                "user_context": user_context,
                "compliance_status": compliance_status,
                "weather_context": weather_context,
            },
        )

    async def _ask_radagast(self, *, query: str) -> dict[str, Any]:
        return await self._call_agent(
            "radagast",
            {
                "location": "",
                "query": query,
            },
        )

    async def _list_agent_specs(self, query: str = "") -> list[dict[str, Any]]:
        """Discover available subagents through the registry tool."""
        raw = await self.tools_by_name["list_agents"].ainvoke({"query": query})
        if not isinstance(raw, str):
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, dict)]

    async def _call_agent(
        self, agent_name: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Call a discovered specialist subagent through the dispatch tool."""
        tool_key = f"call_agent_{agent_name}"
        tool = self.tools_by_name.get(tool_key)
        if tool is None:
            return {}
        raw = await tool.ainvoke({"payload_json": json.dumps(payload, default=str)})
        if isinstance(raw, Command):
            update = raw.update if isinstance(raw.update, dict) else {}
            tool_results = update.get("tool_results", {})
            result = tool_results.get(agent_name, {})
            return result if isinstance(result, dict) else {}
        if not isinstance(raw, str):
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}


def _parse_plan_json(raw: str) -> dict[str, Any]:
    """Parse Gandalf planner JSON from strict or fenced model output."""
    parsed = parse_json_object(raw.strip(), fallback={})
    if parsed:
        return parsed

    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = [
            line for line in stripped.splitlines() if not line.strip().startswith("```")
        ]
        parsed = parse_json_object("\n".join(lines).strip(), fallback={})
        if parsed:
            return parsed

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end <= start:
        return {}
    return parse_json_object(stripped[start : end + 1], fallback={})


def _empty_execution_context() -> dict[str, Any]:
    return {
        "transcript": [],
        "compliance_status": {},
        "user_context": {},
        "weather_context": {},
        "insights": [],
        "analysis_evidence": {},
        "final_answer": "",
        "review_status": {},
        "requires_approval": False,
        "approval_context": None,
    }


def _should_skip_agent(*, agent_name: str, context: dict[str, Any]) -> bool:
    protected_agents = {AgentName.ELROND.value, AgentName.RADAGAST.value}
    return agent_name in protected_agents and not context["compliance_status"].get(
        "is_compliant", False
    )


def _progress_label(agent_name: str) -> str:
    try:
        return AGENT_IDENTITIES[AgentName(agent_name)].progress_label
    except ValueError:
        return f"{agent_name} is working"


def _payload_for_agent(
    *,
    agent_name: str,
    query: str,
    state: dict[str, Any],
    response_format: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    payloads = {
        AgentName.ARAGORN.value: {"query": query},
        AgentName.SAMWISE.value: {"state": state},
        AgentName.ELROND.value: {"query": query},
        AgentName.RADAGAST.value: {"location": "", "query": query},
        AgentName.BILBO.value: {
            "query": query,
            "insights": context["insights"],
            "evidence": context["analysis_evidence"],
            "user_context": context["user_context"],
            "compliance_status": context["compliance_status"],
            "weather_context": context["weather_context"],
            "response_format": response_format,
            "reviewer_feedback": [],
        },
        AgentName.FARAMIR.value: {
            "query": query,
            "final_answer": context["final_answer"],
            "insights": context["insights"],
            "user_context": context["user_context"],
            "compliance_status": context["compliance_status"],
            "weather_context": context["weather_context"],
        },
    }
    return payloads.get(agent_name, {"query": query})


def _apply_agent_result(
    *, context: dict[str, Any], agent_name: str, result: dict[str, Any]
) -> dict[str, Any]:
    updated = {**context}
    transcript = list(updated["transcript"])
    transcript.append({"agent": agent_name, "output": result})
    updated["transcript"] = transcript

    if "is_compliant" in result:
        updated["compliance_status"] = result
    if "preferences" in result or "message_count" in result:
        updated["user_context"] = result
    if "insights" in result:
        updated["insights"] = [str(item) for item in result.get("insights", [])]
        updated["analysis_evidence"] = result
    if {"text", "data", "meta"}.intersection(result):
        updated["weather_context"] = (
            {} if result.get("needs_clarification", False) else result
        )
    if "final_answer" in result:
        updated["final_answer"] = str(result.get("final_answer", ""))
    if "approved" in result:
        updated["review_status"] = result

    clarification_context = _specialist_clarification_context(agent_name, result)
    if clarification_context is not None:
        updated["requires_approval"] = True
        updated["approval_context"] = clarification_context
    return updated


def _clarification_execution_result(context: dict[str, Any]) -> dict[str, Any]:
    question = str(
        (context.get("approval_context") or {}).get(
            "question", "I need more information before answering."
        )
    )
    return {
        "transcript": context["transcript"],
        "compliance_status": context["compliance_status"],
        "user_context": context["user_context"],
        "weather_context": context["weather_context"],
        "insights": context["insights"],
        "final_answer": question,
        "review_status": {
            "approved": True,
            "warnings": [],
            "required_changes": [],
            "reasoning": "A specialist agent requested more user input via LangGraph interrupt.",
        },
        "requires_approval": True,
        "requires_user_input": True,
        "approval_context": context["approval_context"],
        "user_input_context": context["approval_context"],
    }


def _execution_result(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "transcript": context["transcript"],
        "compliance_status": context["compliance_status"],
        "user_context": context["user_context"],
        "weather_context": context["weather_context"],
        "insights": context["insights"],
        "final_answer": context["final_answer"],
        "review_status": context["review_status"],
        "requires_approval": False,
        "requires_user_input": False,
        "approval_context": None,
        "user_input_context": None,
    }


def _tool_results(
    *,
    compliance_status: dict,
    user_context: dict,
    weather_context: dict,
    insights: list[str],
    final_answer: str,
    review_status: dict,
) -> dict[str, Any]:
    return {
        "aragorn": compliance_status,
        "samwise": user_context,
        "elrond": {"insights": insights},
        "radagast": weather_context,
        "bilbo": {"final_answer": final_answer},
        "faramir": review_status,
    }


def _safe_review_failure_answer(review_status: dict[str, Any]) -> str:
    changes = review_status.get("required_changes", [])
    if not changes:
        return "I cannot provide a reliable answer yet because the final review failed."
    return "I cannot provide a reliable answer yet: " + json.dumps(changes)


def _invalid_supervisor_plan() -> SupervisorPlan:
    return SupervisorPlan(intent="invalid", agent_plan=[], response_format="detailed")


def _plan_intent(parsed: dict[str, Any]) -> str:
    raw_intent = parsed.get("intent", "workflow")
    if not isinstance(raw_intent, str):
        return "workflow"
    intent = raw_intent.strip().lower()
    allowed = {
        "capability",
        "hotel_analytics",
        "weather",
        "mixed",
        "general",
        "workflow",
    }
    return intent if intent in allowed else "workflow"


def _plan_response_format(parsed: dict[str, Any], *, intent: str) -> str:
    raw_format = parsed.get("response_format")
    allowed = {"short_simple", "detailed", "insight_report", "capability"}
    if isinstance(raw_format, str) and raw_format in allowed:
        return raw_format
    defaults = {
        "capability": "capability",
        "hotel_analytics": "insight_report",
        "mixed": "insight_report",
    }
    return defaults.get(intent, "detailed")


def _capability_context(specs: list[dict[str, Any]]) -> list[str]:
    return [
        json.dumps(
            {
                "task": (
                    "Answer the user's capability or follow-up exploration question "
                    "using only user-facing hotel insight capabilities. Describe what "
                    "the user can ask next. Do not describe internal workflow such as "
                    "safety checks, memory loading, answer drafting, review, agents, "
                    "or private tools."
                ),
                "public_capabilities": [
                    {
                        "description": spec.get("description", ""),
                    }
                    for spec in _user_facing_capability_specs(specs)
                ],
            },
            default=str,
            sort_keys=True,
        )
    ]


def _user_facing_capability_specs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    user_facing_output_keys = {"insights", "text", "data"}
    user_facing_specs: list[dict[str, Any]] = []
    for spec in specs:
        output_schema = spec.get("output_schema", {})
        if not isinstance(output_schema, dict):
            continue
        if user_facing_output_keys.intersection(output_schema):
            user_facing_specs.append(spec)
    return user_facing_specs


def _required_agents_for_intent(intent: str) -> tuple[str, ...]:
    return {
        "hotel_analytics": ("elrond",),
        "weather": ("radagast",),
        "mixed": ("elrond", "radagast"),
    }.get(intent, ())


def _specialist_clarification_context(
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


def _safe_supervisor_failure_update() -> dict[str, Any]:
    review_status = {
        "approved": False,
        "warnings": [],
        "required_changes": ["Gandalf must return a valid fellowship agent plan."],
        "reasoning": "The supervisor plan was missing or invalid.",
    }
    return {
        "active_agent": AgentName.GANDALF.value,
        "agent_transcript": [
            {
                "agent": AgentName.GANDALF.value,
                "output": {"error": "No valid fellowship plan generated"},
            }
        ],
        "tool_results": {"plan": []},
        "route_decision": AgentName.GANDALF.value,
        "compliance_status": {
            "is_compliant": False,
            "violations": ["Invalid supervisor plan"],
            "warnings": [],
            "reasoning": "No data tools were called because Gandalf did not plan safely.",
        },
        "user_context": {},
        "weather_context": {},
        "insights": [],
        "final_answer": SAFE_FAILURE_ANSWER,
        "review_status": review_status,
        "requires_approval": False,
        "approval_context": None,
        "reasoning_trace": "Gandalf failed closed before delegating to subagents.",
    }


def _clarification_options(result: dict[str, Any]) -> list[str]:
    raw_options = result.get("answer_options", [])
    if not isinstance(raw_options, list):
        return []
    return [option for option in raw_options if isinstance(option, str) and option]


def _query_with_feedback(state: dict[str, Any]) -> str:
    """Extract the query, preserving any interrupt resume clarification."""
    query = str(state.get("query", ""))
    feedback = state.get("user_feedback")
    if isinstance(feedback, str) and feedback.strip():
        return _append_user_feedback(query=query, feedback=feedback)

    approval_context = state.get("approval_context")
    if isinstance(approval_context, dict):
        context_feedback = approval_context.get("user_feedback")
        if isinstance(context_feedback, str) and context_feedback.strip():
            return _append_user_feedback(query=query, feedback=context_feedback)

    return query


def _append_user_feedback(*, query: str, feedback: str) -> str:
    clean_query = query.strip()
    clean_feedback = feedback.strip()
    if not clean_query:
        return clean_feedback
    if clean_feedback in clean_query:
        return clean_query
    return f"{clean_query}\n\nUser clarification: {clean_feedback}"
