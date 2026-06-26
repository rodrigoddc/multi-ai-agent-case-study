import importlib


def test_seed_database_url_recomputes_from_runtime_database_host(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "hoteluser")
    monkeypatch.setenv("POSTGRES_PASSWORD", "hotelpass")
    monkeypatch.setenv("POSTGRES_DB", "hotelsdb")
    monkeypatch.setenv("DB_HOST", "pgbouncer")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    seed_hotels = importlib.import_module("src.jobs.seed_hotels")
    seed_hotels = importlib.reload(seed_hotels)

    assert seed_hotels.get_database_url() == (
        "postgresql+psycopg://hoteluser:hotelpass@pgbouncer:5432/hotelsdb"
    )


def test_seed_database_url_normalizes_runtime_database_url_to_psycopg(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "hoteluser")
    monkeypatch.setenv("POSTGRES_PASSWORD", "hotelpass")
    monkeypatch.setenv("POSTGRES_DB", "hotelsdb")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://hoteluser:hotelpass@postgres:5432/hotelsdb",
    )

    seed_hotels = importlib.import_module("src.jobs.seed_hotels")
    seed_hotels = importlib.reload(seed_hotels)

    assert seed_hotels.get_database_url() == (
        "postgresql+psycopg://hoteluser:hotelpass@postgres:5432/hotelsdb"
    )
