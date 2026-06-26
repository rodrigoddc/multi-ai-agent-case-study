from pydantic import SecretStr

from src.app.infrastructure.config import DatabaseSettings
from src.app.infrastructure.persistence import LangGraphPersistence


def test_langgraph_persistence_owns_contexts_without_private_attrs():
    persistence = LangGraphPersistence(
        checkpointer=object(),
        store=object(),
        checkpointer_context=object(),
        store_context=object(),
    )

    assert not hasattr(persistence.checkpointer, "_ctx")
    assert not hasattr(persistence.store, "_ctx")


def test_database_settings_builds_async_and_plain_postgres_urls():
    settings = DatabaseSettings(
        POSTGRES_PASSWORD=SecretStr("validdbpassword"),
        DB_HOST="localhost",
        DB_PORT=5432,
        POSTGRES_USER="hoteluser",
        POSTGRES_DB="hotelsdb",
    )

    assert (
        settings.sqlalchemy_url()
        == "postgresql+psycopg://hoteluser:validdbpassword@localhost:5432/hotelsdb"
    )
    assert (
        settings.psycopg_url()
        == "postgresql://hoteluser:validdbpassword@localhost:5432/hotelsdb"
    )


def test_database_settings_normalizes_plain_postgres_urls_to_psycopg():
    settings = DatabaseSettings(
        POSTGRES_PASSWORD=SecretStr("validdbpassword"),
        DATABASE_URL="postgresql://hoteluser:validdbpassword@localhost:5432/hotelsdb",
    )

    assert (
        settings.sqlalchemy_url()
        == "postgresql+psycopg://hoteluser:validdbpassword@localhost:5432/hotelsdb"
    )
    assert (
        settings.psycopg_url()
        == "postgresql://hoteluser:validdbpassword@localhost:5432/hotelsdb"
    )


def test_database_settings_normalizes_asyncpg_urls_to_psycopg():
    settings = DatabaseSettings(
        POSTGRES_PASSWORD=SecretStr("validdbpassword"),
        DATABASE_URL="postgresql+asyncpg://hoteluser:validdbpassword@localhost:5432/hotelsdb",
    )

    assert (
        settings.sqlalchemy_url()
        == "postgresql+psycopg://hoteluser:validdbpassword@localhost:5432/hotelsdb"
    )
