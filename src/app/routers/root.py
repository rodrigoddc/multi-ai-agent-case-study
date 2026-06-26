"""Root endpoint — serves the HTML frontend."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()

# Use Path object for robustness across OS and Docker
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/")
async def root(request: Request):
    """Serve the insights-first landing page."""
    return templates.TemplateResponse(
        request,
        "pages/home.html",
        {"request": request, "active_page": "insights"},
    )


@router.get("/chat")
async def chat_page(request: Request):
    """Serve the standalone chat page."""
    return templates.TemplateResponse(
        request,
        "pages/chat.html",
        {"request": request, "active_page": "chat"},
    )
