"""Database engine and session management — infrastructure adapter."""

from __future__ import annotations


from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.app.infrastructure.config import DatabaseSettings
from src.app.infrastructure.orm_models import Base


def create_engine(settings: DatabaseSettings):
    """Create a new async SQLAlchemy engine from typed settings."""
    url = settings.sqlalchemy_url()
    return create_async_engine(
        url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
    )


def create_session_maker(engine):
    """Create a new async session factory."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_tables(engine):
    """Create all configured ORM tables if they do not already exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
