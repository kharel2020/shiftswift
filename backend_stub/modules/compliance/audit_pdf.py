"""Generate Home Office audit pack as PDF."""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modules.compliance.audit_export import build_audit_export


def audit_export_pdf_bytes(*, tenant_id: int, employee_id: int | None, conn: Any) -> bytes:
    pack = build_audit_export(tenant_id=tenant_id, employee_id=employee_id, conn=conn)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"ShiftSwift HR Audit Pack — Tenant {tenant_id}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AuditTitle",
        parent=styles["Heading1"],
        textColor=colors.HexColor("#0F6E56"),
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "AuditSection",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#0F6E56"),
        spaceBefore=14,
        spaceAfter=8,
    )
    body = [
        Paragraph("ShiftSwift HR — Sponsor Licence Audit Pack", title_style),
        Paragraph(
            f"Tenant {pack['tenant_id']} · Generated {pack['generated_on']}"
            + (f" · Employee #{pack['employee_id']}" if pack.get("employee_id") else " · All employees"),
            styles["Normal"],
        ),
        Spacer(1, 8),
        Paragraph(
            f"Summary: {pack['summary']['rtw_checks']} RTW checks, "
            f"{pack['summary']['sms_changes']} SMS changes, "
            f"{pack['summary']['absence_alerts']} absence alerts, "
            f"{pack['summary']['reporting_triggers']} reporting triggers.",
            styles["Normal"],
        ),
    ]

    sections = [
        ("Right to Work checks", pack["sections"].get("right_to_work_checks", [])),
        ("SMS change log", pack["sections"].get("sms_change_log", [])),
        ("Absence alerts", pack["sections"].get("absence_alerts", [])),
        ("Recruitment adverts", pack["sections"].get("advertisement_records", [])),
        ("Reporting triggers", pack["sections"].get("reporting_triggers", [])),
    ]

    for title, rows in sections:
        body.append(Paragraph(title, section_style))
        if not rows:
            body.append(Paragraph("No records.", styles["Italic"]))
            continue
        keys = list(rows[0].keys())[:5]
        table_data = [keys] + [[str(row.get(k, "—"))[:48] for k in keys] for row in rows[:25]]
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F5F0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F6E56")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        body.append(table)
        if len(rows) > 25:
            body.append(Paragraph(f"… and {len(rows) - 25} more rows (see JSON export).", styles["Italic"]))

    doc.build(body)
    return buffer.getvalue()
