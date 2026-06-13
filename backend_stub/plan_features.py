"""Subscription tier feature flags — aligned to ShiftSwift HR strategy pricing."""

from __future__ import annotations

from typing import Any

STARTER_PLAN_IDS = frozenset({"site_starter_monthly", "site_starter_annual"})
GROWTH_PLAN_IDS = frozenset({"site_medium_monthly", "site_medium_annual"})
SCALE_PLAN_IDS = frozenset({"site_growth_monthly", "site_growth_annual"})

TIER_LABELS = {
    "starter": "Starter",
    "growth": "Growth",
    "scale": "Scale",
}


def plan_tier(plan_id: str | None) -> str:
    pid = (plan_id or "").strip()
    if pid in SCALE_PLAN_IDS or pid.startswith("enterprise"):
        return "scale"
    if pid in GROWTH_PLAN_IDS:
        return "growth"
    return "starter"


def plan_display_name(plan_id: str | None) -> str:
    return TIER_LABELS.get(plan_tier(plan_id), "Starter")


def features_for_plan(
    plan_id: str | None,
    *,
    payroll_enabled: bool,
    sponsored_employees: int = 0,
    trial_active: bool = False,
) -> dict[str, object]:
    tier = plan_tier(plan_id)
    growth_plus = tier in ("growth", "scale")
    if trial_active:
        growth_plus = True
    return {
        "plan_tier": tier,
        "plan_display_name": plan_display_name(plan_id),
        "payroll_enabled": False,
        "trial_active": bool(trial_active),
        "sponsor_compliance_enabled": growth_plus,
        "grievance_enabled": growth_plus,
        "disciplinary_enabled": growth_plus,
        "audit_export_enabled": growth_plus,
        "multi_site_enabled": tier == "scale",
        "api_access_enabled": tier == "scale",
        "sponsored_employees": sponsored_employees,
    }


def effective_features_for_tenant(
    *,
    plan_id: str | None,
    payroll_enabled: bool,
    sponsored_employees: int = 0,
    subscription_status: str | None = None,
    trial_access_allowed: bool = False,
) -> dict[str, object]:
    """Plan flags with active trial unlocking Growth-tier HR modules."""
    status = (subscription_status or "").strip().lower()
    trial_active = trial_access_allowed and status in {"trialing", "provisioning"}
    return features_for_plan(
        plan_id,
        payroll_enabled=payroll_enabled,
        sponsored_employees=sponsored_employees,
        trial_active=trial_active,
    )


def assert_tenant_feature(
    *,
    tenant_id: int,
    feature: str,
    conn: Any,
) -> None:
    """Raise HTTPException 403 when tenant plan (or trial) does not include a feature."""
    from admin_service import get_tenant_profile
    from trial_service import trial_snapshot

    profile = get_tenant_profile(tenant_id=tenant_id, conn=conn)
    trial = trial_snapshot(tenant_id=tenant_id, conn=conn)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM employees WHERE tenant_id = %s AND is_sponsored = TRUE",
            (tenant_id,),
        )
        sponsored_employees = int(cur.fetchone()[0])
    feats = effective_features_for_tenant(
        plan_id=profile["subscription_plan"],
        payroll_enabled=bool(profile["payroll_enabled"]),
        sponsored_employees=sponsored_employees,
        subscription_status=profile.get("subscription_status"),
        trial_access_allowed=bool(trial.get("access_allowed")),
    )
    flag = f"{feature}_enabled"
    if feats.get(flag):
        return
    from fastapi import HTTPException

    raise HTTPException(
        status_code=403,
        detail=UPGRADE_MESSAGES.get(feature, "Upgrade your plan to use this feature."),
    )


UPGRADE_MESSAGES = {
    "payroll": "Staff CSV export is not available on your plan yet.",
    "grievance": "Grievance workflows are included on Growth and Scale plans.",
    "disciplinary": "Disciplinary workflows are included on Growth and Scale plans.",
    "audit_export": "Home Office audit export is included on Growth and Scale plans.",
    "sponsor_compliance": "Sponsor licence compliance is included on Growth and Scale plans.",
    "multi_site": "Multi-site dashboard is included on Scale plans.",
    "api_access": "API access is included on Scale plans.",
}


def assert_plan_feature(
    plan_id: str | None,
    feature: str,
    *,
    payroll_enabled: bool = False,
) -> None:
    """Raise HTTPException 403 when the tenant plan does not include a feature."""
    from fastapi import HTTPException

    feats = features_for_plan(plan_id, payroll_enabled=payroll_enabled)
    flag = f"{feature}_enabled"
    if feats.get(flag):
        return
    raise HTTPException(
        status_code=403,
        detail=UPGRADE_MESSAGES.get(feature, "Upgrade your plan to use this feature."),
    )
