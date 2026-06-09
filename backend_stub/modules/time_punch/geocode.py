"""Address geocoding for punch sites (OpenStreetMap Nominatim)."""

from __future__ import annotations

import os

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = os.getenv("GEOCODE_USER_AGENT", "ShiftSwiftHR/1.0 (time-punch)")


def geocode_address(address: str) -> tuple[float, float] | None:
    query = (address or "").strip()
    if len(query) < 5:
        return None
    try:
        with httpx.Client(timeout=12.0) as client:
            response = client.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1, "countrycodes": "gb"},
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            rows = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not rows:
        return None
    try:
        return float(rows[0]["lat"]), float(rows[0]["lon"])
    except (KeyError, TypeError, ValueError):
        return None
