"""Hotel query application service."""

from __future__ import annotations

from __future__ import annotations

from src.app.application.ports import HotelRepository


class HotelQueryService:
    """Read-only hotel data use cases.

    This service depends on the HotelRepository port instead of importing
    SQLAlchemy ORM models. Infrastructure adapters implement the port and
    perform ORM mapping.
    """

    def __init__(self, repository: HotelRepository) -> None:
        self._repository = repository

    async def list_hotels(self) -> list[dict]:
        hotels = await self._repository.list_hotels()
        return [h.model_dump() for h in hotels]

    async def list_reviews(self) -> list[dict]:
        reviews = await self._repository.list_reviews()
        return [r.model_dump() for r in reviews]
