FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

RUN apt-get update \
        && apt-get install -y --no-install-recommends gcc libc6-dev python3-dev libpq-dev \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

COPY src/ src/
COPY evaluators/ evaluators/
COPY evals/*.py evals/
COPY evals/datasets/ evals/datasets/

CMD ["uv", "run", "python", "src/jobs/seed_hotels.py"]
