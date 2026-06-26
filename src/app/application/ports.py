"""Application port interfaces for hotel insights.

These are the contracts that infrastructure adapters must implement.
The application layer depends on these abstractions, not concrete implementations.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence, runtime_checkable

from src.app.application.models.hotel import GuestReview, Hotel


@runtime_checkable
class HotelRepository(Protocol):
    """Port for hotel data access."""

    async def get_hotel_count(self) -> int: ...
    async def get_average_occupancy(self) -> float: ...
    async def get_average_revpar(self) -> float: ...
    async def get_average_sentiment(self) -> float: ...
    async def get_top_hotels(self, metric: str, limit: int) -> Sequence[Hotel]: ...
    async def get_bottom_hotels(self, metric: str, limit: int) -> Sequence[Hotel]: ...
    async def get_hotels_by_trend(self, trend: str, limit: int) -> Sequence[Hotel]: ...
    async def list_hotels(self) -> Sequence[Hotel]: ...
    async def list_reviews(self) -> Sequence[GuestReview]: ...


@runtime_checkable
class ReportingRepository(Protocol):
    """Port for hotel management report data access."""

    async def get_daily_flash(self, report_date=None) -> list[dict]: ...
    async def get_weekly_pace(
        self, year: int | None = None, week: int | None = None
    ) -> list[dict]: ...
    async def get_monthly_owner_pack(
        self, year: int | None = None, month: int | None = None
    ) -> list[dict]: ...
    async def get_quarterly_business_review(
        self, year: int | None = None, quarter: int | None = None
    ) -> list[dict]: ...


@runtime_checkable
class LLMAdapter(Protocol):
    """Port for LLM interaction.

    Abstracts away the specific LLM provider (OpenRouter, Anthropic, etc.).
    In production, a valid API key is required — no mock mode.
    """

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float,
        model: str,
        provider: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            system_prompt: System-level instruction/context.
            user_message: User's query or input.
            temperature: Sampling temperature (0.0-1.0).
            model: Required model identifier selected by the agent config.
            provider: Required provider selected by the agent config.
            config: Optional provider/runtime config such as callbacks and tags.

        Returns:
            Generated text response.

        Note:
            Adapters may expose a `last_usage` attribute (dict | None) after
            each call, with keys like ``input_tokens``, ``output_tokens``,
            ``total_tokens``, and optionally ``cost`` for providers that
            include pricing info.
        """
        ...


@runtime_checkable
class WeatherProvider(Protocol):
    """Port for obtaining weather data.

    Implementations may call external HTTP APIs (Open-Meteo, OpenWeatherMap, etc.).
    The application layer depends on this abstraction so infrastructure adapters can
    provide concrete network implementations without leaking HTTP code into
    business logic.
    """

    async def get_current_weather(self, location: str) -> dict:
        """Return current weather for a location.

        The returned dict must contain at least the keys:
        - temperature_c: float
        - condition: str
        - humidity: float
        - wind_kph: float

        Implementations may include additional metadata (observation_time, source).
        """


@runtime_checkable
class StoreProvider(Protocol):
    """Port for long-term memory storage."""

    async def get_preferences(self, user_id: str) -> dict: ...
    async def save_preference(self, user_id: str, key: str, value: dict) -> None: ...
