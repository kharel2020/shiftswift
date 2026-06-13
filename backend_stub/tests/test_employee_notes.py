from __future__ import annotations

import pytest

from modules.employee_notes.service import VISIBILITY_CHOICES, _normalize_body, _read_body, _store_body


def test_normalize_body_requires_text() -> None:
    with pytest.raises(ValueError, match="required"):
        _normalize_body("   ")


def test_normalize_body_enforces_max_length() -> None:
    with pytest.raises(ValueError, match="4000"):
        _normalize_body("x" * 4001)


def test_store_and_read_employee_visible_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    stored = _store_body(body="Please bring your P45.", visibility="employee_visible")
    assert stored == "Please bring your P45."
    assert _read_body(stored=stored, visibility="employee_visible") == "Please bring your P45."


def test_store_hr_internal_requires_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        _store_body(body="Sensitive HR note", visibility="hr_internal")


def test_visibility_choices() -> None:
    assert VISIBILITY_CHOICES == frozenset({"hr_internal", "employee_visible"})
