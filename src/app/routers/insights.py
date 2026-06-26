"""Insights endpoints — HTTP adapter for the multi-agent pipeline.

Thin layer. Delegates to application services.
"""

from __future__ import annotations

import logging
import socket
from pathlib import Path

import httpx


from fastapi import APIRouter, Depends, Form, Header, Query, Request
from fastapi.templating import Jinja2Templates
from sse_starlette import EventSourceResponse

from src.app.application.dependencies import (
    get_chat_service,
    get_insight_summary_service,
    get_sse_service,
    get_tracing_config,
)
from src.app.application.models.request_identity import (
    build_request_identity,
    new_uuid8_hex,
)
from src.app.application.services.chat_service import (
    ChatService,
    ChatServiceTimeoutError,
    LLMAuthenticationError,
    LLMProviderUnavailableError,
    md_to_html,
)
from src.app.application.services.sse_chat_service import SSEChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@router.get("/report")
async def insights_report(request: Request):
    """Serve the standalone hotel performance report page."""
    return templates.TemplateResponse(
        request,
        "pages/report.html",
        {"request": request, "active_page": "insights"},
    )


@router.get("/summary")
async def insights_summary(
    summary_service=Depends(get_insight_summary_service),
):
    """Quick aggregated metrics without LLM reasoning."""
    return await summary_service.get_summary()


@router.get("/summary/fragment")
async def insights_summary_fragment(
    request: Request,
    summary_service=Depends(get_insight_summary_service),
):
    """Render summary metrics as an HTMX HTML fragment."""
    metrics = await summary_service.get_summary()
    return templates.TemplateResponse(
        request,
        "components/metrics_grid.html",
        {"request": request, "metrics": metrics},
    )


@router.get("/query")
async def insights_query(
    request: Request,
    query: str = Query(..., min_length=5),
    thread_id: str | None = Query(None, min_length=1),
    x_user_id: str = Header("anonymous", alias="X-User-ID"),
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
    chat_service: ChatService = Depends(get_chat_service),
):
    """Run a business question through the multi-agent graph."""
    identity = build_request_identity(
        user_id=x_user_id,
        thread_id=thread_id,
        session_id=x_session_id,
    )
    tracing_config = get_tracing_config(
        request=request,
        user_id=identity.user_id,
        session_id=identity.session_id,
        thread_id=identity.thread_id,
        trace_id=identity.trace_id,
    )

    result = await chat_service.process_chat(
        message=query,
        thread_id=identity.thread_id,
        user_id=identity.user_id,
        session_id=identity.session_id,
        tracing_config=tracing_config,
    )

    return {
        "question": query,
        "answer": result["final_answer"],
        "thread_id": result["thread_id"],
        "reasoning": result["reasoning_trace"],
    }


@router.get("/query/fragment")
async def insights_query_fragment(
    request: Request,
    query: str = Query(..., min_length=5),
    thread_id: str | None = Query(None, min_length=1),
    x_user_id: str = Header("anonymous", alias="X-User-ID"),
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
    chat_service: ChatService = Depends(get_chat_service),
):
    """Render a query answer as an HTMX HTML fragment."""
    identity = build_request_identity(
        user_id=x_user_id,
        thread_id=thread_id,
        session_id=x_session_id,
    )
    tracing_config = get_tracing_config(
        request=request,
        user_id=identity.user_id,
        session_id=identity.session_id,
        thread_id=identity.thread_id,
        trace_id=identity.trace_id,
    )
    try:
        result = await chat_service.process_chat(
            message=query,
            thread_id=identity.thread_id,
            user_id=identity.user_id,
            session_id=identity.session_id,
            tracing_config=tracing_config,
        )
    except LLMAuthenticationError:
        logger.warning(
            "Insight query authentication failed (thread_id=%s)",
            identity.thread_id,
        )
        return templates.TemplateResponse(
            request,
            "components/insight_error.html",
            {
                "request": request,
                "error_message": "Authentication failed. Please check your API credentials.",
            },
        )
    except LLMProviderUnavailableError as exc:
        logger.warning(
            "Insight query provider unavailable (thread_id=%s): %s",
            identity.thread_id,
            exc,
        )
        return templates.TemplateResponse(
            request,
            "components/insight_error.html",
            {"request": request, "error_message": str(exc)},
        )
    except (
        TimeoutError,
        socket.timeout,
        httpx.TimeoutException,
        ChatServiceTimeoutError,
    ):
        logger.warning(
            "Insight query timed out (thread_id=%s)",
            identity.thread_id,
        )
        return templates.TemplateResponse(
            request,
            "components/insight_error.html",
            {"request": request},
        )

    return templates.TemplateResponse(
        request,
        "components/insight_response.html",
        {"request": request, "content": md_to_html(result["final_answer"])},
    )


