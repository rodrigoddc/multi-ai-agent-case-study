# Architecture

The app uses Hexagonal Architecture with a FastAPI composition root.

## Layers

- Domain: pure models and protocol ports in `src/app/domain`.
- `src/app/application`: use cases, application services, LangGraph state, and LangChain subagents.
- `src/app/infrastructure`: PostgreSQL, SQLAlchemy, OpenRouter, LangGraph persistence, Langfuse, and config adapters.
- `src/app/bootstrap`: strategy, typed container, and lifespan lifecycle in `src/app/bootstrap`.
- `src/app/routers`: HTTP adapters in `src/app/routers`.

## Multi-agent runtime

The chat path is intentionally modeled as a LangChain subagent system, not a deterministic fan-out graph.

```text
START -> gandalf -> END
```

`Gandalf` is the supervisor AI agent. He coordinates a fixed fellowship of specialist agents exposed through LangChain tools:

| Agent | Responsibility |
|---|---|
| Gandalf | Supervises the workflow and decides which companion acts. |
| Aragorn | Checks request safety, policy, prompt injection, and domain scope before data access. |
| Samwise | Loads user preferences and conversation context from the injected LangGraph store. |
| Elrond | Analyzes read-only hotel portfolio data through the `HotelRepository` port. |
| Bilbo | Turns approved evidence into the final user-facing answer. |
| Faramir | Reviews the drafted answer for groundedness, quality, and safety. |

The specialist tools are created in `src/app/application/agents/tools.py` and follow the LangChain subagents pattern: each specialist is created as a LangChain agent and wrapped as an `ask_<character>` tool for Gandalf.

The graph keeps persistence, checkpointing, state reducers, and SSE streaming boundaries. It does not make business routing decisions itself.

## Startup lifecycle

1. `create_app()` resolves the selected environment strategy.
2. FastAPI lifespan calls `build_container(strategy)`.
3. Settings are loaded once into `AppSettings`.
4. Database engine, session maker, repositories, LLM adapter, graph persistence, graph, and services are created once.
5. The app stores one typed container at `app.state.container`.
6. Routers resolve dependencies from the container.
7. Shutdown closes persistence resources and the SQLAlchemy engine.

## Environment strategies

Strategies control behavior that differs across environments:

- `local`: local development, static UI enabled, auto-create tables enabled.
- `test`: no DB persistence or table creation; tests may inject an empty lifespan/container.
- `dev`: integration environment with persistence.
- `prod`: persistence enabled and schema changes disabled.

## Dependency rule

Routers do not instantiate settings, repositories, LLM adapters, SQLAlchemy sessions, or LangGraph resources. Application services depend on domain ports or constructor-injected adapters. Infrastructure depends inward on domain/application contracts.
