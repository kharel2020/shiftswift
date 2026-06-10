from __future__ import annotations

import os

from core.notifications import format_from_header


def test_format_from_header_uses_platform_name(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_FROM", "noreply@shiftswifthr.co.uk")
    monkeypatch.setenv("SMTP_FROM_NAME", "ShiftSwift HR")
    header = format_from_header(audience="employee")
    assert header == "ShiftSwift HR <noreply@shiftswifthr.co.uk>"


def test_format_from_header_hr_same_platform_name(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_FROM", "noreply@shiftswifthr.co.uk")
    monkeypatch.setenv("SMTP_FROM_NAME", "ShiftSwift HR")
    header = format_from_header(audience="hr")
    assert "ShiftSwift HR" in header
    assert "noreply@shiftswifthr.co.uk" in header
    assert "Acme" not in header