@router.post("/chat")
async def chat_initiate(
    request: Request,
    message: str = Form(...),
    thread_id: str | None = Form(None),
    target_id: str = Form("chat-messages"),
    thread_input_id: str = Form("thread-id"),
    x_user_id: str = Header("anonymous", alias="X-User-ID"),
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
    x_user_display_name: str | None = Header(None, alias="X-User-Display-Name"),
):
    """Return immediate HTMX chat feedback and a lazy AI response placeholder."""
    if not message or not message.strip():
        return templates.TemplateResponse(
            request,
            "components/chat_error.html",
            {"request": request, "error_message": "Message cannot be empty"},
            status_code=400,
        )

    clean_message = message.strip()
    identity = build_request_identity(
        user_id=x_user_id,
        thread_id=thread_id,
        session_id=x_session_id,
        display_name=x_user_display_name,
    )

    return templates.TemplateResponse(
        request,
        "components/chat_request.html",
        {
            "request": request,
            "user_message": clean_message,
            "thread_id": identity.thread_id,
            "message_id": new_uuid8_hex(),
            "target_id": target_id,
            "thread_input_id": thread_input_id,
            "user_id": identity.user_id,
            "session_id": identity.session_id,
            "display_name": identity.display_name,
        },
    )


@router.get("/chat/response")
async def chat_response(
    request: Request,
    message: str = Query(..., min_length=1),
    thread_id: str | None = Query(None, min_length=1),
    x_user_id: str = Header("anonymous", alias="X-User-ID"),
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
    chat_service: ChatService = Depends(get_chat_service),
):
    """Process a chat message and return the AI response fragment."""
    clean_message = message.strip()
    identity = build_request_identity(
        user_id=x_user_id,
        thread_id=thread_id,
        session_id=x_session_id,
    )
    tracing_config = get_tracing_config(
        request=request,
        user_id=identity.user_id,
        session_id=identity.session_id,
        thread_id=identity.thread_id,
        trace_id=identity.trace_id,
    )
    try:
        result = await chat_service.process_chat(
            message=clean_message,
            thread_id=identity.thread_id,
            user_id=identity.user_id,
            session_id=identity.session_id,
            tracing_config=tracing_config,
        )
    except LLMAuthenticationError:
        logger.warning(
            "Chat response authentication failed (thread_id=%s)",
            identity.thread_id,
        )
        return templates.TemplateResponse(
            request,
            "components/chat_error.html",
            {
                "request": request,
                "error_message": "Authentication failed. Please check your API credentials.",
            },
            status_code=401,
        )

    except LLMProviderUnavailableError as exc:
        logger.warning(
            "Chat response provider unavailable (thread_id=%s): %s",
            identity.thread_id,
            exc,
        )
        return templates.TemplateResponse(
            request,
            "components/chat_error.html",
            {"request": request, "error_message": str(exc)},
            status_code=503,
        )

    return templates.TemplateResponse(
        request,
        "components/chat_response.html",
        {
            "request": request,
            "thread_id": result["thread_id"],
            "content": md_to_html(result["final_answer"]),
        },
    )


@router.get("/chat/stream")
async def chat_stream_events(
    request: Request,
    thread_id: str | None = Query(None),
    message_id: str | None = Query(None),
    query: str = Query(..., min_length=1),
    target_id: str = Query("chat-messages"),
    thread_input_id: str = Query("thread-id"),
    x_user_id: str | None = Query(None, min_length=1, alias="user_id"),
    x_session_id: str | None = Query(None, min_length=1, alias="session_id"),
    x_user_display_name: str | None = Query(None, alias="display_name"),
    sse_service: SSEChatService = Depends(get_sse_service),
) -> EventSourceResponse:
    identity = build_request_identity(
        user_id=x_user_id,
        thread_id=thread_id,
        session_id=x_session_id,
        display_name=x_user_display_name,
    )
    effective_message_id = new_uuid8_hex() if message_id is None else message_id.strip()
    if not effective_message_id:
        effective_message_id = new_uuid8_hex()
    tracing_config = get_tracing_config(
        request=request,
        user_id=identity.user_id,
        session_id=identity.session_id,
        thread_id=identity.thread_id,
        trace_id=identity.trace_id,
    )

    return EventSourceResponse(
        sse_service.stream_chat(
            message=query,
            thread_id=identity.thread_id,
            user_id=identity.user_id,
            session_id=identity.session_id,
            tracing_config=tracing_config,
            message_id=effective_message_id,
            target_id=target_id,
            thread_input_id=thread_input_id,
            display_name=identity.display_name,
        )
    )
