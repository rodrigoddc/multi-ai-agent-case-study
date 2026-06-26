"""SQLAlchemy ORM models for hotel data — infrastructure adapter.

Maps database tables to Python objects. These are separate from the
application models in src/app/application/models/.
"""

from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class HotelORM(Base):
    """SQLAlchemy ORM mapping for the hotels table."""

    __tablename__ = "hotels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    brand = Column(String(255), nullable=False)
    region = Column(String(100), nullable=False)
    rooms = Column(Integer, nullable=False)
    occupancy_rate = Column(Float, nullable=False)
    revpar = Column(Float, nullable=False)
    avg_sentiment = Column(Float, nullable=False)
    trend = Column(String(100), nullable=False)

    reviews = relationship("GuestReviewORM", back_populates="hotel")


class GuestReviewORM(Base):
    """SQLAlchemy ORM mapping for the guest_reviews table."""

    __tablename__ = "guest_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    score = Column(Integer, nullable=False)
    sentiment = Column(Float, nullable=False)
    comment = Column(String(500), nullable=False)

    hotel = relationship("HotelORM", back_populates="reviews")
