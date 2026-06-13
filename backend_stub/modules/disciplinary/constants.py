"""Disciplinary case constants — misconduct types, severity, status workflow."""

from __future__ import annotations

MISCONDUCT_TYPES = [
    {"value": "misconduct", "label": "General misconduct"},
    {"value": "attendance", "label": "Attendance / punctuality"},
    {"value": "performance", "label": "Performance"},
    {"value": "theft", "label": "Theft / dishonesty"},
    {"value": "safety", "label": "Health & safety breach"},
    {"value": "other", "label": "Other — describe"},
]

SEVERITY_LEVELS = [
    {"value": "low", "label": "Low"},
    {"value": "medium", "label": "Medium"},
    {"value": "high", "label": "High"},
    {"value": "critical", "label": "Critical"},
]

STATUS_WORKFLOW = [
    {"value": "investigation", "label": "Investigation"},
    {"value": "hearing", "label": "Disciplinary hearing"},
    {"value": "appeal", "label": "Appeal"},
    {"value": "closed", "label": "Closed"},
]

STATUS_LABELS = {
    "investigation": "Investigating",
    "hearing": "Disciplinary hearing",
    "appeal": "Appeal",
    "closed": "Closed",
}

MISCONDUCT_LABELS = {item["value"]: item["label"] for item in MISCONDUCT_TYPES}

CLOSE_OUTCOMES = [
    {"value": "no_action", "label": "No further action"},
    {"value": "written_warning", "label": "Written warning"},
    {"value": "final_warning", "label": "Final written warning"},
    {"value": "dismissal", "label": "Dismissal"},
    {"value": "withdrawn", "label": "Withdrawn"},
]
