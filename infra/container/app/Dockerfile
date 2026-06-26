FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

RUN apt-get update \
        && apt-get install -y --no-install-recommends gcc libc6-dev python3-dev libpq-dev \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY uv.lock .
RUN uv sync --no-dev --frozen

COPY src/ src/
COPY config/ config/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
