"""Public signup flow — create tenant and auto-provision billing."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from auth_service import AuthUser, create_token_pair, hash_password, log_security_event
from billing_plans import get_plan
from billing_promotions import validate_promotions
from billing_stripe_service import provision_tenant_billing
from config import load_settings
from contracts_service import generate_contract_pack
from deps import client_ip
from payroll_plans import get_payroll_plan

router = APIRouter(prefix="/signup", tags=["Signup"])


class SignupStartRequest(BaseModel):
    business_name: str = Field(min_length=2, max_length=200)
    billing_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=256)
    plan_id: str
    payroll_plan_id: str | None = Field(default=None, max_length=64)
    vat_number: str | None = Field(default=None, max_length=32)
    start_trial: bool = True
    discount_code: str | None = Field(default=None, max_length=64)
    referral_code: str | None = Field(default=None, max_length=64)


def _validate_payroll_for_platform(platform_plan, payroll_plan_id: str | None):
    if not payroll_plan_id:
        return None
    payroll_plan = get_payroll_plan(payroll_plan_id)
    if not payroll_plan:
        raise HTTPException(status_code=404, detail="Unknown payroll plan")
    if payroll_plan.max_employees < platform_plan.max_employees:
        raise HTTPException(
            status_code=400,
            detail="Payroll plan must cover at least as many employees as your platform plan.",
        )
    return payroll_plan


def _db_conn() -> Any:
    import psycopg2

    url = os.getenv("DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
    return psycopg2.connect(url)


def _create_hr_admin_user(conn: Any, tenant_id: int, username: str, password: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app_users (username, password_hash, role, tenant_id, login_portal)
            VALUES (%s, %s, 'hr', %s, 'business')
            ON CONFLICT (username) DO UPDATE SET
              password_hash = EXCLUDED.password_hash,
              role = EXCLUDED.role,
              tenant_id = EXCLUDED.tenant_id,
              login_portal = EXCLUDED.login_portal,
              is_active = TRUE,
              updated_at = NOW()
            """,
            (username.lower(), hash_password(password), tenant_id),
        )


@router.post("/start")
def signup_start(payload: SignupStartRequest, request: Request) -> dict[str, object]:
    settings = load_settings()
    plan = get_plan(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Unknown subscription plan")

    payroll_plan = _validate_payroll_for_platform(plan, payload.payroll_plan_id)

    promotion = validate_promotions(
        plan_id=plan.id,
        base_price_gbp=plan.price_gbp_ex_vat,
        discount_code=payload.discount_code,
        referral_code=payload.referral_code,
    )
    if not promotion.valid:
        raise HTTPException(status_code=400, detail=promotion.message)

    ip = client_ip(request)
    user_agent = request.headers.get("User-Agent")

    conn = _db_conn()
    tenant_id: int
    billing_info: dict[str, object]
    contracts_created: list[dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (
                  name, billing_email, vat_number, subscription_plan,
                  subscription_status, max_employees, platform,
                  discount_code, referral_code, payroll_plan_id, payroll_enabled
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'hr', %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    payload.business_name.strip(),
                    payload.billing_email,
                    payload.vat_number,
                    plan.id,
                    "provisioning",
                    plan.max_employees,
                    promotion.discount_code,
                    promotion.referral_code,
                    payroll_plan.id if payroll_plan else None,
                    bool(payroll_plan),
                ),
            )
            tenant_id = int(cur.fetchone()[0])

        admin_username = str(payload.billing_email).strip().lower()
        _create_hr_admin_user(conn, tenant_id, admin_username, payload.admin_password)

        billing_info = provision_tenant_billing(
            conn=conn,
            tenant_id=tenant_id,
            business_name=payload.business_name.strip(),
            billing_email=payload.billing_email,
            plan=plan,
            start_trial=payload.start_trial,
            promotion=promotion,
            vat_number=payload.vat_number,
            payroll_plan=payroll_plan,
        )
        contracts_created = generate_contract_pack(
            conn,
            tenant_id=tenant_id,
            customer_legal_name=payload.business_name.strip(),
            signatory_email=str(payload.billing_email),
            vat_number=payload.vat_number,
            plan_id=plan.id,
            plan_name=plan.name,
            plan_price_gbp_ex_vat=plan.price_gbp_ex_vat,
            max_employees=plan.max_employees,
            billing_interval=plan.billing_interval,
            payroll_plan_id=payroll_plan.id if payroll_plan else None,
            payroll_plan_name=payroll_plan.name if payroll_plan else None,
            payroll_price_gbp_ex_vat=payroll_plan.price_gbp_ex_vat if payroll_plan else None,
            created_by="signup",
        )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=502, detail="Billing setup failed") from exc
    finally:
        conn.close()

    contracts_count = len(contracts_created)

    log_security_event(
        settings,
        event_type="signup_started",
        username=payload.billing_email,
        tenant_id=str(tenant_id),
        ip_address=ip,
        user_agent=user_agent,
        success=True,
        detail=f"plan={plan.id} payroll={payroll_plan.id if payroll_plan else 'none'} billing_auto=1",
    )

    trial_user = AuthUser(
        username=str(payload.billing_email).strip().lower(),
        role="hr",
        tenant_id=str(tenant_id),
    )
    tokens = create_token_pair(settings, trial_user)

    adjusted_price = round(plan.price_gbp_ex_vat - promotion.discount_amount_gbp, 2)
    payroll_price = payroll_plan.price_gbp_ex_vat if payroll_plan else 0
    total_price = round(max(adjusted_price, 0) + payroll_price, 2)

    return {
        "tenant_id": tenant_id,
        "plan_id": plan.id,
        "plan_name": plan.name,
        "payroll_plan_id": payroll_plan.id if payroll_plan else None,
        "payroll_plan_name": payroll_plan.name if payroll_plan else None,
        "payroll_enabled": bool(payroll_plan),
        "subscription_status": billing_info.get("subscription_status"),
        "billing_auto_created": billing_info.get("billing_auto_created", True),
        "stripe_customer_id": billing_info.get("stripe_customer_id"),
        "stripe_subscription_id": billing_info.get("stripe_subscription_id"),
        "trial_days": billing_info.get("trial_days"),
        "trial_ends_at": billing_info.get("trial_ends_at"),
        "checkout_url": billing_info.get("checkout_url"),
        "promotion_message": promotion.message,
        "discount_applied_gbp": promotion.discount_amount_gbp,
        "price_gbp_ex_vat": plan.price_gbp_ex_vat,
        "payroll_price_gbp_ex_vat": payroll_price if payroll_plan else None,
        "adjusted_price_gbp_ex_vat": max(adjusted_price, 0),
        "total_price_gbp_ex_vat": total_price,
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "tenant_id_token": tokens.tenant_id,
        "contracts_generated": contracts_count,
        "message": "Workspace, billing, and legal contract drafts created automatically.",
    }
