"""Legal agreement versions and signup acceptance audit."""

from __future__ import annotations

from typing import Any

EULA_VERSION = "2026-06-08"
PAYMENT_TERMS_VERSION = "2026-06-09"
DPA_VERSION = "2026-06-08"


def validate_signup_legal_acceptances(
    *,
    accept_eula: bool,
    accept_payment_terms: bool,
    accept_dpa: bool,
    accept_service_scope: bool,
    holds_sponsor_licence: bool,
    sponsor_licence_acknowledged: bool,
) -> None:
    from fastapi import HTTPException

    if not accept_service_scope:
        raise HTTPException(
            status_code=400,
            detail="Please confirm you have read what ShiftSwift HR provides and your organisation's responsibilities.",
        )
    if not accept_eula:
        raise HTTPException(status_code=400, detail="Please accept the HR Module EULA to create an account.")
    if not accept_payment_terms:
        raise HTTPException(status_code=400, detail="Please accept the B2B payment terms to create an account.")
    if not accept_dpa:
        raise HTTPException(
            status_code=400,
            detail="Please accept the Data Processing Addendum and privacy policy to create an account.",
        )
    if sponsor_licence_acknowledged and not holds_sponsor_licence:
        raise HTTPException(
            status_code=400,
            detail="Confirm your organisation holds a UK Sponsor Licence before accepting sponsor duty terms.",
        )


def record_signup_acceptance(
    *,
    conn: Any,
    tenant_id: int,
    accept_eula: bool,
    accept_payment_terms: bool,
    accept_dpa: bool,
    accept_service_scope: bool,
    holds_sponsor_licence: bool,
    sponsor_licence_acknowledged: bool,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tenant_signup_acceptances (
              tenant_id, accepted_eula, accepted_payment_terms, accepted_dpa,
              accepted_service_scope, eula_version, payment_terms_version, dpa_version,
              holds_sponsor_licence, sponsor_licence_acknowledged, ip_address, user_agent
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_id,
                accept_eula,
                accept_payment_terms,
                accept_dpa,
                accept_service_scope,
                EULA_VERSION,
                PAYMENT_TERMS_VERSION,
                DPA_VERSION,
                holds_sponsor_licence,
                sponsor_licence_acknowledged,
                ip_address,
                user_agent,
            ),
        )
