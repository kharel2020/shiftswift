(function () {
  const state = {
    tenants: [],
    overview: null,
    providerName: "Datasoftware Analytics Ltd",
    filter: "all",
    search: "",
    selectedId: null,
    loading: true,
  };

  const els = {
    metrics: document.getElementById("master-metrics"),
    filters: document.getElementById("master-filters"),
    search: document.getElementById("master-search"),
    tableBody: document.getElementById("master-table-body"),
    cardList: document.getElementById("master-card-list"),
    empty: document.getElementById("master-empty"),
    detail: document.getElementById("master-detail"),
    detailClose: document.getElementById("master-detail-close"),
    pageSub: document.getElementById("master-page-sub"),
    providerName: document.getElementById("master-provider-name"),
    userName: document.getElementById("master-user-name"),
    userAvatar: document.getElementById("master-user-avatar"),
    exportBtn: document.getElementById("master-export-btn"),
    sidebar: document.getElementById("master-sidebar"),
    overlay: document.getElementById("master-overlay"),
    menuBtn: document.getElementById("master-menu-btn"),
    sidebarClose: document.getElementById("master-sidebar-close"),
  };

  function apiBase() {
    if (window.ShiftSwiftBrand?.getApiBase) return window.ShiftSwiftBrand.getApiBase();
    if (window.ShiftSwiftBrand?.resolveApiBase) return window.ShiftSwiftBrand.resolveApiBase();
    return localStorage.getItem("apiBaseUrl") || "http://localhost:3000";
  }

  function authHeaders() {
    return {
      Authorization: `Bearer ${localStorage.getItem("token")}`,
      "Content-Type": "application/json",
    };
  }

  async function apiGet(path) {
    const response = await fetch(`${apiBase()}${path}`, { headers: authHeaders() });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "Request failed";
      throw new Error(detail);
    }
    return data;
  }

  async function apiPost(path) {
    const response = await fetch(`${apiBase()}${path}`, {
      method: "POST",
      headers: authHeaders(),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "Request failed";
      throw new Error(detail);
    }
    return data;
  }

  function saveMasterReturnSession() {
    sessionStorage.setItem(
      "masterImpersonationReturn",
      JSON.stringify({
        token: localStorage.getItem("token"),
        refreshToken: localStorage.getItem("refreshToken"),
        userRole: localStorage.getItem("userRole"),
        tenantId: localStorage.getItem("tenantId"),
        masterTenantId: localStorage.getItem("masterTenantId"),
      })
    );
  }

  function applyImpersonationSession(data) {
    localStorage.setItem("token", data.access_token);
    localStorage.removeItem("refreshToken");
    localStorage.setItem("userRole", data.role || "hr");
    localStorage.setItem("tenantId", String(data.tenant_id));
    if (data.tenant_name) localStorage.setItem("businessName", data.tenant_name);
    sessionStorage.setItem(
      "impersonationActive",
      JSON.stringify({
        tenantId: data.tenant_id,
        tenantName: data.tenant_name,
        impersonatedBy: data.impersonated_by,
        expiresIn: data.expires_in,
      })
    );
  }

  async function impersonateTenant(tenant) {
    if (!tenant?.id) return;
    const button = document.getElementById("detail-impersonate");
    if (button) {
      button.disabled = true;
      button.textContent = "Starting session…";
    }
    try {
      const data = await apiPost(`/master/tenants/${tenant.id}/impersonate`);
      saveMasterReturnSession();
      applyImpersonationSession(data);
      window.location.href = data.redirect_url || "./admin.html";
    } catch (error) {
      alert(error.message || "Impersonation failed");
      if (button) {
        button.disabled = false;
        button.textContent = "Impersonate this account";
      }
    }
  }

  function initials(name) {
    const parts = String(name || "Platform").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "OP";
    return parts
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join("");
  }

  function formatMoney(value) {
    if (value == null) return "—";
    return `£${Number(value).toFixed(0)}`;
  }

  function formatDate(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  function planBadgeClass(tier) {
    return `plan-badge plan-badge--${tier || "starter"}`;
  }

  function statusClass(status) {
    return `master-status master-status--${status || "trialing"}`;
  }

  function dotClass(tone) {
    return `master-dot master-dot--${tone || "muted"}`;
  }

  function renderMetrics() {
    const stats = state.overview || {};
    const cards = [
      {
        hero: true,
        label: "MRR",
        value: formatMoney(stats.mrr_gbp),
        valueClass: "master-metric__value--gold",
        sub: stats.churned_this_month != null ? `${stats.churned_this_month} churned this month` : "",
      },
      {
        label: "Total tenants",
        value: stats.total_tenants ?? "0",
        sub: "Registered businesses",
      },
      {
        label: "Active (paying)",
        value: stats.active_paying ?? "0",
        sub: stats.conversion_rate_pct != null ? `${stats.conversion_rate_pct}% conversion` : "",
        valueStyle: "color: var(--master-green)",
      },
      {
        label: "Trialing",
        value: stats.trialing ?? "0",
        sub:
          stats.avg_trial_days_remaining != null
            ? `Avg ${stats.avg_trial_days_remaining} days left`
            : "No active trials",
      },
      {
        label: "Overdue",
        value: stats.overdue ?? "0",
        sub: `${stats.compliance_alert_tenants ?? 0} with compliance alerts`,
        valueStyle: stats.overdue ? "color: var(--master-red)" : "",
      },
    ];

    els.metrics.innerHTML = cards
      .map((card) => {
        const cls = card.hero ? "master-metric master-metric--hero" : "master-metric";
        const valueCls = card.valueClass ? ` ${card.valueClass}` : "";
        const valueStyle = card.valueStyle ? ` style="${card.valueStyle}"` : "";
        return `<article class="${cls}">
          <div class="master-metric__label">${card.label}</div>
          <div class="master-metric__value${valueCls}"${valueStyle}>${card.value}</div>
          <div class="master-metric__sub">${card.sub || ""}</div>
        </article>`;
      })
      .join("");
  }

  function renderFilters() {
    const counts = state.overview?.counts || {};
    const tabs = [
      ["all", "All"],
      ["trialing", "Trialing"],
      ["active", "Active"],
      ["overdue", "Overdue"],
    ];

    els.filters.innerHTML = tabs
      .map(([key, label]) => {
        const count = counts[key] ?? 0;
        const active = state.filter === key ? " is-active" : "";
        return `<button type="button" class="master-filter${active}" data-filter="${key}" role="tab" aria-selected="${
          state.filter === key
        }">${label} (${count})</button>`;
      })
      .join("");

    els.filters.querySelectorAll("[data-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.filter = btn.dataset.filter;
        loadTenants();
      });
    });
  }

  function renderTable() {
    const rows = state.tenants;
    els.empty.hidden = rows.length > 0;
    els.tableBody.innerHTML = rows
      .map((tenant) => {
        const selected = tenant.id === state.selectedId ? " is-selected" : "";
        const mrrClass = tenant.status === "overdue" && tenant.mrr_gbp ? " master-mrr-warn" : "";
        const mrrLabel =
          tenant.status === "overdue" && tenant.mrr_gbp ? `${tenant.mrr_label} ⚠` : tenant.mrr_label;
        return `<tr data-tenant-id="${tenant.id}" class="${selected.trim()}">
          <td>
            <div class="master-business">
              <strong>${escapeHtml(tenant.name)}</strong>
              <span>${escapeHtml(tenant.location)}</span>
            </div>
          </td>
          <td><span class="${planBadgeClass(tenant.plan_tier)}">${escapeHtml(tenant.plan_label)}</span></td>
          <td><span class="${statusClass(tenant.status)}">${escapeHtml(tenant.status)}</span></td>
          <td>${escapeHtml(formatDate(tenant.renewal_or_trial_date || tenant.trial_ends_at))}</td>
          <td>${escapeHtml(tenant.staff_label)}</td>
          <td class="${mrrClass.trim()}">${escapeHtml(mrrLabel)}</td>
          <td><span class="${dotClass(tenant.last_active?.tone)}"></span>${escapeHtml(tenant.last_active?.label || "—")}</td>
          <td><button type="button" class="master-view-link" data-view="${tenant.id}">View</button></td>
        </tr>`;
      })
      .join("");

    bindRowEvents(els.tableBody);
  }

  function renderCards() {
    els.cardList.innerHTML = state.tenants
      .map((tenant) => {
        const selected = tenant.id === state.selectedId ? " is-selected" : "";
        const mrr = tenant.status === "overdue" && tenant.mrr_gbp ? `${tenant.mrr_label} ⚠` : tenant.mrr_label;
        return `<article class="master-card${selected}" data-tenant-id="${tenant.id}">
          <div class="master-card__head">
            <div>
              <strong>${escapeHtml(tenant.name)}</strong>
              <div>${escapeHtml(tenant.location)}</div>
            </div>
            <div>
              <span class="${planBadgeClass(tenant.plan_tier)}">${escapeHtml(tenant.plan_label)}</span>
              <span class="${statusClass(tenant.status)}">${escapeHtml(tenant.status)}</span>
            </div>
          </div>
          <div class="master-card__meta">
            <div>Staff: ${escapeHtml(tenant.staff_label)}</div>
            <div>MRR: ${escapeHtml(mrr)}</div>
            <div>Last active: <span class="${dotClass(tenant.last_active?.tone)}"></span>${escapeHtml(tenant.last_active?.label || "—")}</div>
            ${
              tenant.trial_ends_at
                ? `<div>Trial ends: ${escapeHtml(formatDate(tenant.trial_ends_at))}</div>`
                : ""
            }
          </div>
          <div class="master-card__footer">
            <button type="button" class="master-view-link" data-view="${tenant.id}">View →</button>
          </div>
        </article>`;
      })
      .join("");

    bindRowEvents(els.cardList);
  }

  function bindRowEvents(container) {
    container.querySelectorAll("[data-tenant-id], [data-view]").forEach((el) => {
      el.addEventListener("click", (event) => {
        if (event.target.closest("[data-view]")) {
          event.stopPropagation();
        }
        const id = Number(el.dataset.tenantId || el.dataset.view);
        if (id) selectTenant(id);
      });
    });
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function selectTenant(id) {
    state.selectedId = id;
    renderTable();
    renderCards();
    els.detail.hidden = false;

    try {
      const data = await apiGet(`/master/tenants/${id}`);
      renderDetail(data.tenant);
    } catch (error) {
      renderDetail(state.tenants.find((row) => row.id === id));
      console.error(error);
    }
  }

  function renderDetail(tenant) {
    if (!tenant) return;

    document.getElementById("detail-name").textContent = tenant.name;
    const statusEl = document.getElementById("detail-status");
    statusEl.className = statusClass(tenant.status);
    statusEl.textContent = tenant.status;

    const limit = tenant.employees_limit || 0;
    const active = tenant.employees_active || 0;
    const pct = limit ? Math.min(100, Math.round((active / limit) * 100)) : 0;
    const trialTag =
      tenant.status === "trialing" && tenant.trial_days_remaining != null
        ? ` · ${tenant.trial_days_remaining} days left`
        : "";

    document.getElementById("detail-grid").innerHTML = `
      <div><dt>Location</dt><dd>${escapeHtml(tenant.location)}</dd></div>
      <div><dt>Contact</dt><dd>${escapeHtml(tenant.billing_email || "—")}</dd></div>
      <div><dt>Company number</dt><dd>${escapeHtml(tenant.company_number || "—")}</dd></div>
      <div><dt>Plan &amp; status</dt><dd>${escapeHtml(tenant.plan_label)} · ${escapeHtml(
        tenant.mrr_label
      )}${escapeHtml(trialTag)}</dd></div>
      <div><dt>Trial / renewal</dt><dd>${escapeHtml(formatDate(tenant.renewal_or_trial_date || tenant.trial_ends_at))}</dd></div>
      <div><dt>Employees</dt><dd>${active} active · ${tenant.employees_pending_portal || 0} portal setup pending
        <div class="master-staff-bar"><span style="width:${pct}%"></span></div>
        <small>${escapeHtml(tenant.staff_label)}</small></dd></div>
      <div><dt>Last active</dt><dd>${escapeHtml(tenant.last_active?.label || "—")}</dd></div>
      <div><dt>Signup date</dt><dd>${escapeHtml(formatDate(tenant.created_at))}</dd></div>
    `;

    const modules = tenant.modules || [];
    document.getElementById("detail-modules").innerHTML = modules
      .map(
        (mod) =>
          `<span class="master-module-pill ${mod.active ? "is-active" : "is-inactive"}">${escapeHtml(mod.label)}</span>`
      )
      .join("");

    const notes = document.getElementById("detail-notes");
    if (notes) notes.value = tenant.internal_notes || "";

    const impersonateBtn = document.getElementById("detail-impersonate");
    if (impersonateBtn) {
      impersonateBtn.disabled = false;
      impersonateBtn.textContent = "Impersonate this account";
      impersonateBtn.onclick = () => impersonateTenant(tenant);
    }
  }

  function closeDetail() {
    state.selectedId = null;
    els.detail.hidden = true;
    renderTable();
    renderCards();
  }

  function renderPageSub() {
    const total = state.overview?.total_tenants ?? state.tenants.length;
    els.pageSub.textContent = `All businesses registered on ShiftSwift HR · ${state.providerName} · ${total} tenants`;
    els.providerName.textContent = state.providerName;
  }

  function exportCsv() {
    const header = ["Business", "Location", "Plan", "Status", "Trial/Renewal", "Staff", "MRR", "Last active", "Email"];
    const lines = state.tenants.map((tenant) =>
      [
        tenant.name,
        tenant.location,
        tenant.plan_label,
        tenant.status,
        tenant.renewal_or_trial_date || tenant.trial_ends_at || "",
        tenant.staff_label,
        tenant.mrr_gbp ?? "",
        tenant.last_active?.label || "",
        tenant.billing_email || "",
      ]
        .map((cell) => `"${String(cell).replace(/"/g, '""')}"`)
        .join(",")
    );
    const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `shiftswift-tenants-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function loadTenants() {
    state.loading = true;
    const params = new URLSearchParams();
    if (state.filter && state.filter !== "all") params.set("status", state.filter);
    if (state.search.trim()) params.set("q", state.search.trim());

    try {
      const data = await apiGet(`/master/tenants?${params.toString()}`);
      state.tenants = data.tenants || [];
      state.overview = data.overview || state.overview;
      if (data.provider_name) state.providerName = data.provider_name;
      renderMetrics();
      renderFilters();
      renderTable();
      renderCards();
      renderPageSub();
      els.exportBtn.disabled = state.tenants.length === 0;
    } catch (error) {
      els.pageSub.textContent = error.message || "Failed to load tenants";
      if (String(error.message).includes("401") || /authorization|token/i.test(String(error.message))) {
        window.location.replace("./ops-9x7k2.html");
      }
    } finally {
      state.loading = false;
    }
  }

  async function bootstrap() {
    try {
      const verify = await apiGet("/auth/verify");
      const name = verify.username || "Platform owner";
      els.userName.textContent = name.split("@")[0].replace(/\./g, " ");
      els.userAvatar.textContent = initials(name.split("@")[0]);
    } catch {
      window.location.replace("./ops-9x7k2.html");
      return;
    }

    try {
      const overview = await apiGet("/master/overview");
      state.overview = overview.stats;
      if (overview.provider_name) state.providerName = overview.provider_name;
    } catch (error) {
      console.warn(error);
    }

    await loadTenants();
  }

  let searchTimer;
  els.search?.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.search = els.search.value;
      loadTenants();
    }, 250);
  });

  els.detailClose?.addEventListener("click", closeDetail);
  els.exportBtn?.addEventListener("click", exportCsv);

  function openSidebar() {
    els.sidebar?.classList.add("is-open");
    if (els.overlay) {
      els.overlay.hidden = false;
      els.overlay.setAttribute("aria-hidden", "false");
    }
  }

  function closeSidebar() {
    els.sidebar?.classList.remove("is-open");
    if (els.overlay) {
      els.overlay.hidden = true;
      els.overlay.setAttribute("aria-hidden", "true");
    }
  }

  els.menuBtn?.addEventListener("click", openSidebar);
  els.sidebarClose?.addEventListener("click", closeSidebar);
  els.overlay?.addEventListener("click", closeSidebar);

  bootstrap();
})();
