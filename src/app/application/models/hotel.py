"""Hotel and GuestReview application models.

Pydantic models for application logic. No SQLAlchemy dependencies.
ORM mappings live in the infrastructure layer.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Hotel(BaseModel):
    """A hotel property with performance metrics."""

    id: int = Field(..., description="Primary key")
    name: str = Field(..., description="Hotel name", max_length=255)
    brand: str = Field(..., description="Hotel brand", max_length=255)
    region: str = Field(..., description="Geographic region", max_length=100)
    rooms: int = Field(..., description="Number of rooms")
    occupancy_rate: float = Field(..., description="Occupancy rate percentage")
    revpar: float = Field(..., description="Revenue per available room")
    avg_sentiment: float = Field(..., description="Average guest sentiment score")
    trend: str = Field(..., description="Performance trend", max_length=100)


class GuestReview(BaseModel):
    """A guest review for a hotel."""

    id: int = Field(..., description="Primary key")
    hotel_id: int = Field(..., description="Foreign key to hotel")
    score: int = Field(..., description="Guest score")
    sentiment: float = Field(..., description="Sentiment analysis score")
    comment: str = Field(..., description="Review comment", max_length=500)
