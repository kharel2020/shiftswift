from __future__ import annotations

from plan_features import effective_features_for_tenant, features_for_plan


def test_starter_plan_hides_growth_features() -> None:
    feats = features_for_plan("site_starter_monthly", payroll_enabled=False)
    assert feats["payroll_enabled"] is False
    assert feats["grievance_enabled"] is False
    assert feats["sponsor_compliance_enabled"] is False


def test_trial_unlocks_growth_features_on_starter() -> None:
    feats = effective_features_for_tenant(
        plan_id="site_starter_monthly",
        payroll_enabled=False,
        subscription_status="trialing",
        trial_access_allowed=True,
    )
    assert feats["trial_active"] is True
    assert feats["grievance_enabled"] is True
    assert feats["sponsor_compliance_enabled"] is True
    assert feats["payroll_enabled"] is False
