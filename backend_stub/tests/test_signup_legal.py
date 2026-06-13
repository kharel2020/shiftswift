from __future__ import annotations

import pytest
from fastapi import HTTPException

from legal_acceptance import validate_signup_legal_acceptances


def test_validate_signup_legal_acceptances_requires_all_boxes() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_signup_legal_acceptances(
            accept_eula=False,
            accept_payment_terms=True,
            accept_dpa=True,
            accept_service_scope=True,
            holds_sponsor_licence=False,
            sponsor_licence_acknowledged=False,
        )
    assert exc.value.status_code == 400
    assert "EULA" in str(exc.value.detail)


def test_validate_signup_legal_acceptances_ok() -> None:
    validate_signup_legal_acceptances(
        accept_eula=True,
        accept_payment_terms=True,
        accept_dpa=True,
        accept_service_scope=True,
        holds_sponsor_licence=False,
        sponsor_licence_acknowledged=False,
    )
