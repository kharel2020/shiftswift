"""Leave request types and statuses."""

from __future__ import annotations

LEAVE_TYPES = frozenset({"annual", "sick", "unpaid", "other"})
LEAVE_STATUSES = frozenset({"pending", "approved", "rejected", "cancelled"})

LEAVE_TYPE_LABELS = {
    "annual": "Annual leave",
    "sick": "Sick leave",
    "unpaid": "Unpaid leave",
    "other": "Other leave",
}
