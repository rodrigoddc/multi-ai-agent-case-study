"""SQLAlchemy-backed reporting repository — infrastructure adapter."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.application.ports import ReportingRepository


class SqlAlchemyReportingRepository(ReportingRepository):
    """PostgreSQL-backed repository for report-ready marts."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self.session_maker = session_maker

    async def get_daily_flash(self, report_date: date | None = None) -> list[dict]:
        """Return daily flash rows for one report date."""
        where = (
            "calendar_date = :report_date"
            if report_date
            else "calendar_date = (SELECT MAX(calendar_date) FROM rpt_daily_flash)"
        )
        return await self._fetch_all(
            f"""
            SELECT *
            FROM rpt_daily_flash
            WHERE {where}
            ORDER BY revenue_vs_budget ASC, hotel_name
            """,
            {"report_date": report_date},
        )

    async def get_weekly_pace(
        self, year: int | None = None, week: int | None = None
    ) -> list[dict]:
        """Return weekly pace rows."""
        if year is not None and week is not None:
            where = "year = :year AND week_of_year = :week"
            params = {"year": year, "week": week}
        else:
            where = "(year, week_of_year) = (SELECT year, week_of_year FROM rpt_weekly_pace ORDER BY year DESC, week_of_year DESC LIMIT 1)"
            params = {}
        return await self._fetch_all(
            f"""
            SELECT *
            FROM rpt_weekly_pace
            WHERE {where}
            ORDER BY revenue_pickup_vs_ly ASC, hotel_name
            """,
            params,
        )

    async def get_monthly_owner_pack(
        self, year: int | None = None, month: int | None = None
    ) -> list[dict]:
        """Return monthly owner-pack rows."""
        if year is not None and month is not None:
            where = "year = :year AND month = :month"
            params = {"year": year, "month": month}
        else:
            where = "(year, month) = (SELECT year, month FROM rpt_monthly_owner_pack ORDER BY year DESC, month DESC LIMIT 1)"
            params = {}
        return await self._fetch_all(
            f"""
            SELECT *
            FROM rpt_monthly_owner_pack
            WHERE {where}
            ORDER BY gop_vs_budget ASC, hotel_name
            """,
            params,
        )

    async def get_quarterly_business_review(
        self, year: int | None = None, quarter: int | None = None
    ) -> list[dict]:
        """Return quarterly business review rows."""
        if year is not None and quarter is not None:
            where = "year = :year AND quarter = :quarter"
            params = {"year": year, "quarter": quarter}
        else:
            where = "(year, quarter) = (SELECT year, quarter FROM rpt_quarterly_business_review ORDER BY year DESC, quarter DESC LIMIT 1)"
            params = {}
        return await self._fetch_all(
            f"""
            SELECT *
            FROM rpt_quarterly_business_review
            WHERE {where}
            ORDER BY gop_margin ASC, brand, market
            """,
            params,
        )

    async def _fetch_all(self, sql: str, params: dict) -> list[dict]:
        async with self.session_maker() as session:
            result = await session.execute(text(sql), params)
            return [dict(row) for row in result.mappings().all()]
