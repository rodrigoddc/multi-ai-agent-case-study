from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from src.app.infrastructure.config import settings
from src.app.main import create_app


@asynccontextmanager
async def empty_lifespan(app):
    yield


def test_create_app_can_disable_lifespan_for_router_tests():
    app = create_app(settings.APP_ENV, lifespan_context=empty_lifespan)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
