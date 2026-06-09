/** Admin promotions — validate discount/referral codes and browse catalogs. */
(async function initAdminPromotions() {
  const { apiFetch, loadFormOptions, mountEditForm, renderTableBody, FORM_SCHEMAS, escapeHtml, statusPill, parseHashBaseSection } = window.Admin;

  let validateForm = null;

  function formatDiscount(row) {
    if (row.discount_type === "percent") return `${row.discount_value}% off`;
    return `£${row.discount_value.toFixed(2)} off`;
  }

  function formatReferralReward(row) {
    if (row.reward_type === "percent") return `${row.reward_value}% off`;
    if (row.reward_type === "trial_days") return `+${parseInt(row.reward_value, 10)} trial days`;
    return `£${row.reward_value.toFixed(2)} off`;
  }

  function formatUsage(used, max) {
    if (max == null) return `${used} used · unlimited`;
    return `${used} / ${max} used`;
  }

  function renderValidationResult(data, isError = false) {
    const panel = document.getElementById("promo-validation-result");
    if (!panel) return;
    panel.hidden = false;
    panel.classList.toggle("promo-result--error", isError);
    panel.classList.toggle("promo-result--ok", !isError && data?.valid);

    if (isError || !data?.valid) {
      panel.innerHTML = `
        <h3>Validation failed</h3>
        <p class="promo-result-message">${escapeHtml(data?.message || data?.detail || "Invalid codes")}</p>`;
      return;
    }

    const trialNote = data.extra_trial_days
      ? `<li><strong>Extra trial:</strong> +${escapeHtml(data.extra_trial_days)} days</li>`
      : "";
    const partnerNote = data.partner_name
      ? `<li><strong>Partner:</strong> ${escapeHtml(data.partner_name)}</li>`
      : "";

    panel.innerHTML = `
      <h3>Valid for billing</h3>
      <p class="promo-result-message promo-result-message--ok">${escapeHtml(data.message)}</p>
      <ul class="promo-result-list">
        <li><strong>List price:</strong> £${escapeHtml(data.price_gbp_ex_vat)} + VAT / month</li>
        <li><strong>Discount applied:</strong> £${escapeHtml(data.discount_applied_gbp)}</li>
        <li><strong>Adjusted price:</strong> £${escapeHtml(data.adjusted_price_gbp_ex_vat)} + VAT (£${escapeHtml(data.adjusted_price_gbp_inc_vat)} inc VAT)</li>
        ${trialNote}
        ${partnerNote}
      </ul>`;
  }

  function prefillValidator({ planId, discountCode, referralCode } = {}) {
    if (!validateForm) return;
    if (planId) validateForm.querySelector('[name="plan_id"]').value = planId;
    if (discountCode != null) validateForm.querySelector('[name="discount_code"]').value = discountCode;
    if (referralCode != null) validateForm.querySelector('[name="referral_code"]').value = referralCode;
    document.getElementById("promo-validation-result")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function mountPromoValidator() {
    const host = document.getElementById("promo-validate-form");
    if (!host || host.dataset.mounted === "true") return;

    let defaultPlan = "";
    try {
      await loadFormOptions();
      const statusRes = await apiFetch("/billing/status");
      if (statusRes.ok) {
        const status = await statusRes.json();
        defaultPlan = status.subscription_plan || "";
      }
    } catch {
      /* optional prefill */
    }

    validateForm = mountEditForm(host, FORM_SCHEMAS.promoValidate, {
      values: { plan_id: defaultPlan },
      onSubmit: async (payload) => {
        const discount_code = payload.discount_code?.trim() || null;
        const referral_code = payload.referral_code?.trim() || null;
        if (!discount_code && !referral_code) {
          throw new Error("Enter a discount code, referral code, or both.");
        }
        const res = await apiFetch("/billing/validate-promo", {
          method: "POST",
          body: JSON.stringify({
            plan_id: payload.plan_id,
            discount_code,
            referral_code,
          }),
        });
        const data = await res.json();
        if (!res.ok) {
          renderValidationResult(data, true);
          throw new Error(data.detail || data.message || "Validation failed");
        }
        if (!data.valid) {
          renderValidationResult(data, true);
          throw new Error(data.message || "Invalid codes");
        }
        renderValidationResult(data);
      },
    });
    host.dataset.mounted = "true";
  }

  async function loadDiscountCodes() {
    const tbody = document.getElementById("discount-codes-body");
    if (!tbody) return;
    try {
      const res = await apiFetch("/admin/billing/discount-codes");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      renderTableBody(tbody, {
        emptyMessage: "No discount codes configured. Seed the billing catalog.",
        columns: [
          { key: "code", render: (row) => `<strong>${escapeHtml(row.code)}</strong>` },
          { key: "label", render: (row) => escapeHtml(row.label || "Not set") },
          { key: "discount", render: (row) => escapeHtml(formatDiscount(row)) },
          {
            key: "plans",
            render: (row) =>
              row.applicable_plan_ids?.length
                ? escapeHtml(row.applicable_plan_ids.join(", "))
                : "<span class='muted'>All plans</span>",
          },
          { key: "usage", render: (row) => escapeHtml(formatUsage(row.redemption_count, row.max_redemptions)) },
          {
            key: "status",
            render: (row) => statusPill(row.is_active ? "active" : "inactive"),
          },
          {
            key: "actions",
            render: (row) =>
              `<button type="button" class="btn ghost" data-use-discount="${escapeHtml(row.code)}">Test</button>`,
          },
        ],
        rows: data.items || [],
      });

      tbody.querySelectorAll("[data-use-discount]").forEach((btn) => {
        btn.addEventListener("click", () => {
          prefillValidator({ discountCode: btn.dataset.useDiscount });
        });
      });
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }, { key: "f" }, { key: "g" }],
        rows: [],
        emptyMessage: "Could not load discount codes.",
      });
    }
  }

  async function loadReferralCodes() {
    const tbody = document.getElementById("referral-codes-body");
    if (!tbody) return;
    try {
      const res = await apiFetch("/admin/billing/referral-codes");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      renderTableBody(tbody, {
        emptyMessage: "No referral codes configured. Seed the billing catalog.",
        columns: [
          { key: "code", render: (row) => `<strong>${escapeHtml(row.code)}</strong>` },
          { key: "partner_name", render: (row) => escapeHtml(row.partner_name) },
          { key: "reward", render: (row) => escapeHtml(formatReferralReward(row)) },
          {
            key: "commission",
            render: (row) => `${escapeHtml(row.referrer_commission_percent)}% commission`,
          },
          { key: "usage", render: (row) => escapeHtml(formatUsage(row.use_count, row.max_uses)) },
          {
            key: "status",
            render: (row) => statusPill(row.is_active ? "active" : "inactive"),
          },
          {
            key: "actions",
            render: (row) =>
              `<button type="button" class="btn ghost" data-use-referral="${escapeHtml(row.code)}">Test</button>`,
          },
        ],
        rows: data.items || [],
      });

      tbody.querySelectorAll("[data-use-referral]").forEach((btn) => {
        btn.addEventListener("click", () => {
          prefillValidator({ referralCode: btn.dataset.useReferral });
        });
      });
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }, { key: "f" }, { key: "g" }],
        rows: [],
        emptyMessage: "Could not load referral codes.",
      });
    }
  }

  async function loadPromotionsSection() {
    await mountPromoValidator();
    await Promise.all([loadDiscountCodes(), loadReferralCodes()]);
  }

  const sectionLoaded = new Set();

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "promotions" && !sectionLoaded.has("promotions")) {
      sectionLoaded.add("promotions");
      loadPromotionsSection();
    }
  });

  if (parseHashBaseSection(window.location.hash) === "promotions") {
    sectionLoaded.add("promotions");
    loadPromotionsSection();
  }
})();
