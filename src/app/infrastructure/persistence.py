"""PostgreSQL persistence for LangGraph checkpoints and store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore

from src.app.infrastructure.config import DatabaseSettings


@dataclass(slots=True)
class LangGraphPersistence:
    """Owns LangGraph persistence resources and their context managers."""

    checkpointer: Any
    store: Any
    checkpointer_context: Any
    store_context: Any

    async def close(self) -> None:
        """Close persistence resources in reverse creation order."""
        await self.store_context.__aexit__(None, None, None)
        await self.checkpointer_context.__aexit__(None, None, None)


async def create_persistence(settings: DatabaseSettings) -> LangGraphPersistence:
    """Create and initialize LangGraph persistence resources."""
    dsn = settings.psycopg_url()
    checkpointer_context = AsyncPostgresSaver.from_conn_string(dsn)
    checkpointer = await checkpointer_context.__aenter__()
    await checkpointer.setup()

    store_context = AsyncPostgresStore.from_conn_string(dsn)
    store = await store_context.__aenter__()
    await store.setup()

    return LangGraphPersistence(
        checkpointer=checkpointer,
        store=store,
        checkpointer_context=checkpointer_context,
        store_context=store_context,
    )
