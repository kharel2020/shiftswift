"""Monthly working hours PDF for accountants."""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modules.payroll_export.service import build_hours_report


def hours_report_pdf_bytes(
    *,
    tenant_id: int,
    conn: Any,
    from_date: Any = None,
    to_date: Any = None,
) -> bytes:
    report = build_hours_report(
        tenant_id=tenant_id,
        conn=conn,
        from_date=from_date,
        to_date=to_date,
    )
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Working Hours — {report['tenant_name']}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "HoursTitle",
        parent=styles["Heading1"],
        textColor=colors.HexColor("#0F6E56"),
        spaceAfter=8,
        fontSize=16,
    )
    section_style = ParagraphStyle(
        "HoursSection",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#0F6E56"),
        spaceBefore=10,
        spaceAfter=6,
        fontSize=11,
    )
    small = ParagraphStyle("HoursSmall", parent=styles["Normal"], fontSize=8, leading=10)

    body: list[Any] = [
        Paragraph("ShiftSwift HR — Working Hours Report", title_style),
        Paragraph(
            f"<b>{report['tenant_name']}</b><br/>"
            f"Period: {report['from_date']} to {report['to_date']} (UK)<br/>"
            f"Generated: {report['generated_at']}",
            styles["Normal"],
        ),
        Spacer(1, 6),
        Paragraph(f"<b>How hours are calculated:</b> {report['methodology']}", small),
        Spacer(1, 8),
    ]

    if not report["employees"]:
        body.append(Paragraph("No clock-in/out records found for this period.", styles["Italic"]))
        doc.build(body)
        return buffer.getvalue()

    summary_data = [
        ["Employee", "Days worked", "Incomplete days", "Total hours"],
    ]
    for employee in report["employees"]:
        summary_data.append(
            [
                employee["name"] or f"Employee #{employee['employee_id']}",
                str(employee["days_worked"]),
                str(employee["incomplete_days"]),
                f"{employee['total_hours']:.2f}",
            ]
        )
    summary_data.append(["All employees", "", "", f"{report['grand_total_hours']:.2f}"])

    summary_table = Table(summary_data, repeatRows=1, colWidths=[90 * mm, 28 * mm, 32 * mm, 28 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F5F0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F6E56")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    body.append(Paragraph("Summary for accountant", section_style))
    body.append(summary_table)

    for index, employee in enumerate(report["employees"]):
        if index > 0:
            body.append(PageBreak())
        body.append(
            Paragraph(
                f"{employee['name'] or 'Employee'} — detail (ID {employee['employee_id']})",
                section_style,
            )
        )
        detail_data = [["Date", "Clock in", "Clock out", "Hours", "Status"]]
        for row in employee["rows"]:
            hours_label = "" if row["hours"] is None else f"{row['hours']:.2f}"
            status_label = "Complete" if row["status"] == "complete" else "Incomplete"
            detail_data.append(
                [
                    row["date"],
                    row["clock_in"] or "—",
                    row["clock_out"] or "—",
                    hours_label or "—",
                    status_label,
                ]
            )
        detail_data.append(["", "", "Employee total", f"{employee['total_hours']:.2f}", ""])
        detail_table = Table(
            detail_data,
            repeatRows=1,
            colWidths=[32 * mm, 24 * mm, 24 * mm, 24 * mm, 28 * mm],
        )
        detail_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F5F0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("TEXTCOLOR", (4, 1), (4, -2), colors.HexColor("#555555")),
                ]
            )
        )
        body.append(detail_table)

    doc.build(body)
    return buffer.getvalue()
