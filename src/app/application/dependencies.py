"""Application dependencies — typed service providers for FastAPI injection."""

from __future__ import annotations

from fastapi import Depends, Request

from src.app.application.services.chat_service import ChatService
from src.app.application.services.sse_chat_service import SSEChatService
from src.app.bootstrap.container import ApplicationContainer
from src.app.application.models.request_identity import new_uuid8_hex


def get_container(request: Request) -> ApplicationContainer:
    """Retrieve the typed application container from app state."""
    container = getattr(request.app.state, "container", None)
    if not isinstance(container, ApplicationContainer):
        raise RuntimeError(
            "Application container not initialized. Check lifespan startup."
        )
    return container


def get_chat_service(
    container: ApplicationContainer = Depends(get_container),
) -> ChatService:
    """Retrieve the startup-created chat service."""
    return container.chat_service


def get_sse_service(
    container: ApplicationContainer = Depends(get_container),
) -> SSEChatService:
    """Retrieve the startup-created SSE chat service."""
    return container.sse_chat_service


def get_hotel_query_service(container: ApplicationContainer = Depends(get_container)):
    """Retrieve hotel query service."""
    return container.hotel_query_service


def get_insight_summary_service(
    container: ApplicationContainer = Depends(get_container),
):
    """Retrieve insight summary service."""
    return container.insight_summary_service


def get_management_report_service(
    container: ApplicationContainer = Depends(get_container),
):
    """Retrieve hotel management report service."""
    if container.management_report_service is None:
        raise RuntimeError("Management report service is not initialized.")
    return container.management_report_service


def get_tracing_config(
    request: Request,
    user_id: str,
    session_id: str,
    thread_id: str,
    trace_id: str | None = None,
) -> dict | None:
    """Build tracing config from the container-managed tracing service."""
    container = get_container(request)
    build_config = getattr(container.tracing_service, "build_config", None)
    if build_config is None:
        return None
    return build_config(
        user_id=user_id,
        session_id=session_id,
        thread_id=thread_id,
        trace_id=trace_id or new_uuid8_hex(),
    )
