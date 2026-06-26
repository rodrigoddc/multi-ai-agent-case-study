"""Insight summary application service."""

from __future__ import annotations

from src.app.application.ports import HotelRepository, LLMAdapter


class InsightSummaryService:
    """Provides summary metrics without request-time infrastructure creation."""

    def __init__(self, repository: HotelRepository, llm: LLMAdapter) -> None:
        self._repository = repository
        self._llm = llm

    async def get_summary(self) -> dict:
        """Return aggregated hotel metrics."""
        return {
            "hotel_count": await self._repository.get_hotel_count(),
            "average_occupancy_rate": await self._repository.get_average_occupancy(),
            "average_revpar": await self._repository.get_average_revpar(),
            "average_sentiment": await self._repository.get_average_sentiment(),
        }
