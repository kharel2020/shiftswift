"""Shared infrastructure — database connections."""

from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException


def get_connection() -> Any:
    import psycopg2

    url = os.getenv("DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
    return psycopg2.connect(url)
