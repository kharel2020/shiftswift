/** Admin promotions — validate discount/referral codes and browse catalogs. */
(async function initAdminPromotions() {
  const { apiFetch, loadFormOptions, mountEditForm, FORM_SCHEMAS, escapeHtml, statusPill, parseHashBaseSection, downloadAuthenticated, isPlatformAdmin } = window.Admin;

  let validateForm = null;
  let discountCodes = [];
  let referralCodes = [];
  let selectedPromo = null;
  let exportsBound = false;

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

  function renderPromoSidePanel() {
    const empty = document.getElementById("promo-detail-empty");
    const content = document.getElementById("promo-detail-content");
    if (!content) return;
    if (!selectedPromo) {
      empty?.removeAttribute("hidden");
      content.hidden = true;
      return;
    }
    empty?.setAttribute("hidden", "");
    content.hidden = false;

    if (selectedPromo.kind === "discount") {
      const row = selectedPromo.row;
      content.innerHTML = `
        <div class="hr-detail-head">
          <div>
            <h3>${escapeHtml(row.code)}</h3>
            ${statusPill(row.is_active ? "active" : "inactive")}
          </div>
        </div>
        <dl class="hr-detail-grid">
          <div><dt>Label</dt><dd>${escapeHtml(row.label || "Not set")}</dd></div>
          <div><dt>Discount</dt><dd>${escapeHtml(formatDiscount(row))}</dd></div>
          <div><dt>Plans</dt><dd>${row.applicable_plan_ids?.length ? escapeHtml(row.applicable_plan_ids.join(", ")) : "All plans"}</dd></div>
          <div><dt>Usage</dt><dd>${escapeHtml(formatUsage(row.redemption_count, row.max_redemptions))}</dd></div>
        </dl>
        <div class="hr-detail-foot">
          <button type="button" class="btn" id="promo-side-test-discount-btn">Test in validator</button>
        </div>`;
      content.querySelector("#promo-side-test-discount-btn")?.addEventListener("click", () => {
        prefillValidator({ discountCode: row.code });
      });
      return;
    }

    const row = selectedPromo.row;
    content.innerHTML = `
      <div class="hr-detail-head">
        <div>
          <h3>${escapeHtml(row.code)}</h3>
          ${statusPill(row.is_active ? "active" : "inactive")}
        </div>
      </div>
      <dl class="hr-detail-grid">
        <div><dt>Partner</dt><dd>${escapeHtml(row.partner_name)}</dd></div>
        <div><dt>Reward</dt><dd>${escapeHtml(formatReferralReward(row))}</dd></div>
        <div><dt>Agreed commission</dt><dd>${escapeHtml(row.referrer_commission_percent)}% (manual payout)</dd></div>
        <div><dt>Usage</dt><dd>${escapeHtml(formatUsage(row.use_count, row.max_uses))}</dd></div>
      </dl>
      <div class="hr-detail-foot">
        <button type="button" class="btn" id="promo-side-test-referral-btn">Test in validator</button>
        ${isPlatformAdmin() ? `<button type="button" class="btn ghost" id="promo-side-export-referral-btn">Export CSV</button>` : ""}
      </div>`;
    content.querySelector("#promo-side-test-referral-btn")?.addEventListener("click", () => {
      prefillValidator({ referralCode: row.code });
    });
    content.querySelector("#promo-side-export-referral-btn")?.addEventListener("click", async () => {
      try {
        await exportIntroducerCode(row.code);
      } catch (error) {
        alert(error.message || "Export failed");
      }
    });
  }

  function selectDiscountCode(code) {
    selectedPromo = { kind: "discount", code, row: discountCodes.find((r) => r.code === code) };
    renderDiscountTable();
    renderReferralTable();
    renderPromoSidePanel();
  }

  function selectReferralCode(code) {
    selectedPromo = { kind: "referral", code, row: referralCodes.find((r) => r.code === code) };
    renderDiscountTable();
    renderReferralTable();
    renderPromoSidePanel();
  }

  function renderDiscountTable() {
    const tbody = document.getElementById("discount-codes-body");
    if (!tbody) return;
    if (!discountCodes.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="muted">No discount codes configured. Seed the billing catalog.</td></tr>';
      return;
    }
    tbody.innerHTML = discountCodes
      .map((row) => {
        const selected =
          selectedPromo?.kind === "discount" && selectedPromo.code === row.code ? " hr-register-row--selected" : "";
        return `<tr class="hr-register-row${selected}" data-discount-code="${escapeHtml(row.code)}">
          <td><strong>${escapeHtml(row.code)}</strong></td>
          <td>${escapeHtml(row.label || "Not set")}</td>
          <td>${escapeHtml(formatDiscount(row))}</td>
          <td>${row.applicable_plan_ids?.length ? escapeHtml(row.applicable_plan_ids.join(", ")) : "<span class='muted'>All plans</span>"}</td>
          <td>${escapeHtml(formatUsage(row.redemption_count, row.max_redemptions))}</td>
          <td>${statusPill(row.is_active ? "active" : "inactive")}</td>
        </tr>`;
      })
      .join("");
    tbody.querySelectorAll("[data-discount-code]").forEach((row) => {
      row.addEventListener("click", () => selectDiscountCode(row.dataset.discountCode));
    });
  }

  function renderReferralTable() {
    const tbody = document.getElementById("referral-codes-body");
    if (!tbody) return;
    if (!referralCodes.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="muted">No referral codes configured. Seed the billing catalog.</td></tr>';
      return;
    }
    tbody.innerHTML = referralCodes
      .map((row) => {
        const selected =
          selectedPromo?.kind === "referral" && selectedPromo.code === row.code ? " hr-register-row--selected" : "";
        return `<tr class="hr-register-row${selected}" data-referral-code="${escapeHtml(row.code)}">
          <td><strong>${escapeHtml(row.code)}</strong></td>
          <td>${escapeHtml(row.partner_name)}</td>
          <td>${escapeHtml(formatReferralReward(row))}</td>
          <td>${escapeHtml(row.referrer_commission_percent)}% (manual)</td>
          <td>${escapeHtml(formatUsage(row.use_count, row.max_uses))}</td>
          <td>${statusPill(row.is_active ? "active" : "inactive")}</td>
        </tr>`;
      })
      .join("");
    tbody.querySelectorAll("[data-referral-code]").forEach((row) => {
      row.addEventListener("click", () => selectReferralCode(row.dataset.referralCode));
    });
  }

  async function loadDiscountCodes() {
    const tbody = document.getElementById("discount-codes-body");
    if (!tbody) return;
    try {
      const res = await apiFetch("/admin/billing/discount-codes");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      discountCodes = data.items || [];
      renderDiscountTable();
    } catch {
      discountCodes = [];
      tbody.innerHTML = '<tr><td colspan="6" class="muted">Could not load discount codes.</td></tr>';
    }
  }

  function setupIntroducerExports() {
    const toolbar = document.getElementById("introducer-export-actions");
    if (!toolbar || !isPlatformAdmin()) return;
    toolbar.hidden = false;
    if (exportsBound) return;
    exportsBound = true;

    document.getElementById("export-all-introducers-btn")?.addEventListener("click", async () => {
      try {
        await downloadAuthenticated("/admin/billing/introducer-commission.csv", "shiftswift-introducers-all.csv");
      } catch (error) {
        alert(error.message || "Export failed");
      }
    });
  }

  async function exportIntroducerCode(code) {
    const safe = encodeURIComponent(code);
    await downloadAuthenticated(
      `/admin/billing/introducer-commission.csv?referral_code=${safe}`,
      `shiftswift-introducer-${code}.csv`
    );
  }

  async function loadReferralCodes() {
    const tbody = document.getElementById("referral-codes-body");
    if (!tbody) return;
    try {
      const res = await apiFetch("/admin/billing/referral-codes");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      referralCodes = data.items || [];
      renderReferralTable();
    } catch {
      referralCodes = [];
      tbody.innerHTML = '<tr><td colspan="6" class="muted">Could not load referral codes.</td></tr>';
    }
  }

  async function loadPromotionsSection() {
    setupIntroducerExports();
    await mountPromoValidator();
    await Promise.all([loadDiscountCodes(), loadReferralCodes()]);
    if (selectedPromo) renderPromoSidePanel();
  }

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "promotions") loadPromotionsSection();
  });

  if (parseHashBaseSection(window.location.hash) === "promotions") loadPromotionsSection();
})();
