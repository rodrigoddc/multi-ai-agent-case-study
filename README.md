# Hotel Insights Multi-Agent API

FastAPI application for hotel portfolio analysis using a LangGraph multi-agent workflow, OpenRouter-hosted LLMs, optional Langfuse observability, PostgreSQL persistence, Docker Compose, and Kubernetes manifests.

The app answers operational questions about hotel performance, guest sentiment, revenue, and portfolio trends through JSON endpoints, an HTMX UI, and SSE chat streaming.

## Current architecture

The project follows Hexagonal / Ports and Adapters boundaries:

- `src/app/domain`: domain models and protocol ports.
- `src/app/application`: use cases, application services, LangGraph state, and agents.
- `src/app/infrastructure`: SQLAlchemy, PostgreSQL, OpenRouter, LangGraph persistence, config, logging, and external adapters.
- `src/app/bootstrap`: app factory strategy resolution, typed container, and resource lifecycle.
- `src/app/routers`: HTTP adapters only. Routers delegate to application services.
- `src/app/templates` and `src/app/static`: HTMX/Jinja UI and static assets.

Runtime dependencies are created once during FastAPI startup. Request handlers use the typed `ApplicationContainer` instead of constructing settings, database clients, repositories, LLM clients, or graphs per request.

## Main capabilities

- Hotel and review read endpoints.
- Aggregated hotel metrics.
- Natural language insight queries through a Gandalf-led LangChain subagent fellowship.
- Streaming chat over SSE using LangGraph stream API v2.
- HTMX frontend for chat and portfolio reports.
- PostgreSQL persistence for SQLAlchemy data and LangGraph checkpoint/store resources.
- Environment strategies for `local`, `test`, `dev`, and `prod`.

## Multi-agent fellowship

The chat workflow is a real LangChain subagents architecture wrapped by LangGraph persistence:

- `Gandalf`: AI supervisor agent. Coordinates the request and delegates to specialist companions.
- `Aragorn`: pre-flight safety, policy, prompt-injection, and scope checker.
- `Samwise`: user preference and conversation context keeper.
- `Elrond`: read-only hotel portfolio analyst using repository-backed data tools.
- `Bilbo`: final answer writer.
- `Faramir`: final groundedness, quality, and safety reviewer.

LangGraph now runs `START -> gandalf -> END`. Gandalf is the only graph supervisor node. Specialists are hidden behind LangChain tool-based discovery: `list_agents` exposes subagent specs and `call_agent` dispatches to the chosen subagent. The graph never wires Radagast, Elrond, or other subagents directly.

## Project structure

```text
src/app/
├── main.py                         # FastAPI app factory
├── bootstrap/
│   ├── container.py                # Typed runtime container
│   ├── lifespan.py                 # Startup/shutdown orchestration
│   └── strategy.py                 # local/test/dev/prod policies
├── domain/
│   ├── models.py                   # Domain models
│   └── ports.py                    # Protocol interfaces
├── application/
│   ├── agents/                     # LangGraph agent implementations
│   ├── services/                   # Application use cases
│   ├── agent_state.py              # AgentState TypedDict + factory
│   ├── dependencies.py             # FastAPI dependency providers
│   └── graph.py                    # Graph builder
├── infrastructure/
│   ├── adapters/                   # OpenRouter adapter
│   ├── repositories/               # SQLAlchemy repositories
│   ├── config.py                   # Pydantic settings aggregate
│   ├── database.py                 # SQLAlchemy engine/session factories
│   ├── observability.py            # Langfuse support
│   ├── orm_models.py               # ORM models
│   └── persistence.py              # LangGraph checkpoint/store lifecycle
├── routers/                        # HTTP adapters
├── templates/
│   ├── layouts/base.html
│   ├── pages/home.html
│   ├── partials/header.html
│   └── sections/{chat,insights}.html
└── static/
    └── css/app.css
```

## Configuration

Settings are loaded once at startup through `AppSettings`. Secrets are mandatory and fail fast.

Required variables:

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER_API_KEY` | LLM provider API key (generic: OpenRouter, Anthropic, etc.) |
| `POSTGRES_PASSWORD` | PostgreSQL password |

Common optional variables:

| Variable | Default |
|---|---|
| `APP_ENV` | `local` |
| `LLM_PROVIDER_MODEL` | e.g. `openrouter/free` |
| `POSTGRES_USER` | `hoteluser` |
| `POSTGRES_DB` | `hotelsdb` |
| `DB_HOST` | `localhost` |
| `DB_PORT` | `5432` |
| `LANGFUSE_ENABLED` | `false` |

Environment behavior is controlled by strategy classes:

| Environment | Auto-create tables | Persistence | Static UI |
|---|---:|---:|---:|
| `local` | yes | yes | yes |
| `test` | no | no | yes |
| `dev` | yes | yes | yes |
| `prod` | no | yes | yes |

## Development

Install/sync dependencies:

```bash
uv sync --dev
```

Run tests:

```bash
uv run pytest
uv run pytest tests/app/application/test_sse_chat_service.py -v
```

Run formatting and linting:

```bash
uv run ruff format .
uv run ruff check --fix .
```

Run coverage:

```bash
uv run pytest --cov=src
```

## Local Docker Compose

```bash
docker compose -f infra/container/docker-compose.yml up --build
```

Then open:

- UI: `http://localhost:8000/`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Kubernetes

Kubernetes manifests live under `infra/k8s`. The deployment expects real secrets and production-safe configuration.

Typical local Kind flow:

```bash
KIND_EXPERIMENTAL_PROVIDER=podman kind create cluster --config infra/k8s/cluster/kind-cluster.yml
kubectl apply -f infra/k8s/cluster/namespace.yml
kubectl apply -f infra/k8s/
kubectl port-forward svc/fastapi-svc 8000:8000 -n hotel-insights
```

Do not commit real credentials into manifests or `.env` files.

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/hotels` | List hotels |
| `GET` | `/reviews` | List reviews |
| `GET` | `/insights/summary` | Aggregate metrics |
| `GET` | `/insights/query` | Non-streaming graph query |
| `POST` | `/insights/chat` | HTMX chat initiation fragment |
| `GET` | `/insights/chat/stream` | SSE response stream |
