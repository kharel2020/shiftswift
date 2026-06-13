"""Document store constants — categories, lifecycle stages, requirements."""

from __future__ import annotations

DOCUMENT_LIFECYCLE_STAGES = [
    {"value": "recruitment", "label": "Recruitment"},
    {"value": "onboarding", "label": "On-boarding"},
    {"value": "induction", "label": "Personal information"},
    {"value": "document_store", "label": "Document store"},
    {"value": "compliance", "label": "Compliance"},
    {"value": "offboarding", "label": "Off-boarding"},
    {"value": "general", "label": "General"},
    {"value": "policy", "label": "Policy (tenant-wide)"},
]

TENANT_DOCUMENT_CATEGORIES = [
    {"value": "general", "label": "General"},
    {"value": "policy", "label": "Policy & handbook"},
    {"value": "contract", "label": "Employment contract template"},
    {"value": "rtw", "label": "Right to work"},
    {"value": "payroll", "label": "Payroll"},
    {"value": "disciplinary", "label": "Disciplinary"},
    {"value": "other", "label": "Other"},
]

EMPLOYEE_DOCUMENT_CATEGORIES = [
    {"value": "contract", "label": "Employment contract"},
    {"value": "payslip", "label": "Payslip"},
    {"value": "id", "label": "ID / passport"},
    {"value": "rtw", "label": "Right to work"},
    {"value": "qualification", "label": "Qualification"},
    {"value": "policy", "label": "Signed policy / handbook"},
    {"value": "disciplinary", "label": "Disciplinary"},
    {"value": "general", "label": "General"},
    {"value": "other", "label": "Other"},
]

# Categories visible in the employee self-service portal (HR-only docs such as RTW copies stay admin-only).
EMPLOYEE_SELF_SERVICE_CATEGORIES = frozenset(
    {"contract", "policy", "general", "qualification", "payslip", "other"}
)

EMPLOYEE_DOCUMENT_CATEGORY_LABELS = {item["value"]: item["label"] for item in EMPLOYEE_DOCUMENT_CATEGORIES}

EMPLOYEE_DOCUMENT_REQUIREMENTS = {
    "standard": (
        {"category": "contract", "label": "Signed employment contract", "required": True},
        {"category": "id", "label": "Photo ID or passport copy", "required": True},
        {"category": "policy", "label": "Handbook / H&S acknowledgement", "required": False},
    ),
    "sponsored": (
        {"category": "contract", "label": "Signed employment contract", "required": True},
        {"category": "id", "label": "Photo ID or passport copy", "required": True},
        {"category": "rtw", "label": "Right to work evidence", "required": True},
        {"category": "policy", "label": "Handbook / H&S acknowledgement", "required": False},
    ),
}

VALID_EMPLOYEE_CATEGORIES = frozenset(item["value"] for item in EMPLOYEE_DOCUMENT_CATEGORIES)
VALID_TENANT_CATEGORIES = frozenset(item["value"] for item in TENANT_DOCUMENT_CATEGORIES)
VALID_LIFECYCLE_STAGES = frozenset(item["value"] for item in DOCUMENT_LIFECYCLE_STAGES)
