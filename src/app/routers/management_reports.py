"""Hotel management report endpoints — HTTP adapter."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates

from src.app.application.dependencies import get_management_report_service
from src.app.application.services.hotel_management_report_service import (
    HotelManagementReportService,
)

router = APIRouter(prefix="/management-reports", tags=["management-reports"])

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("")
async def report_index(
    request: Request,
    report_service: HotelManagementReportService = Depends(
        get_management_report_service
    ),
):
    """Render the management report landing page."""
    reports = await report_service.get_report_index()
    return templates.TemplateResponse(
        request,
        "pages/management_reports.html",
        {"request": request, "active_page": "reports", "reports": reports},
    )


@router.get("/daily-flash")
async def daily_flash(
    report_date: date | None = Query(None),
    report_service: HotelManagementReportService = Depends(
        get_management_report_service
    ),
):
    """Return daily flash report data."""
    return await report_service.get_daily_flash(report_date=report_date)


@router.get("/daily-flash/fragment")
async def daily_flash_fragment(
    request: Request,
    report_date: date | None = Query(None),
    report_service: HotelManagementReportService = Depends(
        get_management_report_service
    ),
):
    """Render daily flash report fragment."""
    report = await report_service.get_daily_flash(report_date=report_date)
    return templates.TemplateResponse(
        request,
        "reports/daily_flash.html",
        {"request": request, "report": report},
    )


@router.get("/weekly-pace")
async def weekly_pace(
    year: int | None = Query(None, ge=2024, le=2030),
    week: int | None = Query(None, ge=1, le=53),
    report_service: HotelManagementReportService = Depends(
        get_management_report_service
    ),
):
    """Return weekly pace report data."""
    return await report_service.get_weekly_pace(year=year, week=week)


@router.get("/weekly-pace/fragment")
async def weekly_pace_fragment(
    request: Request,
    year: int | None = Query(None, ge=2024, le=2030),
    week: int | None = Query(None, ge=1, le=53),
    report_service: HotelManagementReportService = Depends(
        get_management_report_service
    ),
):
    """Render weekly pace report fragment."""
    report = await report_service.get_weekly_pace(year=year, week=week)
    return templates.TemplateResponse(
        request,
        "reports/weekly_pace.html",
        {"request": request, "report": report},
    )


@router.get("/monthly-owner-pack")
async def monthly_owner_pack(
    year: int | None = Query(None, ge=2024, le=2030),
    month: int | None = Query(None, ge=1, le=12),
    report_service: HotelManagementReportService = Depends(
        get_management_report_service
    ),
):
    """Return monthly owner-pack report data."""
    return await report_service.get_monthly_owner_pack(year=year, month=month)


@router.get("/monthly-owner-pack/fragment")
async def monthly_owner_pack_fragment(
    request: Request,
    year: int | None = Query(None, ge=2024, le=2030),
    month: int | None = Query(None, ge=1, le=12),
    report_service: HotelManagementReportService = Depends(
        get_management_report_service
    ),
):
    """Render monthly owner-pack report fragment."""
    report = await report_service.get_monthly_owner_pack(year=year, month=month)
    return templates.TemplateResponse(
        request,
        "reports/monthly_owner_pack.html",
        {"request": request, "report": report},
    )


@router.get("/quarterly-business-review")
async def quarterly_business_review(
    year: int | None = Query(None, ge=2024, le=2030),
    quarter: int | None = Query(None, ge=1, le=4),
    report_service: HotelManagementReportService = Depends(
        get_management_report_service
    ),
):
    """Return quarterly business review report data."""
    return await report_service.get_quarterly_business_review(
        year=year, quarter=quarter
    )


@router.get("/quarterly-business-review/fragment")
async def quarterly_business_review_fragment(
    request: Request,
    year: int | None = Query(None, ge=2024, le=2030),
    quarter: int | None = Query(None, ge=1, le=4),
    report_service: HotelManagementReportService = Depends(
        get_management_report_service
    ),
):
    """Render quarterly business review report fragment."""
    report = await report_service.get_quarterly_business_review(
        year=year, quarter=quarter
    )
    return templates.TemplateResponse(
        request,
        "reports/quarterly_business_review.html",
        {"request": request, "report": report},
    )
