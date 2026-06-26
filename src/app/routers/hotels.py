"""Hotel data endpoints — HTTP adapter."""

from fastapi import APIRouter, Depends

from src.app.application.dependencies import get_hotel_query_service
from src.app.application.services.hotel_query_service import HotelQueryService

router = APIRouter(tags=["hotels"])


@router.get("/hotels")
async def get_hotels(
    hotel_query_service: HotelQueryService = Depends(get_hotel_query_service),
):
    """List hotels."""
    return await hotel_query_service.list_hotels()


@router.get("/reviews")
async def get_reviews(
    hotel_query_service: HotelQueryService = Depends(get_hotel_query_service),
):
    """List guest reviews."""
    return await hotel_query_service.list_reviews()
