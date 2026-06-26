from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.application.dependencies import get_container
from src.app.bootstrap.container import ApplicationContainer
from src.app.routers import hotels, insights


class HotelQueryServiceStub:
    async def list_hotels(self):
        return [{"id": 1, "name": "Hotel A"}]

    async def list_reviews(self):
        return [{"id": 1, "hotel_id": 1, "score": 5}]


class InsightSummaryServiceStub:
    async def get_summary(self):
        return {"hotel_count": 1}


def build_container() -> ApplicationContainer:
    return ApplicationContainer(
        settings=SimpleNamespace(environment="test"),
        graph=object(),
        repository=object(),
        llm=object(),
        chat_service=object(),
        sse_chat_service=object(),
        hotel_query_service=HotelQueryServiceStub(),
        insight_summary_service=InsightSummaryServiceStub(),
        tracing_service=object(),
    )


def test_get_container_reads_only_typed_container_from_app_state():
    app = FastAPI()
    app.state.container = build_container()

    @app.get("/container")
    def read_container(container=fastapi_depends(get_container)):
        return {"environment": container.settings.environment}

    with TestClient(app) as client:
        response = client.get("/container")

    assert response.status_code == 200
    assert response.json() == {"environment": "test"}


def fastapi_depends(dependency):
    from fastapi import Depends

    return Depends(dependency)


def test_hotels_router_uses_service_dependency_not_app_state_session_maker():
    app = FastAPI()
    app.include_router(hotels.router)
    app.state.container = build_container()

    with TestClient(app) as client:
        response = client.get("/hotels")

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "Hotel A"}]


def test_insights_summary_uses_container_service_not_request_time_clients():
    app = FastAPI()
    app.include_router(insights.router)
    app.state.container = build_container()

    with TestClient(app) as client:
        response = client.get("/insights/summary")

    assert response.status_code == 200
    assert response.json() == {"hotel_count": 1}
