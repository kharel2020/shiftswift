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
          Upgrade anytime. We will email you at 7, 3, and 1 day before trial ends.</p>
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
        ${data.trial_active ? `<p class="promo-result" style="margin-bottom:1rem;">Your <strong>14-day trial</strong> includes full HR, compliance, and workforce tools${data.days_remaining != null ? ` — <strong>${escapeHtml(data.days_remaining)} days</strong> remaining` : ""}.</p>` : ""}
        <article class="metric-card">
          <strong>${escapeHtml(data.active_employees)}</strong>
          <span>Active employees</span>
          <p class="muted">Limit ${escapeHtml(data.max_employees)} on current plan</p>
        </article>
        <article class="metric-card">
          <strong>${escapeHtml(data.subscription_status || "Not set")}</strong>
          <span>Subscription</span>
          <p class="muted">${escapeHtml(data.plan_display_name || data.subscription_plan || "No plan")} plan</p>
        </article>
        <article class="metric-card">
          <strong>${escapeHtml(data.document_count)}</strong>
          <span>Stored documents</span>
        </article>
        <article class="metric-card">
          <strong>Export</strong>
          <span>Payroll partners</span>
          <p class="muted">BrightPay &amp; Xero CSV export included</p>
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

  async function loadPayrollExportPanel() {
    const panel = document.getElementById("payroll-export-panel");
    if (!panel) return;
    const today = new Date();
    const monthStart = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`;
    const monthEnd = today.toISOString().slice(0, 10);
    panel.innerHTML = `
      <div class="promo-result" style="margin-bottom:1rem;">
        <p><strong>Bring your own payroll.</strong> Most UK SMEs already use BrightPay, Xero, or a bureau.
        ShiftSwift HR keeps HR &amp; compliance records — export CSV when you need to sync employees or hours.</p>
      </div>
      <div class="detail-grid">
        <div><span class="muted">BrightPay</span><strong>CSV employee import</strong></div>
        <div><span class="muted">Xero Payroll</span><strong>Manual / CSV add employees</strong></div>
        <div><span class="muted">RTI &amp; payslips</span><strong>In your payroll software</strong></div>
      </div>
      <p class="link-row" style="margin-top:1rem;">
        <button type="button" class="btn" id="payroll-export-employees-btn">Download employee CSV</button>
        <button type="button" class="btn secondary" id="payroll-export-hours-btn">Download hours CSV</button>
        <a class="btn ghost" href="./payroll-export-guide.html" target="_blank" rel="noopener">BrightPay setup guide</a>
      </p>
      <label class="edit-field" style="margin-top:1rem;max-width:320px;">
        <span class="edit-label">Hours export — from date</span>
        <input type="date" id="payroll-hours-from" value="${monthStart}" />
      </label>
      <label class="edit-field" style="max-width:320px;">
        <span class="edit-label">Hours export — to date</span>
        <input type="date" id="payroll-hours-to" value="${monthEnd}" />
      </label>
      <p class="muted">Include NI numbers and start dates in employee profiles before exporting for smoother payroll import.</p>`;

    document.getElementById("payroll-export-employees-btn")?.addEventListener("click", async () => {
      try {
        await downloadAuthenticated("/admin/payroll-export/employees.csv", "shiftswift-employees.csv");
      } catch (error) {
        alert(error.message || "Export failed");
      }
    });
    document.getElementById("payroll-export-hours-btn")?.addEventListener("click", async () => {
      const from = document.getElementById("payroll-hours-from")?.value;
      const to = document.getElementById("payroll-hours-to")?.value;
      let path = "/admin/payroll-export/hours.csv";
      const params = new URLSearchParams();
      if (from) params.set("from_date", from);
      if (to) params.set("to_date", to);
      if (params.toString()) path += `?${params.toString()}`;
      try {
        await downloadAuthenticated(path, "shiftswift-hours.csv");
      } catch (error) {
        alert(error.message || "Export failed");
      }
    });
  }

  const sectionLoaded = new Set();

  window.addEventListener("admin:section", (event) => {
    const section = event.detail?.section;
    if (section === "overview") loadOverview();
    if (section === "payroll" && !sectionLoaded.has("payroll")) {
      sectionLoaded.add("payroll");
      loadPayrollExportPanel();
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
