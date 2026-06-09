"""Digital Right to Work verification via IDSP or development mock."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx


class IdspError(Exception):
    pass


def idsp_configured() -> bool:
    return bool(os.getenv("IDSP_API_KEY") and os.getenv("IDSP_API_URL"))


def verify_share_code(
    *,
    share_code: str,
    date_of_birth: date,
    employee_id: int,
    tenant_id: int,
) -> dict[str, Any]:
    share_code = share_code.strip().upper()
    if len(share_code) < 6:
        raise IdspError("Share code must be at least 6 characters")

    if idsp_configured():
        return _verify_via_idsp(share_code=share_code, date_of_birth=date_of_birth)

    return _verify_mock(
        share_code=share_code,
        date_of_birth=date_of_birth,
        employee_id=employee_id,
        tenant_id=tenant_id,
    )


def _verify_via_idsp(*, share_code: str, date_of_birth: date) -> dict[str, Any]:
    api_url = os.getenv("IDSP_API_URL", "").rstrip("/")
    api_key = os.getenv("IDSP_API_KEY", "")
    try:
        response = httpx.post(
            f"{api_url}/verify",
            json={
                "share_code": share_code,
                "date_of_birth": date_of_birth.isoformat(),
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        raise IdspError(f"IDSP verification request failed: {exc}") from exc

    outcome = data.get("outcome", data.get("status", "unknown")).lower()
    approved = outcome in {"accepted", "approved", "pass", "time_limited"}
    expiry_raw = data.get("expiry_date") or data.get("visa_expiry_date")
    expiry_date = date.fromisoformat(str(expiry_raw)[:10]) if expiry_raw else None
    return {
        "mode": "idsp",
        "outcome": "pass" if approved else "fail",
        "rtw_status": "approved" if approved else "rejected",
        "expiry_date": expiry_date.isoformat() if expiry_date else None,
        "provider_reference": data.get("reference") or data.get("transaction_id"),
        "raw": data,
    }


def _verify_mock(
    *,
    share_code: str,
    date_of_birth: date,
    employee_id: int,
    tenant_id: int,
) -> dict[str, Any]:
    """Deterministic mock for local dev when IDSP is not configured."""
    seed = sum(ord(c) for c in share_code) + date_of_birth.toordinal() + employee_id + tenant_id
    approved = seed % 7 != 0
    expiry = date.today() + timedelta(days=180 + (seed % 365))
    return {
        "mode": "mock",
        "outcome": "pass" if approved else "fail",
        "rtw_status": "approved" if approved else "rejected",
        "expiry_date": expiry.isoformat() if approved else None,
        "provider_reference": f"MOCK-{share_code[:4]}-{employee_id}",
        "message": "IDSP not configured — mock verification for development only.",
    }


def persist_verification(
    *,
    conn: Any,
    tenant_id: int,
    employee_id: int,
    share_code: str,
    verification: dict[str, Any],
    verified_by: str,
) -> dict[str, Any]:
    rtw_status = verification.get("rtw_status", "pending")
    expiry = verification.get("expiry_date")
    expiry_date = date.fromisoformat(expiry) if expiry else None
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO employee_sponsor_profiles (
              tenant_id, employee_id, is_sponsored_worker, share_code,
              visa_expiry_date, rtw_status, updated_at
            )
            VALUES (%s, %s, TRUE, %s, %s, %s, NOW())
            ON CONFLICT (tenant_id, employee_id) DO UPDATE SET
              share_code = EXCLUDED.share_code,
              visa_expiry_date = COALESCE(EXCLUDED.visa_expiry_date, employee_sponsor_profiles.visa_expiry_date),
              rtw_status = EXCLUDED.rtw_status,
              is_sponsored_worker = TRUE,
              updated_at = NOW()
            """,
            (tenant_id, employee_id, share_code, expiry_date, rtw_status),
        )
        cur.execute(
            """
            UPDATE employees SET is_sponsored = TRUE, updated_at = NOW()
            WHERE tenant_id = %s AND id = %s
            """,
            (tenant_id, employee_id),
        )
        cur.execute(
            """
            INSERT INTO compliance_audit_events (tenant_id, event_type, entity_type, entity_id, payload)
            VALUES (%s, 'idsp_rtw_verification', 'employee', %s, %s::jsonb)
            """,
            (
                tenant_id,
                employee_id,
                {
                    "share_code": share_code,
                    "rtw_status": rtw_status,
                    "expiry_date": expiry,
                    "mode": verification.get("mode"),
                    "provider_reference": verification.get("provider_reference"),
                    "verified_by": verified_by,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                },
            ),
        )
    conn.commit()
    return {
        "employee_id": employee_id,
        "rtw_status": rtw_status,
        "expiry_date": expiry,
        "provider_reference": verification.get("provider_reference"),
        "mode": verification.get("mode"),
        "message": verification.get("message"),
    }
