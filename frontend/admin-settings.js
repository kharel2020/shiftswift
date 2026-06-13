/** Settings workspace — left nav, plan badge, business profile, billing, notifications. */
(function initAdminSettings() {
  const { apiFetch, escapeHtml, isFeatureEnabled, parseHashPath } = window.Admin;

  const PANELS = ["business", "documents", "billing", "notifications", "users", "multisite", "api"];
  const PANEL_COPY = {
    business: {
      title: "Business information",
      subtitle: "Your organisation's legal details, signatory, and contact information.",
    },
    documents: {
      title: "Document store",
      subtitle: "Upload files or register external document links for audits and offboarding.",
    },
    billing: {
      title: "Billing & plan",
      subtitle: "Current subscription, trial status, and billing contacts.",
    },
    notifications: {
      title: "Notifications",
      subtitle: "Choose how your organisation receives compliance and workforce alerts.",
    },
    users: {
      title: "Users & access",
      subtitle: "People who can sign in to this ShiftSwift HR workspace.",
    },
    multisite: {
      title: "Multi-site",
      subtitle: "Manage staff and compliance across multiple locations.",
    },
    api: {
      title: "API access",
      subtitle: "Integrate ShiftSwift HR with external tools and systems.",
    },
  };
  const SAVED_AT_KEY = `settings_business_saved_${window.Admin?.TENANT_ID ?? "default"}`;

  let sectionReady = false;
  let businessFormBound = false;

  function settingsPanelId() {
    const { path } = parseHashPath(window.location.hash || "#settings/business");
    const part = path.split("/")[1];
    return PANELS.includes(part) ? part : "business";
  }

  function showSettingsToast(message) {
    const toast = document.getElementById("settings-toast");
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    toast.classList.add("settings-toast--visible");
    window.clearTimeout(showSettingsToast._timer);
    showSettingsToast._timer = window.setTimeout(() => {
      toast.classList.remove("settings-toast--visible");
      window.setTimeout(() => {
        toast.hidden = true;
      }, 300);
    }, 3200);
  }

  function formatSavedAt(iso) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  }

  function updateLastSavedLabel(iso) {
    const el = document.getElementById("tenant-profile-last-saved");
    if (!el) return;
    const when = formatSavedAt(iso);
    el.textContent = when ? `Saved · ${when}` : "";
  }

  function activateSettingsPanel(panelId) {
    document.querySelectorAll("[data-settings-panel]").forEach((el) => {
      el.hidden = el.dataset.settingsPanel !== panelId;
    });
    document.querySelectorAll("[data-settings-nav]").forEach((btn) => {
      const active = btn.dataset.settingsNav === panelId;
      btn.classList.toggle("settings-nav__item--active", active);
      btn.setAttribute("aria-current", active ? "page" : "false");
    });
    const copy = PANEL_COPY[panelId] || PANEL_COPY.business;
    const titleEl = document.getElementById("settings-panel-title");
    const subtitleEl = document.getElementById("settings-panel-subtitle");
    if (titleEl) titleEl.textContent = copy.title;
    if (subtitleEl) subtitleEl.textContent = copy.subtitle;
  }

  function bindSettingsNav() {
    document.querySelectorAll("[data-settings-nav]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const panel = btn.dataset.settingsNav;
        window.location.hash = `settings/${panel}`;
        activateSettingsPanel(panel);
      });
    });
    window.addEventListener("hashchange", () => {
      if (parseHashPath(window.location.hash).baseSection === "settings") {
        activateSettingsPanel(settingsPanelId());
      }
    });
  }

  async function loadPlanBadge() {
    const label = document.getElementById("settings-plan-label");
    if (!label) return;
    const businessName = localStorage.getItem("businessName") || "Your business";
    try {
      const [overviewRes, billingRes] = await Promise.all([
        apiFetch("/admin/overview"),
        apiFetch("/billing/status"),
      ]);
      let planName = "Starter";
      if (overviewRes.ok) {
        const overview = await overviewRes.json();
        planName = overview.plan_display_name || overview.subscription_plan || "Starter";
      } else if (billingRes.ok) {
        const billing = await billingRes.json();
        planName = (billing.subscription_plan || "starter").replace(/_/g, " ");
      }
      label.textContent = `${planName} plan · ${businessName}`;
    } catch {
      label.textContent = businessName;
    }
  }

  async function startUpgrade() {
    try {
      const res = await apiFetch("/billing/upgrade", { method: "POST", body: JSON.stringify({}) });
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }
      window.location.href = "./index.html#pricing";
    } catch {
      window.location.href = "./index.html#pricing";
    }
  }

  function bindUpgradeActions() {
    document.getElementById("settings-upgrade-link")?.addEventListener("click", (e) => {
      e.preventDefault();
      startUpgrade();
    });
    document.querySelectorAll("[data-settings-upgrade]").forEach((btn) => {
      btn.addEventListener("click", startUpgrade);
    });
  }

  function applyGatedPanels() {
    document.querySelectorAll(".settings-gated-card").forEach((card) => {
      const feature = card.dataset.feature;
      const enabled = feature ? isFeatureEnabled(feature) : true;
      card.classList.toggle("settings-gated-card--locked", !enabled);
      const locked = card.querySelector(".settings-gated-card__locked");
      const unlocked = card.querySelector(".settings-gated-card__unlocked");
      if (locked) locked.hidden = enabled;
      if (unlocked) unlocked.hidden = !enabled;
    });
  }

  async function loadBusinessPanel() {
    const host = document.getElementById("tenant-profile-form");
    if (!host || businessFormBound) return;

    let values = {};
    try {
      const res = await apiFetch("/admin/tenant-profile");
      if (res.ok) values = await res.json();
    } catch {
      /* optional */
    }

    const savedAt = localStorage.getItem(SAVED_AT_KEY);
    updateLastSavedLabel(savedAt);

    host.innerHTML = `
      <form class="settings-business-form" id="tenant-profile-form-el">
        <section class="settings-form-section">
          <h4 class="settings-form-section__title">Legal &amp; registration</h4>
          <div class="edit-form edit-form--cols-2">
            <label class="edit-field"><span class="edit-label">Legal company name</span><input name="name" type="text" required value="${escapeHtml(values.name || "")}" /></label>
            <label class="edit-field"><span class="edit-label">Trading name (if different)</span><input name="trading_name" type="text" placeholder="e.g. Himalayan Inn" value="${escapeHtml(values.trading_name || "")}" /></label>
            <label class="edit-field"><span class="edit-label">Company number</span><input name="company_number" type="text" placeholder="e.g. 14568900" value="${escapeHtml(values.company_number || "")}" /></label>
            <label class="edit-field"><span class="edit-label">VAT number (optional)</span><input name="vat_number" type="text" placeholder="e.g. GB 123 456 789" value="${escapeHtml(values.vat_number || "")}" /></label>
            <label class="edit-field" data-span="2"><span class="edit-label">Registered address</span><textarea name="registered_address" rows="3" placeholder="Full registered address including postcode">${escapeHtml(values.registered_address || "")}</textarea></label>
          </div>
        </section>
        <section class="settings-form-section">
          <h4 class="settings-form-section__title">Contact</h4>
          <div class="edit-form edit-form--cols-2">
            <label class="edit-field"><span class="edit-label">Phone</span><input name="phone" type="tel" placeholder="e.g. +44 115 000 0000" value="${escapeHtml(values.phone || "")}" /></label>
            <label class="edit-field"><span class="edit-label">Billing email</span><input name="billing_email" type="email" value="${escapeHtml(values.billing_email || "")}" /></label>
          </div>
        </section>
        <section class="settings-form-section">
          <h4 class="settings-form-section__title">Signatory</h4>
          <div class="edit-form edit-form--cols-2">
            <label class="edit-field"><span class="edit-label">Full name</span><input name="signatory_name" type="text" placeholder="e.g. Gobinda Chhetri" value="${escapeHtml(values.signatory_name || "")}" /></label>
            <label class="edit-field"><span class="edit-label">Title / role</span><input name="signatory_title" type="text" value="${escapeHtml(values.signatory_title || "Director")}" /></label>
            <label class="edit-field" data-span="2"><span class="edit-label">Email</span><input name="signatory_email" type="email" placeholder="signatory@yourbusiness.co.uk" value="${escapeHtml(values.signatory_email || "")}" /></label>
          </div>
        </section>
        <div class="settings-form-actions">
          <button type="submit" class="btn outline settings-save-btn">
            <span class="settings-save-btn__icon" aria-hidden="true">💾</span>
            Save business details
          </button>
          <span id="tenant-profile-last-saved" class="settings-last-saved muted"></span>
          <p class="edit-form-status muted" data-status></p>
        </div>
      </form>`;

    updateLastSavedLabel(savedAt);

    host.querySelector("#tenant-profile-form-el").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const status = form.querySelector("[data-status]");
      if (status) status.textContent = "Saving…";
      const payload = Object.fromEntries(new FormData(form).entries());
      try {
        const res = await apiFetch("/admin/tenant-profile", {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Update failed");
        const now = new Date().toISOString();
        localStorage.setItem(SAVED_AT_KEY, now);
        updateLastSavedLabel(now);
        if (status) status.textContent = "";
        showSettingsToast("Business details saved ✓");
      } catch (error) {
        if (status) status.textContent = error.message || "Save failed.";
      }
    });

    businessFormBound = true;
  }

  async function loadBillingPanel() {
    const host = document.getElementById("settings-billing-content");
    if (!host || host.dataset.ready === "true") return;
    try {
      const [overviewRes, billingRes] = await Promise.all([
        apiFetch("/admin/overview"),
        apiFetch("/billing/status"),
      ]);
      const overview = overviewRes.ok ? await overviewRes.json() : {};
      const billing = billingRes.ok ? await billingRes.json() : {};
      const planName = overview.plan_display_name || "Starter";
      const status = billing.subscription_status || overview.subscription_status || "trial";
      const trialDays = billing.days_remaining;
      const trialEnds = billing.trial_ends_at
        ? new Date(billing.trial_ends_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
        : null;

      host.innerHTML = `
        <div class="settings-billing-summary">
          <div class="settings-billing-row"><span class="muted">Current plan</span><strong>${escapeHtml(planName)}</strong></div>
          <div class="settings-billing-row"><span class="muted">Status</span><strong>${escapeHtml(String(status).replace(/_/g, " "))}</strong></div>
          ${trialEnds ? `<div class="settings-billing-row"><span class="muted">Trial ends</span><strong>${escapeHtml(trialEnds)}${trialDays != null ? ` (${escapeHtml(trialDays)} days left)` : ""}</strong></div>` : ""}
          <div class="settings-billing-row"><span class="muted">Employee limit</span><strong>${escapeHtml(overview.max_employees ?? billing.max_employees ?? "—")}</strong></div>
        </div>
        <div class="link-row settings-billing-actions">
          <button type="button" class="btn outline" data-settings-upgrade>Upgrade plan</button>
          <a class="btn ghost" href="./payment-terms.html" target="_blank" rel="noopener">Payment terms</a>
          <a class="btn ghost" href="mailto:support@shiftswifthr.co.uk?subject=Billing%20enquiry">Contact billing</a>
        </div>
        <p class="muted settings-billing-note">Invoice history and self-service cancellation will appear here once Stripe live billing is enabled.</p>`;
      host.querySelector("[data-settings-upgrade]")?.addEventListener("click", startUpgrade);
      host.dataset.ready = "true";
    } catch {
      host.innerHTML = `<p class="muted">Could not load billing details.</p>`;
    }
  }

  const NOTIFICATION_EVENTS = [
    { id: "rtw_expiry", label: "RTW expiry approaching", default: "email" },
    { id: "absence_day5", label: "Absence day-5 warning", default: "email" },
    { id: "absence_day9", label: "Absence day-9 alert", default: "email_sms" },
    { id: "rota_published", label: "Rota published", default: "email" },
  ];

  function loadNotificationsPanel() {
    const host = document.getElementById("settings-notifications-content");
    if (!host || host.dataset.ready === "true") return;

    host.innerHTML = `<p class="muted">Loading notification preferences…</p>`;

    apiFetch("/admin/notification-preferences")
      .then(async (res) => {
        const data = res.ok ? await res.json() : null;
        const events = data?.events?.length ? data.events : NOTIFICATION_EVENTS;
        const prefs = data?.preferences || {};

        host.innerHTML = `
      <p class="muted">Choose how your organisation receives alerts. Employee emails respect each person's notification setting.</p>
      <div class="settings-notify-table-wrap">
        <table class="data-table settings-notify-table">
          <thead><tr><th>Event</th><th>Delivery</th></tr></thead>
          <tbody>
            ${events.map((ev) => {
              const fallback = NOTIFICATION_EVENTS.find((item) => item.id === ev.id)?.default || "email";
              const current = prefs[ev.id] || fallback;
              return `
              <tr>
                <td>${escapeHtml(ev.label)}</td>
                <td>
                  <select class="settings-notify-select" data-notify-id="${escapeHtml(ev.id)}">
                    <option value="email" ${current === "email" ? "selected" : ""}>Email</option>
                    <option value="email_sms" ${current === "email_sms" ? "selected" : ""}>Email + SMS</option>
                    <option value="off" ${current === "off" ? "selected" : ""}>Off</option>
                  </select>
                </td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>
      <p class="muted settings-notify-foot">Rota publish emails also require the “Notify staff by email” checkbox when publishing.</p>`;

        host.querySelectorAll(".settings-notify-select").forEach((select) => {
          select.addEventListener("change", async () => {
            const preferences = {};
            host.querySelectorAll(".settings-notify-select").forEach((el) => {
              preferences[el.dataset.notifyId] = el.value;
            });
            try {
              const saveRes = await apiFetch("/admin/notification-preferences", {
                method: "PATCH",
                body: JSON.stringify({ preferences }),
              });
              const saveData = await saveRes.json();
              if (!saveRes.ok) throw new Error(saveData.detail || "Save failed");
              showSettingsToast("Notification preferences saved ✓");
            } catch (error) {
              showSettingsToast(error.message || "Could not save preferences");
            }
          });
        });

        host.dataset.ready = "true";
      })
      .catch(() => {
        host.innerHTML = `<p class="muted">Could not load notification preferences.</p>`;
      });
  }

  function loadUsersPanel() {
    const host = document.getElementById("settings-users-content");
    if (!host || host.dataset.ready === "true") return;
    const username = localStorage.getItem("username") || "Admin";
    const role = localStorage.getItem("userRole") || "hr";
    const roleLabel = role === "admin" ? "Platform admin" : role === "hr" ? "HR admin" : role;

    host.innerHTML = `
      <p class="muted">People who can sign in to this ShiftSwift HR workspace.</p>
      <div class="settings-user-card">
        <div class="settings-user-card__main">
          <strong>${escapeHtml(username)}</strong>
          <span class="settings-user-badge">Owner</span>
        </div>
        <span class="muted">${escapeHtml(roleLabel)} · you</span>
      </div>
      <div class="settings-form-actions">
        <a class="btn outline" href="mailto:support@shiftswifthr.co.uk?subject=Invite%20manager%20to%20ShiftSwift%20HR">Invite manager</a>
      </div>
      <p class="muted">Multi-user roles and manager invites are managed by support during early access. Email us to add HR managers or site leads.</p>`;
    host.dataset.ready = "true";
  }

  async function initSettingsSection() {
    bindSettingsNav();
    bindUpgradeActions();
    try {
      await window.Admin.loadTenantFeatures();
      window.Admin.applyFeatureGates();
    } catch {
      /* optional */
    }
    applyGatedPanels();
    await loadPlanBadge();
    activateSettingsPanel(settingsPanelId());
    await loadBusinessPanel();
    await loadBillingPanel();
    loadNotificationsPanel();
    loadUsersPanel();
    if (window.AdminDocuments?.loadSettingsDocuments) {
      await window.AdminDocuments.loadSettingsDocuments();
    }
  }

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "settings" && !sectionReady) {
      sectionReady = true;
      window.Admin.loadFormOptions().then(initSettingsSection);
    }
    if (event.detail?.section === "settings") {
      activateSettingsPanel(settingsPanelId());
    }
  });

  window.addEventListener("admin:features", () => {
    applyGatedPanels();
  });

  if (parseHashPath(window.location.hash).baseSection === "settings") {
    sectionReady = true;
    window.Admin.loadFormOptions().then(initSettingsSection);
  }

  window.AdminSettings = { showSettingsToast, startUpgrade };
})();
