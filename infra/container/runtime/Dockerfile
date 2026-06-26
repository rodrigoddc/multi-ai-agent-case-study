FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

RUN apt-get update \
        && apt-get install -y --no-install-recommends gcc libc6-dev python3-dev libpq-dev \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY uv.lock .
RUN uv sync --frozen --group dev

COPY src/ src/
COPY config/ config/

ENTRYPOINT ["sleep", "infinity"]
