# Multi-Agent Fellowship

The project uses the LangChain subagents pattern for chat orchestration.

Reference: https://docs.langchain.com/oss/python/langchain/multi-agent/subagents

## Runtime shape

```text
FastAPI router
  -> ChatService
  -> LangGraph state/checkpoint wrapper
  -> Gandalf supervisor AI agent
  -> specialist subagent tools
  -> final AgentState
```

LangGraph is still used for state, checkpointing, persistence, and streaming, but it no longer performs deterministic business fan-out. The only application graph node is `gandalf`.

```text
START -> gandalf -> END
```

## Agents

| Character | Runtime role |
|---|---|
| Gandalf | Supervisor AI agent. Coordinates the fellowship and delegates work. |
| Aragorn | Safety, policy, prompt-injection, and scope gate. Must run before data access. |
| Samwise | Memory keeper. Loads user preferences and conversation context. |
| Elrond | Hotel portfolio analyst. Uses read-only repository-backed data tools. |
| Bilbo | Final answer writer. Produces concise user-facing prose from approved evidence. |
| Faramir | Final reviewer. Checks groundedness, quality, and safety before return. |

## Normal request path

1. Gandalf receives the user question from `AgentState.query`.
2. Gandalf asks Aragorn whether the request is safe and in scope.
3. Gandalf asks Samwise for user context.
4. If Aragorn approves, Gandalf asks Elrond for hotel analytics.
5. Gandalf asks Bilbo to write the final answer.
6. Gandalf asks Faramir to review the answer.
7. Gandalf returns state updates including `final_answer`, `compliance_status`, `review_status`, `insights`, `user_context`, and `agent_transcript`.

## Blocked request path

If Aragorn returns `is_compliant=false`, Gandalf does not ask Elrond to access hotel data. Bilbo drafts a safe refusal and Faramir reviews that refusal.

## Implementation files

- `src/app/application/agents/gandalf.py`: concrete supervisor implementation and orchestration.
- `src/app/application/agents/protocols.py`: AI agent protocol consumed by graph assembly.
- `src/app/application/agents/aragorn.py`: pre-flight compliance subagent.
- `src/app/application/agents/samwise.py`: memory/context subagent.
- `src/app/application/agents/elrond.py`: hotel analysis subagent.
- `src/app/application/agents/bilbo.py`: final answer writer subagent.
- `src/app/application/agents/faramir.py`: final reviewer subagent.
- `src/app/application/agents/tools.py`: LangChain tool wrappers for specialists.
- `src/app/application/agents/identities.py`: stable character names, roles, and progress labels.
- `src/app/application/graph.py`: LangGraph wrapper around an injected `AIAgent` supervisor. Runtime bootstrap currently injects Gandalf and names the compiled node `gandalf` for observability/backward compatibility.

## Boundaries

- Application agents depend on domain ports, not infrastructure implementations.
- Repository access remains behind `HotelRepository`.
- LLM calls remain behind `LLMAdapter`.
- Settings and real provider clients are constructed once in bootstrap.
- No production mock/fallback mode is introduced.
