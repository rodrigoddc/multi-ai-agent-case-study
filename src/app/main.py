"""Composition root — FastAPI application factory."""

from __future__ import annotations
import logging

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from functools import partial

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.app.bootstrap.strategy import _STRATEGIES
from src.app.infrastructure.config import AppEnvironment, BASE_DIR, settings
from src.app.routers import auth, health, hotels, insights, management_reports, root

from src.app.application.services.chat_service import (
    ChatServiceTimeoutError,
    LLMAuthenticationError,
    LLMProviderUnavailableError,
)
from src.app.bootstrap.lifespan import lifespan_for_strategy
from src.app.infrastructure.logging_config import configure_logging


LifespanFactory = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    templates = Jinja2Templates(directory=BASE_DIR / "templates")

    @app.exception_handler(TimeoutError)
    @app.exception_handler(ChatServiceTimeoutError)
    async def timeout_exception_handler(
        request: Request, exc: TimeoutError | ChatServiceTimeoutError
    ) -> HTMLResponse:
        # For HTMX fragment requests, return the error fragment
        if request.headers.get("HX-Request") == "true":
            return templates.TemplateResponse(
                request,
                "components/insight_error.html",
                {"request": request},
            )
        # For SSE/streaming requests, let FastAPI's default handler deal with it
        # For regular requests, return a simple error page
        return HTMLResponse(
            content="""
            <html>
                <head><title>Request Timeout</title></head>
                <body style="font-family: system-ui; padding: 2rem; max-width: 600px; margin: 2rem auto;">
                    <h1>Request Timed Out</h1>
                    <p>The AI model did not respond in time. Please try again.</p>
                    <a href="/" style="color: #3b82f6;">← Back to Report</a>
                </body>
            </html>
            """,
            status_code=504,
        )

    @app.exception_handler(LLMAuthenticationError)
    async def auth_exception_handler(
        request: Request, exc: LLMAuthenticationError
    ) -> HTMLResponse:
        # For HTMX fragment requests, return an error fragment with auth message
        if request.headers.get("HX-Request") == "true":
            return templates.TemplateResponse(
                request,
                "components/insight_error.html",
                {
                    "request": request,
                    "error_message": "Authentication failed. Please check your API credentials.",
                },
            )
        # For regular requests, return a simple error page
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Authentication Error</title></head>
                <body style="font-family: system-ui; padding: 2rem; max-width: 600px; margin: 2rem auto;">
                    <h1>Authentication Failed</h1>
                    <p>The AI provider rejected the request due to missing or invalid credentials.</p>
                    <p style="color: #666; font-size: 0.875rem;">{exc}</p>
                    <a href="/" style="color: #3b82f6;">← Back to Report</a>
                </body>
            </html>
            """,
            status_code=401,
        )

    @app.exception_handler(LLMProviderUnavailableError)
    async def provider_unavailable_exception_handler(
        request: Request, exc: LLMProviderUnavailableError
    ) -> HTMLResponse:
        if request.headers.get("HX-Request") == "true":
            return templates.TemplateResponse(
                request,
                "components/insight_error.html",
                {"request": request, "error_message": str(exc)},
                status_code=503,
            )
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>AI Provider Unavailable</title></head>
                <body style="font-family: system-ui; padding: 2rem; max-width: 600px; margin: 2rem auto;">
                    <h1>AI Provider Unavailable</h1>
                    <p>{exc}</p>
                    <a href="/" style="color: #3b82f6;">← Back to Report</a>
                </body>
            </html>
            """,
            status_code=503,
        )


def create_app(
    environment: AppEnvironment,
    *,
    lifespan_context: LifespanFactory | None = None,
) -> FastAPI:
    """Create and configure a FastAPI application instance.

    Args:
        environment: Runtime environment name.
        lifespan_context: Optional lifespan override for tests.

    Returns:
        Configured FastAPI application.
    """
    configure_logging()

    logging.info("Starting application with environment: %s", environment.value)

    strategy = _STRATEGIES[environment]
    effective_lifespan = lifespan_context or partial(
        lifespan_for_strategy, strategy=strategy
    )

    fastapi_app = FastAPI(title="Hotel Insights API", lifespan=effective_lifespan)
    fastapi_app.state.environment = environment.value

    _register_exception_handlers(fastapi_app)

    static_path = BASE_DIR / "src" / "app" / "static"
    fastapi_app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    fastapi_app.include_router(root.router)
    fastapi_app.include_router(health.router)
    fastapi_app.include_router(auth.router)
    fastapi_app.include_router(hotels.router)
    fastapi_app.include_router(insights.router)
    fastapi_app.include_router(management_reports.router)
    return fastapi_app


app = create_app(settings.APP_ENV)
