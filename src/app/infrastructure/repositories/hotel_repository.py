"""SQLAlchemy-backed hotel repository — infrastructure adapter.

Implements the HotelRepository application port.
Maps between SQLA ORM models and application models.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.application.models.hotel import Hotel
from src.app.application.ports import HotelRepository
from src.app.infrastructure.orm_models import HotelORM, GuestReviewORM


def _orm_to_model(orm: HotelORM) -> Hotel:
    """Map SQLAlchemy ORM hotel to application model."""
    return Hotel(
        id=orm.id,
        name=orm.name,
        brand=orm.brand,
        region=orm.region,
        rooms=orm.rooms,
        occupancy_rate=float(orm.occupancy_rate),
        revpar=float(orm.revpar),
        avg_sentiment=float(orm.avg_sentiment),
        trend=orm.trend,
    )


class SqlAlchemyHotelRepository(HotelRepository):
    """PostgreSQL-backed hotel repository implementing HotelRepository port."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self.session_maker = session_maker

    async def get_hotel_count(self) -> int:
        async with self.session_maker() as session:
            val = await session.scalar(select(func.count()).select_from(HotelORM))
            return int(val or 0)

    async def get_average_occupancy(self) -> float:
        async with self.session_maker() as session:
            val = await session.scalar(select(func.avg(HotelORM.occupancy_rate)))
            return float(val or 0.0)

    async def get_average_revpar(self) -> float:
        async with self.session_maker() as session:
            val = await session.scalar(select(func.avg(HotelORM.revpar)))
            return float(val or 0.0)

    async def get_average_sentiment(self) -> float:
        async with self.session_maker() as session:
            val = await session.scalar(select(func.avg(HotelORM.avg_sentiment)))
            return float(val or 0.0)

    async def get_top_hotels(
        self, metric: str = "sentiment", limit: int = 5
    ) -> list[Hotel]:
        async with self.session_maker() as session:
            order_col = self._order_column(metric, ascending=False)
            result = await session.execute(
                select(HotelORM).order_by(order_col).limit(limit)
            )
            return [_orm_to_model(h) for h in result.scalars().all()]

    async def get_bottom_hotels(
        self, metric: str = "sentiment", limit: int = 5
    ) -> list[Hotel]:
        async with self.session_maker() as session:
            order_col = self._order_column(metric, ascending=True)
            result = await session.execute(
                select(HotelORM).order_by(order_col).limit(limit)
            )
            return [_orm_to_model(h) for h in result.scalars().all()]

    async def get_hotels_by_trend(self, trend: str, limit: int = 5) -> list[Hotel]:
        async with self.session_maker() as session:
            result = await session.execute(
                select(HotelORM).where(HotelORM.trend.ilike(f"%{trend}%")).limit(limit)
            )
            return [_orm_to_model(h) for h in result.scalars().all()]

    def _order_column(self, metric: str, ascending: bool):
        col_map = {
            "sentiment": HotelORM.avg_sentiment,
            "occupancy": HotelORM.occupancy_rate,
            "revpar": HotelORM.revpar,
        }
        col = col_map.get(metric, HotelORM.avg_sentiment)
        return col.asc() if ascending else col.desc()

    async def list_hotels(self) -> list[Hotel]:
        async with self.session_maker() as session:
            result = await session.execute(select(HotelORM))
            return [_orm_to_model(h) for h in result.scalars().all()]

    async def list_reviews(self) -> list[dict]:
        async with self.session_maker() as session:
            result = await session.execute(select(GuestReviewORM))
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "hotel_id": r.hotel_id,
                    "score": r.score,
                    "sentiment": r.sentiment,
                    "comment": r.comment,
                }
                for r in rows
            ]
