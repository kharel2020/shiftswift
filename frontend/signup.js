const API_BASE = localStorage.getItem("apiBaseUrl") || "http://localhost:3000";

let currentPlanId = "site_starter_monthly";
let currentPayrollPlanId = null;

function readUrlPromos() {
  const params = new URLSearchParams(window.location.search);
  const discount = params.get("discount") || params.get("promo");
  const referral = params.get("ref") || params.get("referral");
  if (discount) document.getElementById("discount-code").value = discount;
  if (referral) document.getElementById("referral-code").value = referral;
}

async function applyPromoCodes() {
  const planId = document.getElementById("selected-plan-id")?.value || currentPlanId;
  const discount_code = document.getElementById("discount-code")?.value.trim() || null;
  const referral_code = document.getElementById("referral-code")?.value.trim() || null;
  const promoMessage = document.getElementById("promo-message");
  const summaryPrice = document.querySelector(".signup-summary-price");

  if (!discount_code && !referral_code) {
    if (promoMessage) promoMessage.textContent = "";
    window.ShiftSwiftPricing?.refreshSummary?.(planId);
    return;
  }

  if (promoMessage) promoMessage.textContent = "Checking codes…";

  try {
    const res = await fetch(`${API_BASE}/billing/validate-promo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan_id: planId, discount_code, referral_code }),
    });
    const data = await res.json();
    if (!res.ok || !data.valid) throw new Error(data.message || data.detail || "Invalid code");

    if (promoMessage) {
      promoMessage.textContent = `${data.message} · £${data.adjusted_price_gbp_ex_vat} + VAT after discount`;
      promoMessage.classList.remove("muted");
      promoMessage.classList.add("promo-success");
    }
    if (summaryPrice && data.adjusted_price_gbp_ex_vat != null) {
      summaryPrice.textContent = `£${data.adjusted_price_gbp_ex_vat} + VAT after discount · up to selected staff cap`;
    }
    if (data.extra_trial_days) {
      if (promoMessage) {
        promoMessage.textContent += ` · +${data.extra_trial_days} extra trial days`;
      }
    }
  } catch (error) {
    if (promoMessage) {
      promoMessage.textContent = error.message;
      promoMessage.classList.add("muted");
      promoMessage.classList.remove("promo-success");
    }
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  readUrlPromos();
  const result = await window.ShiftSwiftPricing?.initSignup("signup-pricing-plans", "signup-payroll-plans");
  if (result?.selectedPlanId) currentPlanId = result.selectedPlanId;
  if (result?.selectedPayrollPlanId) currentPayrollPlanId = result.selectedPayrollPlanId;

  document.getElementById("apply-promo-btn")?.addEventListener("click", applyPromoCodes);
  if (document.getElementById("discount-code")?.value || document.getElementById("referral-code")?.value) {
    applyPromoCodes();
  }
});

document.getElementById("signup-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = document.getElementById("signup-status");
  const form = event.currentTarget;
  const planId = document.getElementById("selected-plan-id")?.value || currentPlanId;
  const payrollPlanId = document.getElementById("selected-payroll-plan-id")?.value.trim() || null;
  if (!planId) {
    if (status) status.textContent = "Please select a subscription plan.";
    return;
  }

  const payload = {
    business_name: form.business_name.value.trim(),
    billing_email: form.billing_email.value.trim(),
    plan_id: planId,
    payroll_plan_id: payrollPlanId || null,
    vat_number: form.vat_number.value.trim() || null,
    start_trial: form.start_trial.checked,
    discount_code: form.discount_code?.value.trim() || null,
    referral_code: form.referral_code?.value.trim() || null,
  };

  if (status) status.textContent = "Creating workspace and billing…";

  try {
    const res = await fetch(`${API_BASE}/signup/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Signup failed");

    localStorage.setItem("token", data.access_token);
    localStorage.setItem("refreshToken", data.refresh_token);
    localStorage.setItem("tenantId", String(data.tenant_id));
    localStorage.setItem("businessName", payload.business_name);
    localStorage.setItem("subscriptionPlan", data.plan_id);
    if (data.payroll_plan_id) localStorage.setItem("payrollPlan", data.payroll_plan_id);

    if (data.checkout_url) {
      window.location.href = data.checkout_url;
      return;
    }

    window.location.href = `./signup-success.html?tenant=${data.tenant_id}&plan=${encodeURIComponent(data.plan_id)}`;
  } catch (error) {
    if (status) status.textContent = error.message;
  }
});
