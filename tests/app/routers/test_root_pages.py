from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from src.app.infrastructure.config import settings
from src.app.main import create_app


@asynccontextmanager
async def empty_lifespan(app):
    yield


def test_root_page_serves_insights_first_landing_page():
    app = create_app(settings.APP_ENV, lifespan_context=empty_lifespan)

    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Hotel Performance Report" in response.text
    assert "Insights Assistant" in response.text
    assert "assistant-panel" in response.text
    assert "Ask Questions About Your Hotels" not in response.text


def test_standalone_chat_page_remains_available():
    app = create_app(settings.APP_ENV, lifespan_context=empty_lifespan)

    with TestClient(app) as client:
        response = client.get("/chat")

    assert response.status_code == 200
    assert "Ask Questions About Your Hotels" in response.text
    assert "Hotel Performance Report" not in response.text
