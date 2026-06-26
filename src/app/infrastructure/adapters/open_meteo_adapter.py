"""Open-Meteo adapter implementing the WeatherProvider port.

Uses httpx for async HTTP calls. Returns normalized dict compatible with
WeatherProvider.get_current_weather contract.
"""

from __future__ import annotations

from typing import Any

import urllib.parse

import httpx


OPEN_METEO_ENDPOINT = "https://api.open-meteo.com/v1/forecast"


class OpenMeteoAdapter:
    """Adapter for Open-Meteo current weather lookups.

    This implementation resolves a free-form location by attempting to parse
    a "lat,lon" pair first. If the string doesn't match lat,lon, it will
    attempt a direct lookup via Open-Meteo's geocoding API (simple fallback).
    """

    def __init__(self, *, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=10.0)

    async def _resolve_latlon(self, location: str) -> tuple[float, float] | None:
        loc = location.strip()
        if "," in loc:
            parts = [p.strip() for p in loc.split(",", 1)]
            try:
                lat = float(parts[0])
                lon = float(parts[1])
                return lat, lon
            except ValueError:
                return None
        # Use Open-Meteo geocoding
        q = urllib.parse.quote_plus(loc)
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1"
        resp = await self._client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("results") or []
        if not results:
            return None
        first = results[0]
        return float(first.get("latitude")), float(first.get("longitude"))

    async def get_current_weather(self, location: str) -> dict[str, Any]:
        latlon = await self._resolve_latlon(location)
        if latlon is None:
            raise RuntimeError("Unable to resolve location to lat,lon")
        lat, lon = latlon
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "hourly": "",
        }
        resp = await self._client.get(OPEN_METEO_ENDPOINT, params=params)
        if resp.status_code != 200:
            raise RuntimeError("Open-Meteo request failed")
        payload = resp.json()
        current = payload.get("current_weather") or {}
        # Normalize keys expected by WeatherProvider
        temp_c = float(current.get("temperature", 0.0))
        wind_mps = float(current.get("windspeed", 0.0))
        # open-meteo provides windspeed in km/h? docs say km/h for wv
        wind_kph = wind_mps
        condition = "Unknown"
        # Open-Meteo current_weather does not include a human condition; leave as code
        return {
            "temperature_c": temp_c,
            "condition": condition,
            "humidity": float(
                payload.get("hourly", {}).get("relativehumidity_2m", [0])[0]
            )
            if payload.get("hourly")
            else 0.0,
            "wind_kph": wind_kph,
            "observation_time": current.get("time"),
            "source": "open-meteo",
            "latitude": lat,
            "longitude": lon,
            "raw": payload,
        }
