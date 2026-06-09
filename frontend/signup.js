const API_BASE =
  (window.ShiftSwiftBrand?.resolveApiBase && window.ShiftSwiftBrand.resolveApiBase()) ||
  localStorage.getItem("apiBaseUrl") ||
  "http://localhost:3000";

let currentPlanId = "site_starter_monthly";
let currentPayrollPlanId = null;

function parsePromoCode(raw) {
  const code = String(raw || "").trim();
  if (!code) return { discount_code: null, referral_code: null };
  if (/^ref[-_]/i.test(code)) return { discount_code: null, referral_code: code };
  return { discount_code: code, referral_code: null };
}

function readUrlPromos() {
  const params = new URLSearchParams(window.location.search);
  const discount = params.get("discount") || params.get("promo");
  const referral = params.get("ref") || params.get("referral");
  const promoInput = document.getElementById("promo-code");
  if (!promoInput) return;
  if (discount) promoInput.value = discount;
  else if (referral) promoInput.value = referral;
}

async function applyPromoCodes() {
  const planId = document.getElementById("selected-plan-id")?.value || currentPlanId;
  const promoInput = document.getElementById("promo-code");
  const { discount_code, referral_code } = parsePromoCode(promoInput?.value);
  const promoMessage = document.getElementById("promo-message");

  if (!discount_code && !referral_code) {
    if (promoMessage) promoMessage.textContent = "";
    window.ShiftSwiftPricing?.refreshSummary?.(planId);
    return;
  }

  if (promoMessage) promoMessage.textContent = "Checking code…";

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
    const priceLine = document.getElementById("signup-summary-price");
    if (priceLine && data.adjusted_price_gbp_ex_vat != null) {
      priceLine.textContent = `£${data.adjusted_price_gbp_ex_vat} + VAT after discount · selected plan`;
    }
    if (data.extra_trial_days && promoMessage) {
      promoMessage.textContent += ` · +${data.extra_trial_days} extra trial days`;
    }
  } catch (error) {
    if (promoMessage) {
      promoMessage.textContent = error.message;
      promoMessage.classList.add("muted");
      promoMessage.classList.remove("promo-success");
    }
  }
}

function initSignupUi() {
  const vatToggle = document.getElementById("vat-toggle");
  const vatWrap = document.getElementById("vat-field-wrap");
  vatToggle?.addEventListener("click", () => {
    const open = vatWrap?.hidden !== false;
    if (vatWrap) vatWrap.hidden = !open;
    vatToggle.setAttribute("aria-expanded", open ? "true" : "false");
    vatToggle.textContent = open ? "− Hide VAT number" : "+ Add VAT number";
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  initSignupUi();
  readUrlPromos();
  const result = await window.ShiftSwiftPricing?.initSignup("signup-pricing-plans", "signup-payroll-plans");
  if (result?.selectedPlanId) currentPlanId = result.selectedPlanId;
  if (result?.selectedPayrollPlanId) currentPayrollPlanId = result.selectedPayrollPlanId;

  document.getElementById("apply-promo-btn")?.addEventListener("click", applyPromoCodes);
  if (document.getElementById("promo-code")?.value) applyPromoCodes();
});

document.getElementById("signup-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = document.getElementById("signup-status");
  const form = event.currentTarget;
  const planId = document.getElementById("selected-plan-id")?.value || currentPlanId;
  const payrollPlanId = document.getElementById("selected-payroll-plan-id")?.value.trim() || null;

  if (!planId) {
    if (status) status.textContent = "Please select an HR plan.";
    return;
  }

  const password = form.admin_password.value;
  const confirm = form.admin_password_confirm.value;
  if (password.length < 8) {
    if (status) status.textContent = "Password must be at least 8 characters.";
    return;
  }
  if (password !== confirm) {
    if (status) status.textContent = "Passwords do not match.";
    return;
  }

  const { discount_code, referral_code } = parsePromoCode(form.promo_code?.value);

  const payload = {
    business_name: form.business_name.value.trim(),
    billing_email: form.billing_email.value.trim(),
    admin_password: password,
    plan_id: planId,
    payroll_plan_id: payrollPlanId || null,
    vat_number: form.vat_number?.value.trim() || null,
    start_trial: form.start_trial.checked,
    discount_code,
    referral_code,
  };

  if (status) status.textContent = "Creating your workspace…";

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
