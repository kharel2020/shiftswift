"""Unit tests for geofenced time punch."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from modules.time_punch.service import haversine_meters, preview_geofence, record_punch


def test_haversine_same_point_is_zero() -> None:
    assert haversine_meters(53.48, -2.24, 53.48, -2.24) == 0.0


def test_haversine_known_distance_roughly() -> None:
    # ~1 km north-south at Manchester latitude
    distance = haversine_meters(53.48, -2.24, 53.489, -2.24)
    assert 900 < distance < 1100


def test_record_punch_rejects_when_outside_geofence() -> None:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor

    cursor.fetchone.side_effect = [
        (1, "Demo", "Employee", "employee@shiftswifthr.co.uk", "active"),
        (10, "in", "2026-06-08T09:00:00+00:00", "Main site", 1),
    ]
    cursor.fetchall.side_effect = [
        [],
        [(1, 1, "Main site", "1 Spinningfields", 53.4794, -2.2451, 150, True, True)],
    ]

    try:
        record_punch(
            tenant_id=1,
            employee_id=1,
            username="employee@shiftswifthr.co.uk",
            punch_type="out",
            latitude=51.5074,
            longitude=-0.1278,
            accuracy_meters=10.0,
            ip_address="127.0.0.1",
            user_agent="test",
            conn=conn,
        )
        assert False, "expected PermissionError"
    except PermissionError as exc:
        assert "150m" in str(exc)


def test_preview_geofence_outside() -> None:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = [
        (1, 1, "Himalayan Inn", "1 High St", 53.4794, -2.2451, 100, True, True),
    ]

    result = preview_geofence(
        tenant_id=1,
        employee_id=1,
        latitude=51.5074,
        longitude=-0.1278,
        accuracy_meters=34.0,
        conn=conn,
    )
    assert result["within_geofence"] is False
    assert result["accuracy_meters"] == 34.0
    assert "Himalayan Inn" in result["message"]
    assert result["radius_meters"] == 100


def test_preview_geofence_inside() -> None:
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = [
        (1, 1, "Himalayan Inn", "1 High St", 53.4794, -2.2451, 100, True, True),
    ]

    result = preview_geofence(
        tenant_id=1,
        employee_id=1,
        latitude=53.4794,
        longitude=-2.2451,
        accuracy_meters=12.0,
        conn=conn,
    )
    assert result["within_geofence"] is True
    assert result["distance_meters"] == 0.0
