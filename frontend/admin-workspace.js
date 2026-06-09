/** Admin workspace sections — overview, employees, payroll, settings. */
(async function initAdminWorkspace() {
  const {
    apiFetch,
    loadFormOptions,
    loadTenantFeatures,
    applyFeatureGates,
    isFeatureEnabled,
    mountEditForm,
    renderTableBody,
    FORM_SCHEMAS,
    escapeHtml,
    statusPill,
  } = window.Admin;

  try {
    await loadFormOptions();
    await loadTenantFeatures();
    applyFeatureGates();
  } catch (error) {
    console.warn("Form metadata unavailable:", error.message);
  }

  window.addEventListener("admin:features-refresh", async () => {
    await loadTenantFeatures();
    applyFeatureGates();
  });

  async function loadTrialBanner() {
    const banner = document.getElementById("trial-upgrade-banner");
    if (!banner) return;
    try {
      const res = await apiFetch("/billing/status");
      if (!res.ok) {
        banner.hidden = true;
        return;
      }
      const status = await res.json();
      const days = status.days_remaining;
      const expired = status.upgrade_required || status.subscription_status === "trial_expired";
      const onHold = status.license_on_hold;
      const paymentWarning = status.license_warning;

      if (
        !onHold &&
        !paymentWarning &&
        status.access_allowed &&
        !expired &&
        (days == null || days > 7)
      ) {
        banner.hidden = true;
        return;
      }

      banner.hidden = false;
      banner.className = "promo-result promo-result-message";
      banner.classList.remove("promo-result--error");

      if (onHold) {
        banner.classList.add("promo-result--error");
        banner.innerHTML = `
          <p><strong>Licence on hold.</strong> ${escapeHtml(status.hold_message || "Direct Debit payment was not received after the grace period.")}</p>
          <button type="button" class="btn" id="trial-upgrade-btn">Update payment</button>`;
      } else if (paymentWarning) {
        banner.innerHTML = `
          <p><strong>Direct Debit failed.</strong> ${escapeHtml(status.warning_message || "Please update payment.")}
          <strong>${escapeHtml(status.grace_days_remaining)}</strong> day(s) before access is restricted.</p>
          <button type="button" class="btn" id="trial-upgrade-btn">Fix payment</button>
          <button type="button" class="btn secondary" id="trial-dd-btn">Set up Direct Debit</button>`;
      } else if (expired) {
        banner.classList.add("promo-result--error");
        banner.innerHTML = `
          <p><strong>Free trial ended.</strong> Upgrade your ShiftSwift HR subscription to continue using admin features.
          Reminder emails were sent to <strong>${escapeHtml(status.billing_email || "your billing email")}</strong>.</p>
          <button type="button" class="btn" id="trial-upgrade-btn">Upgrade now</button>`;
      } else {
        banner.innerHTML = `
          <p><strong>${escapeHtml(days)} day${days === 1 ? "" : "s"} left</strong> on your 14-day free trial.
          Upgrade anytime — we'll email you at 7, 3, and 1 day before trial ends.</p>
          <button type="button" class="btn secondary" id="trial-upgrade-btn">View plans & upgrade</button>`;
      }
      document.getElementById("trial-upgrade-btn")?.addEventListener("click", startUpgrade);
      document.getElementById("trial-dd-btn")?.addEventListener("click", startDirectDebitSetup);
    } catch {
      banner.hidden = true;
    }
  }

  async function startDirectDebitSetup() {
    try {
      const res = await apiFetch("/billing/direct-debit/mandate", {
        method: "POST",
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }
      alert(data.message || data.detail || "Direct Debit setup unavailable");
    } catch (error) {
      alert(error.message || "Direct Debit setup failed");
    }
  }

  async function startUpgrade() {
    try {
      const res = await apiFetch("/billing/upgrade", {
        method: "POST",
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }
      alert(data.message || data.detail || "Upgrade is not available in local mode. Email support@shiftswifthr.co.uk.");
    } catch (error) {
      alert(error.message || "Upgrade request failed");
    }
  }

  async function loadOverview() {
    const grid = document.getElementById("overview-metrics");
    if (!grid) return;
    try {
      const res = await apiFetch("/admin/overview");
      if (!res.ok) throw new Error("Overview unavailable");
      const data = await res.json();
      await loadTenantFeatures();
      applyFeatureGates();
      grid.innerHTML = `
        <article class="metric-card">
          <strong>${escapeHtml(data.active_employees)}</strong>
          <span>Active employees</span>
          <p class="muted">Limit ${escapeHtml(data.max_employees)} on current plan</p>
        </article>
        <article class="metric-card">
          <strong>${escapeHtml(data.subscription_status || "—")}</strong>
          <span>Subscription</span>
          <p class="muted">${escapeHtml(data.plan_display_name || data.subscription_plan || "No plan")} plan</p>
        </article>
        <article class="metric-card">
          <strong>${escapeHtml(data.document_count)}</strong>
          <span>Stored documents</span>
        </article>
        <article class="metric-card">
          <strong>${data.payroll_enabled ? "On" : "Off"}</strong>
          <span>Payroll add-on</span>
          <p class="muted">${escapeHtml(data.payroll_plan_id || "Not configured")}</p>
        </article>`;
    } catch (error) {
      grid.innerHTML = `<p class="muted">${escapeHtml(error.message || "Could not load overview.")}</p>`;
    }
  }

  async function loadTenantProfileForm() {
    const host = document.getElementById("tenant-profile-form");
    if (!host) return;
    let values = {};
    try {
      const res = await apiFetch("/admin/tenant-profile");
      if (res.ok) values = await res.json();
    } catch {
      /* empty */
    }
    mountEditForm(host, FORM_SCHEMAS.tenantProfile, {
      values,
      onSubmit: async (payload) => {
        const res = await apiFetch("/admin/tenant-profile", {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Update failed");
      },
    });
  }

  async function loadDocuments() {
    if (window.AdminDocuments?.loadSettingsDocuments) {
      await window.AdminDocuments.loadSettingsDocuments();
    }
  }

  async function loadPayrollPanel() {
    const panel = document.getElementById("payroll-details");
    const enrollPanel = document.getElementById("payroll-enroll-panel");
    const activePanel = document.getElementById("payroll-active-panel");
    if (!panel) return;

    if (!isFeatureEnabled("payroll")) {
      enrollPanel?.removeAttribute("hidden");
      activePanel?.setAttribute("hidden", "");
      document.getElementById("payroll-enroll-upgrade-btn")?.addEventListener("click", startUpgrade, { once: true });
      return;
    }

    enrollPanel?.setAttribute("hidden", "");
    activePanel?.removeAttribute("hidden");

    try {
      const [statusRes, meta] = await Promise.all([
        apiFetch("/billing/status"),
        window.Admin.formOptions ? Promise.resolve(window.Admin.formOptions) : loadFormOptions(),
      ]);
      if (!statusRes.ok) throw new Error("Billing unavailable");
      const status = await statusRes.json();
      const payrollPlan = (meta.payroll_plans || []).find((p) => p.value === status.payroll_plan_id);
      const platformPlan = (meta.platform_plans || []).find((p) => p.value === status.subscription_plan);
      const mandateLabel = status.direct_debit_active
        ? `Active · ${status.mandate_sort_code || "—"} · ${status.mandate_account_last4 || "****"}`
        : status.direct_debit_pending
          ? "Pending confirmation (Bacs)"
          : status.mandate_status && status.mandate_status !== "none"
            ? String(status.mandate_status)
            : "Not set up";
      panel.innerHTML = `
        <div class="detail-grid">
          <div><span class="muted">Platform plan</span><strong>${escapeHtml(platformPlan?.label || status.subscription_plan || "—")}</strong></div>
          <div><span class="muted">Status</span><strong>${escapeHtml(status.subscription_status || "—")}</strong></div>
          <div><span class="muted">Trial</span><strong>${status.days_remaining != null ? `${escapeHtml(status.days_remaining)} days left` : status.subscription_status === "active" ? "Subscribed" : "—"}</strong></div>
          <div><span class="muted">Direct Debit</span><strong>${escapeHtml(mandateLabel)}</strong></div>
          <div><span class="muted">Employee band</span><strong>${escapeHtml(status.max_employees)} max</strong></div>
          <div><span class="muted">Payroll add-on</span><strong>${status.payroll_enabled ? "Enabled" : "Not enabled"}</strong></div>
          <div><span class="muted">Payroll plan</span><strong>${escapeHtml(payrollPlan?.label || status.payroll_plan_id || "—")}</strong></div>
          <div><span class="muted">Billing email</span><strong>${escapeHtml(status.billing_email || "—")}</strong></div>
        </div>
        <p class="link-row" style="margin-top:0.75rem;">
          <button type="button" class="btn" id="payroll-upgrade-btn">Upgrade subscription</button>
          ${!status.direct_debit_active ? '<button type="button" class="btn secondary" id="payroll-dd-btn">Set up Direct Debit</button>' : ""}
        </p>
        <p class="muted">Monthly billing via UK Bacs Direct Debit (Stripe mandate) or card at checkout. First Direct Debit payment may take a few working days.</p>`;
      document.getElementById("payroll-upgrade-btn")?.addEventListener("click", startUpgrade);
      document.getElementById("payroll-dd-btn")?.addEventListener("click", startDirectDebitSetup);
    } catch {
      panel.innerHTML = `<p class="muted">Billing details unavailable. Sign in and ensure the API is running.</p>`;
    }
  }

  const sectionLoaded = new Set();

  window.addEventListener("admin:section", (event) => {
    const section = event.detail?.section;
    if (section === "overview") loadOverview();
    if (section === "payroll" && !sectionLoaded.has("payroll")) {
      sectionLoaded.add("payroll");
      loadPayrollPanel();
    }
    if (section === "settings" && !sectionLoaded.has("settings")) {
      sectionLoaded.add("settings");
      loadFormOptions().then(() => {
        loadTenantProfileForm();
        loadDocuments();
      });
    }
  });

  loadOverview();
  loadTrialBanner();
})();
