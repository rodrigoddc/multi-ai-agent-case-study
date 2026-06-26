# Development

## Commands

```bash
uv sync --dev
uv run ruff format .
uv run ruff check --fix .
uv run pytest
uv run pytest --cov=src
```

## TDD workflow

For each bug or behavior change:

1. Write a focused pytest that reproduces the problem.
2. Run the test and confirm it fails for the expected reason.
3. Implement the smallest production change that makes the test pass.
4. Run the targeted test.
5. Run the full suite and ruff.

## Test layout

Tests mirror source structure under `tests/app`.

Examples:

- `src/app/application/services/sse_chat_service.py`
- `tests/app/application/test_sse_chat_service.py`

## Frontend structure

The HTMX UI is intentionally split:

- `templates/layouts/base.html`: global shell and assets only.
- `templates/pages/home.html`: page composition.
- `templates/partials/header.html`: reusable header.
- `templates/sections/chat.html`: chat UI.
- `templates/sections/insights.html`: insights report UI.
- `static/css/app.css`: non-trivial CSS.

Keep Python routers free of inline HTML.
