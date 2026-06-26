"""Auth endpoints for lightweight display-name handling."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.templating import Jinja2Templates

from src.app.application.models.request_identity import build_request_identity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@router.post("/signin")
async def signin_display_name(
    request: Request,
    display_name: str | None = Form(None, alias="display_name"),
):
    """Save an optional user display name in the browser.

    Client-side code stores the final value in localStorage. If omitted or
    invalid, the client should continue as anonymous.
    """
    identity = build_request_identity(display_name=display_name)
    if request.headers.get("HX-Request") != "true":
        return {"accepted": True, "display_name": identity.display_name}
    return templates.TemplateResponse(
        request,
        "components/chat_request.html",
        {"request": request},
    )


@router.get("/viewer")
async def viewer(request: Request) -> dict:
    """Return minimal viewer metadata for header refresh flows."""
    display_name = request.headers.get("X-User-Display-Name", "")
    return {
        "display_name": display_name.strip() if isinstance(display_name, str) else ""
    }
