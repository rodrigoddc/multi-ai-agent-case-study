"""Hotel management report use cases."""

from __future__ import annotations

from datetime import date

from src.app.application.ports import ReportingRepository


class HotelManagementReportService:
    """Build report-ready management packs for hotel chain operators."""

    def __init__(self, repository: ReportingRepository) -> None:
        self._repository = repository

    async def get_daily_flash(self, report_date: date | None = None) -> dict:
        """Return a daily flash report for operating managers."""
        rows = await self._repository.get_daily_flash(report_date=report_date)
        portfolio = self._portfolio_summary(rows)
        return {
            "title": "Daily Flash Report",
            "report_date": report_date.isoformat()
            if report_date
            else "latest available",
            "portfolio": portfolio,
            "commentary": self._daily_flash_commentary(portfolio),
            "rows": rows,
        }

    async def get_weekly_pace(
        self, year: int | None = None, week: int | None = None
    ) -> dict:
        """Return weekly pace and pickup metrics."""
        rows = await self._repository.get_weekly_pace(year=year, week=week)
        portfolio = self._pace_summary(rows)
        return {
            "title": "Weekly Pace Report",
            "period": self._period_label(year=year, week=week),
            "portfolio": portfolio,
            "commentary": self._pace_commentary(portfolio),
            "rows": rows,
        }

    async def get_monthly_owner_pack(
        self, year: int | None = None, month: int | None = None
    ) -> dict:
        """Return owner-facing USALI-lite monthly performance pack."""
        rows = await self._repository.get_monthly_owner_pack(year=year, month=month)
        portfolio = self._owner_pack_summary(rows)
        return {
            "title": "Monthly Owner Pack",
            "period": self._period_label(year=year, month=month),
            "portfolio": portfolio,
            "commentary": self._owner_pack_commentary(portfolio),
            "rows": rows,
        }

    async def get_quarterly_business_review(
        self, year: int | None = None, quarter: int | None = None
    ) -> dict:
        """Return regional/brand quarterly business review data."""
        rows = await self._repository.get_quarterly_business_review(
            year=year, quarter=quarter
        )
        portfolio = self._qbr_summary(rows)
        return {
            "title": "Quarterly Business Review",
            "period": self._period_label(year=year, quarter=quarter),
            "portfolio": portfolio,
            "commentary": self._qbr_commentary(portfolio),
            "rows": rows,
        }

    async def get_report_index(self) -> dict:
        """Return default report landing-page data."""
        daily_flash = await self.get_daily_flash()
        weekly_pace = await self.get_weekly_pace()
        monthly_owner_pack = await self.get_monthly_owner_pack()
        quarterly_business_review = await self.get_quarterly_business_review()
        return {
            "daily_flash": daily_flash,
            "weekly_pace": weekly_pace,
            "monthly_owner_pack": monthly_owner_pack,
            "quarterly_business_review": quarterly_business_review,
        }

    def _portfolio_summary(self, rows: list[dict]) -> dict:
        if not rows:
            return {}
        rooms_available = sum(row["rooms_available"] for row in rows)
        rooms_sold = sum(row["rooms_sold"] for row in rows)
        total_revenue = sum(float(row["total_revenue"] or 0) for row in rows)
        revenue_vs_budget = sum(float(row["revenue_vs_budget"] or 0) for row in rows)
        gop = sum(float(row["gop"] or 0) for row in rows)
        avg_gss = self._avg(row.get("gss_score") for row in rows)
        return {
            "hotel_count": len(rows),
            "occupancy_rate": self._safe_percent(rooms_sold, rooms_available),
            "adr": self._safe_div(total_revenue, rooms_sold),
            "revpar": self._safe_div(total_revenue, rooms_available),
            "total_revenue": total_revenue,
            "revenue_vs_budget": revenue_vs_budget,
            "gop": gop,
            "gop_margin": self._safe_percent(gop, total_revenue),
            "gss_score": avg_gss,
        }

    def _pace_summary(self, rows: list[dict]) -> dict:
        if not rows:
            return {}
        room_nights = sum(row["room_nights_on_books"] for row in rows)
        revenue = sum(float(row["revenue_on_books"] or 0) for row in rows)
        room_pickup = sum(row["room_night_pickup_vs_ly"] for row in rows)
        revenue_pickup = sum(float(row["revenue_pickup_vs_ly"] or 0) for row in rows)
        return {
            "hotel_count": len(rows),
            "room_nights_on_books": room_nights,
            "revenue_on_books": revenue,
            "adr_on_books": self._safe_div(revenue, room_nights),
            "room_night_pickup_vs_ly": room_pickup,
            "revenue_pickup_vs_ly": revenue_pickup,
            "avg_booking_window_days": self._avg(
                row.get("avg_booking_window_days") for row in rows
            ),
        }

    def _owner_pack_summary(self, rows: list[dict]) -> dict:
        if not rows:
            return {}
        room_nights_available = sum(row["room_nights_available"] for row in rows)
        room_nights_sold = sum(row["room_nights_sold"] for row in rows)
        rooms_revenue = sum(float(row["rooms_revenue"] or 0) for row in rows)
        total_revenue = sum(float(row["total_revenue"] or 0) for row in rows)
        gop = sum(float(row["gop"] or 0) for row in rows)
        noi = sum(float(row["noi"] or 0) for row in rows)
        return {
            "hotel_count": len(rows),
            "occupancy_rate": self._safe_percent(
                room_nights_sold, room_nights_available
            ),
            "adr": self._safe_div(rooms_revenue, room_nights_sold),
            "revpar": self._safe_div(rooms_revenue, room_nights_available),
            "total_revenue": total_revenue,
            "gop": gop,
            "gop_margin": self._safe_percent(gop, total_revenue),
            "noi": noi,
            "revenue_vs_budget": sum(
                float(row["revenue_vs_budget"] or 0) for row in rows
            ),
            "gop_vs_budget": sum(float(row["gop_vs_budget"] or 0) for row in rows),
            "gss_score": self._avg(row.get("gss_score") for row in rows),
        }

    def _qbr_summary(self, rows: list[dict]) -> dict:
        if not rows:
            return {}
        room_nights_available = sum(row["room_nights_available"] for row in rows)
        room_nights_sold = sum(row["room_nights_sold"] for row in rows)
        total_revenue = sum(float(row["total_revenue"] or 0) for row in rows)
        gop = sum(float(row["gop"] or 0) for row in rows)
        return {
            "hotel_count": sum(row["hotel_count"] for row in rows),
            "occupancy_rate": self._safe_percent(
                room_nights_sold, room_nights_available
            ),
            "adr": self._safe_div(total_revenue, room_nights_sold),
            "revpar": self._safe_div(total_revenue, room_nights_available),
            "total_revenue": total_revenue,
            "gop": gop,
            "gop_margin": self._safe_percent(gop, total_revenue),
            "gss_score": self._avg(row.get("gss_score") for row in rows),
            "open_capex_budget": sum(
                float(row["open_capex_budget"] or 0) for row in rows
            ),
            "open_capex_spend": sum(
                float(row["open_capex_spend"] or 0) for row in rows
            ),
        }

    def _daily_flash_commentary(self, portfolio: dict) -> list[str]:
        if not portfolio:
            return ["No report rows are available. Run the hotel seed job first."]
        revenue_position = (
            "ahead of" if portfolio["revenue_vs_budget"] >= 0 else "behind"
        )
        return [
            f"Portfolio occupancy closed at {portfolio['occupancy_rate']:.1f}% with RevPAR of {portfolio['revpar']:.2f}.",
            f"Revenue is {revenue_position} budget by {abs(portfolio['revenue_vs_budget']):,.0f}, driven by rooms sold and ADR mix.",
            f"GOP margin is {portfolio['gop_margin']:.1f}%; watch labor and channel cost where margin is below brand target.",
        ]

    def _pace_commentary(self, portfolio: dict) -> list[str]:
        if not portfolio:
            return ["No weekly pace rows are available. Run the hotel seed job first."]
        room_position = (
            "ahead" if portfolio["room_night_pickup_vs_ly"] >= 0 else "behind"
        )
        revenue_position = (
            "ahead" if portfolio["revenue_pickup_vs_ly"] >= 0 else "behind"
        )
        return [
            f"Room nights on the books are {room_position} last year by {abs(portfolio['room_night_pickup_vs_ly']):,.0f} nights.",
            f"Revenue pickup is {revenue_position} last year by {abs(portfolio['revenue_pickup_vs_ly']):,.0f}.",
            f"Average booking window is {portfolio['avg_booking_window_days']:.1f} days; short-window demand should be monitored by channel.",
        ]

    def _owner_pack_commentary(self, portfolio: dict) -> list[str]:
        if not portfolio:
            return [
                "No monthly owner-pack rows are available. Run the hotel seed job first."
            ]
        return [
            f"Total revenue is {portfolio['total_revenue']:,.0f} with GOP margin at {portfolio['gop_margin']:.1f}%.",
            f"NOI after management fees and FF&E reserve is {portfolio['noi']:,.0f}.",
            f"GSS score is {portfolio['gss_score']:.1f}; brands below 90 should prioritize service recovery and QA follow-up.",
        ]

    def _qbr_commentary(self, portfolio: dict) -> list[str]:
        if not portfolio:
            return ["No QBR rows are available. Run the hotel seed job first."]
        return [
            f"Portfolio quarterly revenue is {portfolio['total_revenue']:,.0f} with GOP of {portfolio['gop']:,.0f}.",
            f"Open CapEx budget totals {portfolio['open_capex_budget']:,.0f}; current spend is {portfolio['open_capex_spend']:,.0f}.",
            "Review markets with RevPAR growth but weak GOP flow-through for labor, commission, and utility pressure.",
        ]

    def _period_label(
        self,
        *,
        year: int | None = None,
        month: int | None = None,
        week: int | None = None,
        quarter: int | None = None,
    ) -> str:
        if year is None:
            return "latest available"
        if month is not None:
            return f"{year}-{month:02d}"
        if week is not None:
            return f"{year} W{week:02d}"
        if quarter is not None:
            return f"{year} Q{quarter}"
        return str(year)

    def _avg(self, values) -> float:
        numbers = [float(value) for value in values if value is not None]
        return sum(numbers) / len(numbers) if numbers else 0.0

    def _safe_div(self, numerator: float, denominator: float) -> float:
        return float(numerator / denominator) if denominator else 0.0

    def _safe_percent(self, numerator: float, denominator: float) -> float:
        return self._safe_div(numerator, denominator) * 100
