/** Admin workspace sections — overview, employees, staff export, settings. */
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

  function formatOverviewTime(iso) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  }

  function moduleCard({ icon, title, value, sub, href, tone }) {
    const toneClass = tone ? ` overview-module-card--${tone}` : "";
    return `
      <a class="overview-module-card${toneClass}" href="${escapeHtml(href)}">
        <span class="overview-module-card__icon" aria-hidden="true">${icon}</span>
        <span class="overview-module-card__title">${escapeHtml(title)}</span>
        <span class="overview-module-card__value">${escapeHtml(value)}</span>
        <span class="overview-module-card__sub">${escapeHtml(sub)}</span>
      </a>`;
  }

  function actionItem(item) {
    return `
      <a class="overview-action overview-action--${escapeHtml(item.severity)}" href="${escapeHtml(item.href)}">
        <span class="overview-action__title">${escapeHtml(item.title)}</span>
        <span class="overview-action__detail muted">${escapeHtml(item.detail)}</span>
      </a>`;
  }

  async function loadOverview() {
    const grid = document.getElementById("overview-metrics");
    const modulesHost = document.getElementById("overview-modules");
    const actionsHost = document.getElementById("overview-actions");
    const actionsCount = document.getElementById("overview-actions-count");
    const subtitle = document.getElementById("overview-subtitle");
    const trialNote = document.getElementById("overview-trial-note");
    if (!grid) return;
    try {
      const res = await apiFetch("/admin/overview");
      if (!res.ok) throw new Error("Overview unavailable");
      const data = await res.json();
      await loadTenantFeatures();
      applyFeatureGates();

      const businessName = data.trading_name || data.tenant_name || "your business";
      if (subtitle) {
        subtitle.textContent = `Welcome back — ${businessName} at a glance.`;
      }

      if (trialNote) {
        if (data.trial_active) {
          trialNote.hidden = false;
          trialNote.className = "promo-result hr-overview-trial";
          trialNote.innerHTML = `Your <strong>14-day trial</strong> includes full HR, compliance, and workforce tools${data.days_remaining != null ? ` — <strong>${escapeHtml(data.days_remaining)} days</strong> remaining` : ""}.`;
        } else {
          trialNote.hidden = true;
          trialNote.innerHTML = "";
        }
      }

      const m = data.modules || {};
      const employees = m.employees || {};
      const punch = m.time_punch || {};
      const actions = data.open_actions_count || 0;
      const critical = (data.open_actions || []).filter((a) => a.severity === "critical").length;

      grid.innerHTML = `
        <article class="hr-stat-card">
          <span class="hr-stat-card__icon" aria-hidden="true">👥</span>
          <span class="hr-stat-card__label">Active employees</span>
          <span class="hr-stat-card__value">${escapeHtml(employees.active ?? 0)}</span>
          <span class="hr-stat-card__sub">Limit ${escapeHtml(employees.limit ?? data.max_employees ?? "—")} on ${escapeHtml(data.plan_display_name || "current")} plan</span>
        </article>
        <article class="hr-stat-card hr-stat-card--ok">
          <span class="hr-stat-card__icon" aria-hidden="true">🕐</span>
          <span class="hr-stat-card__label">Today's punches</span>
          <span class="hr-stat-card__value">${escapeHtml(punch.today_punches ?? 0)}</span>
          <span class="hr-stat-card__sub">${punch.last_punch_at ? `Last punch ${formatOverviewTime(punch.last_punch_at)}` : "No punches yet"}</span>
        </article>
        <article class="hr-stat-card${critical ? " hr-stat-card--warn" : actions ? " hr-stat-card--warn" : ""}">
          <span class="hr-stat-card__icon" aria-hidden="true">${critical ? "⚠️" : "✓"}</span>
          <span class="hr-stat-card__label">Open actions</span>
          <span class="hr-stat-card__value">${escapeHtml(actions)}</span>
          <span class="hr-stat-card__sub">${critical ? `${critical} need immediate attention` : actions ? "Review items in the panel" : "All clear"}</span>
        </article>
        <article class="hr-stat-card">
          <span class="hr-stat-card__icon" aria-hidden="true">💳</span>
          <span class="hr-stat-card__label">Subscription</span>
          <span class="hr-stat-card__value">${escapeHtml(data.subscription_status || "Not set")}</span>
          <span class="hr-stat-card__sub">${escapeHtml(data.plan_display_name || data.subscription_plan || "No plan")} plan</span>
        </article>`;

      if (modulesHost) {
        const rtw = m.rtw || {};
        const absence = m.absence || {};
        const recruitment = m.recruitment || {};
        const rota = m.rota || {};
        const grievance = m.grievance || {};
        const offboarding = m.offboarding || {};
        const contracts = m.contracts || {};
        const docs = m.documents || {};
        const rotaLabel =
          rota.status === "published"
            ? "Published this week"
            : rota.shift_count
              ? "Draft — not published"
              : "No shifts yet";

        modulesHost.innerHTML = [
          moduleCard({
            icon: "👥",
            title: "Employees",
            value: String(employees.active ?? 0),
            sub: employees.onboarding ? `${employees.onboarding} onboarding` : "Active register",
            href: "#employees",
          }),
          moduleCard({
            icon: "📋",
            title: "Recruitment",
            value: String(recruitment.open_vacancies ?? 0),
            sub: recruitment.pending_applicants
              ? `${recruitment.pending_applicants} pending applicants`
              : "Open vacancies",
            href: "#recruitment",
          }),
          moduleCard({
            icon: "🛂",
            title: "Right to work",
            value: String(rtw.verified ?? 0),
            sub: `${rtw.expiring_soon ?? 0} expiring · ${rtw.needs_review ?? 0} need review`,
            href: "#compliance",
            tone: (rtw.needs_review ?? 0) > 0 ? "danger" : (rtw.expiring_soon ?? 0) > 0 ? "warn" : "",
          }),
          moduleCard({
            icon: "🏥",
            title: "Absence monitoring",
            value: String(absence.day9_alerts ?? 0),
            sub:
              (absence.day9_alerts ?? 0) > 0
                ? "Day-9 alerts need action"
                : `${absence.active_this_month ?? 0} absence days this month`,
            href: "#compliance",
            tone: (absence.day9_alerts ?? 0) > 0 ? "danger" : "",
          }),
          moduleCard({
            icon: "📍",
            title: "Time punch",
            value: String(punch.sites ?? 0),
            sub: punch.today_punches
              ? `${punch.today_punches} punch${punch.today_punches === 1 ? "" : "es"} today`
              : punch.sites
                ? "No punches today"
                : "Set up geofence sites",
            href: "#time-punch",
            tone: !punch.sites ? "warn" : "",
          }),
          moduleCard({
            icon: "📅",
            title: "Rota",
            value: String(rota.shift_count ?? 0),
            sub: rotaLabel,
            href: "#rota",
            tone: rota.status !== "published" && rota.shift_count ? "warn" : "",
          }),
          moduleCard({
            icon: "⚖️",
            title: "Grievance",
            value: String(grievance.open_cases ?? 0),
            sub: grievance.open_cases ? "Open cases" : "No open cases",
            href: "#grievance",
            tone: (grievance.open_cases ?? 0) > 0 ? "warn" : "",
          }),
          moduleCard({
            icon: "📄",
            title: "Employment contracts",
            value: String(contracts.pending_signature ?? 0),
            sub: contracts.pending_signature ? "Awaiting signature" : "Up to date",
            href: "#employment-contracts",
            tone: (contracts.pending_signature ?? 0) > 0 ? "warn" : "",
          }),
          moduleCard({
            icon: "🚪",
            title: "Offboarding",
            value: String(offboarding.in_progress ?? 0),
            sub: offboarding.in_progress ? "In progress" : "No active leavers",
            href: "#offboarding",
          }),
          moduleCard({
            icon: "🗂️",
            title: "Documents",
            value: String(docs.count ?? data.document_count ?? 0),
            sub: "In tenant document store",
            href: "#settings",
          }),
        ].join("");
      }

      if (actionsHost) {
        const items = data.open_actions || [];
        if (actionsCount) actionsCount.textContent = String(items.length);
        actionsHost.innerHTML = items.length
          ? items.map(actionItem).join("")
          : `<p class="overview-actions-empty muted">No open actions — your workspace looks good.</p>`;
      }
    } catch (error) {
      grid.innerHTML = `<p class="muted">${escapeHtml(error.message || "Could not load overview.")}</p>`;
      if (modulesHost) modulesHost.innerHTML = "";
      if (actionsHost) actionsHost.innerHTML = "";
    }
  }

  async function loadTenantProfileForm() {
    /* Business profile form is rendered in admin-settings.js */
  }

  async function loadDocuments() {
    /* Settings documents load via admin-settings.js */
  }

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "overview") loadOverview();
  });

  loadOverview();
  loadTrialBanner();
})();
