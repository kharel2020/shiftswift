"""Grievance case constants — allegation types, severity, status workflow."""

from __future__ import annotations

ALLEGATION_TYPES = [
    {"value": "harassment", "label": "Harassment"},
    {"value": "discrimination", "label": "Discrimination"},
    {"value": "pay_dispute", "label": "Pay dispute"},
    {"value": "bullying", "label": "Bullying"},
    {"value": "unfair_treatment", "label": "Unfair treatment"},
    {"value": "working_conditions", "label": "Working conditions"},
    {"value": "whistleblowing", "label": "Whistleblowing"},
    {"value": "other", "label": "Other — describe"},
]

SEVERITY_LEVELS = [
    {"value": "low", "label": "Low"},
    {"value": "medium", "label": "Medium"},
    {"value": "high", "label": "High"},
    {"value": "critical", "label": "Critical"},
]

STATUS_WORKFLOW = [
    {"value": "open", "label": "Open"},
    {"value": "investigating", "label": "Investigating"},
    {"value": "acas", "label": "ACAS"},
    {"value": "resolved", "label": "Resolved"},
]

STATUS_LABELS = {
    "investigation": "Investigating",
    "hearing": "ACAS conciliation",
    "appeal": "Appeal",
    "closed": "Resolved",
}

ALLEGATION_LABELS = {item["value"]: item["label"] for item in ALLEGATION_TYPES}
