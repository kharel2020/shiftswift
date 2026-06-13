/** Admin — geofenced time punch sites and punch log. */
(function () {
  const { apiFetch, escapeHtml, parseHashBaseSection, downloadAuthenticated } = window.Admin;

  const ROLE_LABELS = {
    all: "All staff",
    kitchen: "Kitchen",
    front_of_house: "Front of house",
    bar: "Bar",
    management: "Management",
  };

  let sites = [];
  let punches = [];
  let todayPunches = [];
  let weekPunches = [];
  let employees = [];
  let tenantProfile = null;
  let selectedSiteId = null;
  let activeTab = "sites";
  let filters = { date_from: "", date_to: "", employee_id: "", site_id: "", punch_type: "" };
  let bound = false;

  function $(id) {
    return document.getElementById(id);
  }

  function haversineMeters(lat1, lon1, lat2, lon2) {
    const radius = 6371000;
    const phi1 = (lat1 * Math.PI) / 180;
    const phi2 = (lat2 * Math.PI) / 180;
    const dphi = ((lat2 - lat1) * Math.PI) / 180;
    const dlambda = ((lon2 - lon1) * Math.PI) / 180;
    const a =
      Math.sin(dphi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlambda / 2) ** 2;
    return 2 * radius * Math.asin(Math.sqrt(a));
  }

  function todayIso() {
    return new Date().toISOString().slice(0, 10);
  }

  function mondayIso(d = new Date()) {
    const day = new Date(d);
    const diff = (day.getDay() + 6) % 7;
    day.setDate(day.getDate() - diff);
    return day.toISOString().slice(0, 10);
  }

  function formatWhen(iso) {
    try {
      return new Date(iso).toLocaleString("en-GB", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso || "";
    }
  }

  function formatTimeShort(iso) {
    try {
      return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  }

  function formatSyncShort(iso) {
    if (!iso) return "never";
    try {
      const d = new Date(iso);
      const date = d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
      const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
      return `${date} ${time}`;
    } catch {
      return iso;
    }
  }

  function lastSyncIso() {
    const primary = primarySite();
    return primary?.updated_at || localStorage.getItem("punch-last-sync-at") || null;
  }

  function lastSyncLabel() {
    return `Last: ${formatSyncShort(lastSyncIso())}`;
  }

  function hasBusinessAddress() {
    return Boolean(String(tenantProfile?.registered_address || "").trim());
  }

  function primarySite() {
    return sites.find((s) => s.is_primary) || sites[0] || null;
  }

  function roleLabel(value) {
    if (!value || value === "all") return "All staff";
    if (ROLE_LABELS[value]) return ROLE_LABELS[value];
    return value.replace(/_/g, " ").replace(/,/g, ", ");
  }

  function punchWithinGeofence(punch) {
    if (punch.admin_override) return true;
    if (punch.within_geofence === false) return false;
    if (punch.distance_meters != null && punch.radius_meters != null) {
      return punch.distance_meters <= punch.radius_meters;
    }
    return punch.within_geofence !== false;
  }

  function renderDistanceCell(punch) {
    if (punch.admin_override) {
      return '<span class="punch-distance punch-distance--admin" title="Admin override">Admin</span>';
    }
    if (punch.distance_meters == null) return '<span class="muted">—</span>';
    const within = punchWithinGeofence(punch);
    if (within) {
      return `<span class="punch-distance punch-distance--ok" title="Within geofence">✓ ${Math.round(punch.distance_meters)}m</span>`;
    }
    return `<span class="punch-distance punch-distance--warn" title="Outside geofence">⚠ ${Math.round(punch.distance_meters)}m</span>`;
  }

  function renderTypeBadge(type) {
    return type === "in"
      ? '<span class="punch-type-badge punch-type-badge--in">Clock in</span>'
      : '<span class="punch-type-badge punch-type-badge--out">Clock out</span>';
  }

  function showMessage(text, tone) {
    const msg = $("punch-admin-message");
    if (!msg) return;
    if (!text) {
      msg.hidden = true;
      msg.textContent = "";
      msg.className = "muted punch-admin-message";
      return;
    }
    msg.hidden = false;
    msg.textContent = text;
    msg.className = tone === "ok" ? "punch-admin-message punch-admin-message--ok" : "muted punch-admin-message";
  }

  function updateSetupUi() {
    const warning = $("punch-address-warning");
    const setupGuide = $("punch-setup-guide");
    const selectHint = $("punch-detail-select-hint");
    const noSites = !sites.length;

    if (warning) warning.hidden = hasBusinessAddress();
    const syncMeta = $("punch-sync-meta");
    if (syncMeta) syncMeta.textContent = lastSyncLabel();

    if (setupGuide && selectHint) {
      if (noSites) {
        setupGuide.hidden = false;
        selectHint.hidden = true;
      } else if (!selectedSiteId) {
        setupGuide.hidden = true;
        selectHint.hidden = false;
      } else {
        setupGuide.hidden = true;
        selectHint.hidden = true;
      }
    }
  }

  function updatePunchStats() {
    const siteItems = sites || [];
    const todayItems = todayPunches || [];
    $("punch-stat-sites").textContent = String(siteItems.length);
    $("punch-stat-today").textContent = String(todayItems.length);

    const lastToday = todayItems[0];
    $("punch-stat-today-sub").textContent = lastToday
      ? `Last punch ${formatTimeShort(lastToday.punched_at)}`
      : "No punches yet";

    const primary = primarySite();
    if (primary) {
      $("punch-stat-primary").textContent = primary.name;
      const addressLine = String(primary.address || "").split(",")[0]?.trim();
      $("punch-stat-primary-sub").textContent = addressLine || "Main clock location";
      $("punch-stat-radius").textContent = `${primary.radius_meters}m`;
      $("punch-stat-radius-sub").textContent = "Staff must be on site to punch";
    } else {
      $("punch-stat-primary").textContent = "None";
      $("punch-stat-primary-sub").textContent = "Not configured";
      $("punch-stat-radius").textContent = "—";
      $("punch-stat-radius-sub").textContent = "Set up a punch site first";
    }
    updateSetupUi();
  }

  function setActiveTab(tab) {
    activeTab = tab;
    document.querySelectorAll(".punch-view-tab").forEach((btn) => {
      const isActive = btn.dataset.punchTab === tab;
      btn.classList.toggle("is-active", isActive);
      btn.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    document.querySelectorAll(".punch-tab-panel").forEach((panel) => {
      panel.hidden = panel.dataset.punchPanel !== tab;
    });
    if (tab === "summary") renderActivityChart();
  }

  function populateSelect(select, items, placeholder) {
    if (!select) return;
    const current = select.value;
    select.innerHTML = `<option value="">${escapeHtml(placeholder)}</option>`;
    items.forEach((item) => {
      const opt = document.createElement("option");
      opt.value = String(item.value);
      opt.textContent = item.label;
      select.appendChild(opt);
    });
    if (current && [...select.options].some((o) => o.value === current)) {
      select.value = current;
    }
  }

  function refreshFilterSelects() {
    const employeeOptions = employees.map((e) => ({
      value: e.id,
      label: `${e.first_name} ${e.last_name}`.trim(),
    }));
    populateSelect($("punch-filter-employee"), employeeOptions, "All employees");
    populateSelect($("punch-admin-employee"), employeeOptions, "Select employee…");
    populateSelect(
      $("punch-filter-site"),
      sites.map((s) => ({ value: s.id, label: s.name })),
      "All sites"
    );
    populateSelect(
      $("punch-admin-site"),
      sites.filter((s) => s.is_active).map((s) => ({ value: s.id, label: s.name })),
      "Select site…"
    );
  }

  function geofenceVizSvg(radiusMeters) {
    return `
      <div class="punch-geofence-viz" aria-hidden="true">
        <svg viewBox="0 0 220 220" class="punch-geofence-viz__svg">
          <rect width="220" height="220" rx="12" fill="#f0faf6"/>
          <circle cx="110" cy="110" r="78" fill="none" stroke="#74c69d" stroke-width="2" stroke-dasharray="6 5"/>
          <circle cx="110" cy="110" r="8" fill="#1b4332"/>
          <text x="110" y="198" text-anchor="middle" font-size="12" fill="#52796f">${escapeHtml(String(radiusMeters))}m radius</text>
        </svg>
      </div>`;
  }

  function siteTodayStats(siteId) {
    const items = todayPunches.filter((p) => p.punch_site_id === siteId);
    const outside = items.filter((p) => !punchWithinGeofence(p)).length;
    return { total: items.length, outside };
  }

  function outsideAlertsForSite(site) {
    return todayPunches.filter(
      (p) => p.punch_site_id === site.id && !punchWithinGeofence(p) && !p.admin_override
    );
  }

  function renderSiteDetail(site) {
    const empty = $("punch-detail-empty");
    const content = $("punch-detail-content");
    if (!content || !site) return;
    empty?.setAttribute("hidden", "");
    content.hidden = false;

    const stats = siteTodayStats(site.id);
    const outside = outsideAlertsForSite(site);
    const alertsHtml = outside
      .map(
        (p) =>
          `<div class="alert-card alert-card-warning punch-site-alert"><p class="alert-copy">Outside geofence: <strong>${escapeHtml(p.employee_name)}</strong> clocked ${p.punch_type === "in" ? "in" : "out"} at ${Math.round(p.distance_meters || 0)}m — limit ${site.radius_meters}m.</p></div>`
      )
      .join("");

    content.innerHTML = `
      <div class="hr-detail-head"><div><h3>${escapeHtml(site.name)}</h3><span class="contracts-status-pill contracts-status-pill--${site.is_active ? "signed" : "draft"}">${site.is_active ? "Active" : "Inactive"}</span></div></div>
      <dl class="hr-detail-grid">
        <div><dt>Address</dt><dd>${escapeHtml(site.address)}</dd></div>
        <div><dt>Geofence radius</dt><dd>${escapeHtml(site.radius_meters)} metres</dd></div>
        <div><dt>Permitted roles</dt><dd>${escapeHtml(roleLabel(site.permitted_roles))}</dd></div>
        <div><dt>Last synced</dt><dd>${escapeHtml(formatSyncShort(site.updated_at || lastSyncIso()))}</dd></div>
        <div><dt>Today's punches</dt><dd>${stats.total} punch${stats.total === 1 ? "" : "es"}${stats.outside ? ` · <span class="punch-outside-count">${stats.outside} outside geofence</span>` : ""}</dd></div>
      </dl>
      ${geofenceVizSvg(site.radius_meters)}
      ${alertsHtml}
      <div id="punch-edit-form-wrap" hidden></div>
      <div class="hr-detail-foot">
        <button type="button" class="btn outline" id="punch-test-geofence-btn"><span aria-hidden="true">◎</span> Test geofence</button>
        <button type="button" class="btn ghost" id="punch-edit-site-btn"><span aria-hidden="true">✎</span> Edit site</button>
      </div>
      <p id="punch-geofence-test-result" class="muted punch-geofence-result" aria-live="polite"></p>`;

    content.querySelector("#punch-test-geofence-btn")?.addEventListener("click", () => testGeofence(site));
    content.querySelector("#punch-edit-site-btn")?.addEventListener("click", () => showEditSiteForm(site));
    updateSetupUi();
  }

  function showEditSiteForm(site) {
    const wrap = $("punch-edit-form-wrap");
    if (!wrap) return;
    wrap.hidden = false;
    wrap.innerHTML = `
      <form id="punch-edit-form" class="punch-inline-form punch-edit-form">
        <label class="edit-field"><span class="edit-label">Site name</span><input type="text" name="name" value="${escapeHtml(site.name)}" required /></label>
        <label class="edit-field"><span class="edit-label">Radius (metres)</span><input type="number" name="radius_meters" min="25" max="2000" value="${site.radius_meters}" required /></label>
        <label class="edit-field"><span class="edit-label">Permitted roles</span>
          <select name="permitted_roles">
            <option value="all" ${site.permitted_roles === "all" ? "selected" : ""}>All staff</option>
            <option value="kitchen" ${site.permitted_roles === "kitchen" ? "selected" : ""}>Kitchen</option>
            <option value="front_of_house" ${site.permitted_roles === "front_of_house" ? "selected" : ""}>Front of house</option>
            <option value="bar" ${site.permitted_roles === "bar" ? "selected" : ""}>Bar</option>
            <option value="management" ${site.permitted_roles === "management" ? "selected" : ""}>Management</option>
          </select>
        </label>
        <div class="punch-inline-form__actions">
          <button type="submit" class="btn primary">Save changes</button>
          <button type="button" class="btn ghost" id="punch-edit-cancel">Cancel</button>
        </div>
      </form>`;
    wrap.querySelector("#punch-edit-cancel")?.addEventListener("click", () => {
      wrap.hidden = true;
      wrap.innerHTML = "";
    });
    wrap.querySelector("#punch-edit-form")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      await saveSiteEdit(site.id, event.currentTarget);
    });
  }

  async function saveSiteEdit(siteId, form) {
    const payload = {
      name: form.name.value.trim(),
      radius_meters: Number(form.radius_meters.value),
      permitted_roles: form.permitted_roles.value,
    };
    try {
      const res = await apiFetch(`/admin/time-punch/sites/${siteId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showMessage(data.detail || "Could not save site.");
        return;
      }
      showMessage("Site updated.", "ok");
      await loadSites();
      selectedSiteId = siteId;
      renderSiteDetail(sites.find((s) => s.id === siteId));
      updatePunchStats();
    } catch (error) {
      showMessage(error.message || "Could not save site.");
    }
  }

  function testGeofence(site) {
    const result = $("punch-geofence-test-result");
    if (!navigator.geolocation) {
      if (result) result.textContent = "Geolocation is not available in this browser.";
      return;
    }
    if (result) result.textContent = "Checking your location…";
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const distance = haversineMeters(
          pos.coords.latitude,
          pos.coords.longitude,
          site.latitude,
          site.longitude
        );
        const within = distance <= site.radius_meters;
        if (result) {
          result.textContent = within
            ? `Inside geofence — ~${Math.round(distance)}m from site (limit ${site.radius_meters}m).`
            : `Outside geofence — ~${Math.round(distance)}m from site (limit ${site.radius_meters}m). Adjust radius if needed.`;
          result.className = within
            ? "punch-geofence-result punch-geofence-result--ok"
            : "punch-geofence-result punch-geofence-result--warn";
        }
      },
      (error) => {
        if (result) result.textContent = error.message || "Could not read your location.";
      },
      { enableHighAccuracy: true, timeout: 15000 }
    );
  }

  function renderSitesTable() {
    const tbody = $("punch-sites-body");
    if (!tbody) return;
    if (!sites.length) {
      tbody.innerHTML =
        '<tr><td colspan="5" class="muted">No punch sites yet. Sync from address or add one manually.</td></tr>';
      return;
    }
    tbody.innerHTML = sites
      .map((row) => {
        const selected = selectedSiteId === row.id ? " hr-register-row--selected" : "";
        return `<tr class="hr-register-row${selected}" data-site-id="${row.id}">
          <td><strong>${escapeHtml(row.name)}</strong></td>
          <td>${escapeHtml(row.address)}</td>
          <td>${row.radius_meters}m</td>
          <td>${escapeHtml(roleLabel(row.permitted_roles))}</td>
          <td>${row.is_active ? "Active" : "Inactive"}</td>
        </tr>`;
      })
      .join("");
    tbody.querySelectorAll("[data-site-id]").forEach((row) => {
      row.addEventListener("click", () => {
        selectedSiteId = Number(row.dataset.siteId);
        renderSitesTable();
        renderSiteDetail(sites.find((s) => s.id === selectedSiteId));
      });
    });
  }

  function renderTodayPreview() {
    const tbody = $("punch-today-preview-body");
    if (!tbody) return;
    if (!todayPunches.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="muted">No punches today.</td></tr>';
      return;
    }
    tbody.innerHTML = todayPunches
      .slice(0, 8)
      .map(
        (row) => `<tr>
          <td>${escapeHtml(formatTimeShort(row.punched_at))}</td>
          <td>${escapeHtml(row.employee_name)}</td>
          <td>${renderTypeBadge(row.punch_type)}</td>
          <td>${renderDistanceCell(row)}</td>
        </tr>`
      )
      .join("");
  }

  function renderPunchesTable() {
    const tbody = $("recent-punches-body");
    if (!tbody) return;
    if (!punches.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="muted">No punches match your filters.</td></tr>';
      return;
    }
    tbody.innerHTML = punches
      .map(
        (row) => `<tr class="hr-register-row">
          <td>${escapeHtml(formatWhen(row.punched_at))}</td>
          <td>${escapeHtml(row.employee_name)}</td>
          <td>${renderTypeBadge(row.punch_type)}</td>
          <td>${escapeHtml(row.site_name)}</td>
          <td>${renderDistanceCell(row)}</td>
        </tr>`
      )
      .join("");
  }

  function renderActivityChart() {
    const host = $("punch-activity-chart");
    if (!host) return;
    const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const counts = [0, 0, 0, 0, 0, 0, 0];
    const weekStart = new Date(`${mondayIso()}T00:00:00`);
    weekPunches.forEach((p) => {
      const d = new Date(p.punched_at);
      const idx = (d.getDay() + 6) % 7;
      if (d >= weekStart) counts[idx] += 1;
    });
    const max = Math.max(...counts, 1);
    const todayIdx = (new Date().getDay() + 6) % 7;
    const avg = counts.reduce((a, b) => a + b, 0) / 7;

    host.innerHTML = `
      <div class="punch-chart-bars">
        ${days
          .map((label, idx) => {
            const height = Math.round((counts[idx] / max) * 100);
            const classes = [
              "punch-chart-bar",
              idx === todayIdx ? "punch-chart-bar--today" : "",
              counts[idx] > 0 && counts[idx] < avg * 0.6 ? "punch-chart-bar--low" : "",
            ]
              .filter(Boolean)
              .join(" ");
            return `<div class="punch-chart-col">
              <div class="${classes}" style="height:${Math.max(height, 6)}%" title="${counts[idx]} punches"><span>${counts[idx]}</span></div>
              <span class="punch-chart-label">${label}</span>
            </div>`;
          })
          .join("")}
      </div>`;
  }

  function buildPunchQuery(extra) {
    const params = new URLSearchParams({ limit: "50", ...extra });
    if (filters.date_from) params.set("date_from", filters.date_from);
    if (filters.date_to) params.set("date_to", filters.date_to);
    if (filters.employee_id) params.set("employee_id", filters.employee_id);
    if (filters.site_id) params.set("site_id", filters.site_id);
    if (filters.punch_type) params.set("punch_type", filters.punch_type);
    return `/admin/time-punch/punches?${params.toString()}`;
  }

  async function loadTenantProfile() {
    try {
      const res = await apiFetch("/admin/tenant-profile");
      if (!res.ok) throw new Error("Load failed");
      tenantProfile = await res.json();
    } catch {
      tenantProfile = null;
    }
  }

  async function loadEmployeeList() {
    try {
      const res = await apiFetch("/admin/employees");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      employees = data.items || [];
    } catch {
      employees = [];
    }
    refreshFilterSelects();
  }

  async function loadSites() {
    try {
      const res = await apiFetch("/admin/time-punch/sites");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      sites = data.items || [];
    } catch {
      sites = [];
    }
    renderSitesTable();
    refreshFilterSelects();
    if (sites.length && !selectedSiteId) {
      selectedSiteId = primarySite()?.id || sites[0].id;
      renderSiteDetail(sites.find((s) => s.id === selectedSiteId));
      renderSitesTable();
    }
  }

  async function loadPunches() {
    try {
      const res = await apiFetch(buildPunchQuery());
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      punches = data.items || [];
    } catch {
      punches = [];
    }
    renderPunchesTable();
  }

  async function loadTodayPunches() {
    const iso = todayIso();
    try {
      const res = await apiFetch(`/admin/time-punch/punches?limit=100&date_from=${iso}&date_to=${iso}`);
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      todayPunches = data.items || [];
    } catch {
      todayPunches = [];
    }
    renderTodayPreview();
  }

  async function loadWeekPunches() {
    try {
      const res = await apiFetch(
        `/admin/time-punch/punches?limit=500&date_from=${mondayIso()}&date_to=${todayIso()}`
      );
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      weekPunches = data.items || [];
    } catch {
      weekPunches = [];
    }
    renderActivityChart();
  }

  async function syncFromAddress(sourceBtn) {
    const btn = sourceBtn || $("sync-punch-site-btn");
    if (btn) btn.disabled = true;
    showMessage("Syncing from registered business address…");
    try {
      const res = await apiFetch("/admin/time-punch/sites/sync-from-address", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showMessage(data.detail || "Sync failed.");
        updateSetupUi();
        return;
      }
      localStorage.setItem("punch-last-sync-at", new Date().toISOString());
      showMessage(`Synced primary site: ${data.name}`, "ok");
      selectedSiteId = data.id;
      await Promise.all([loadSites(), loadTodayPunches(), loadWeekPunches()]);
      updatePunchStats();
    } catch (error) {
      showMessage(error.message || "Sync failed.");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function resolveRadius(form) {
    const preset = form.radius_preset.value;
    if (preset === "custom") return Number(form.radius_custom.value);
    return Number(preset);
  }

  function resolvePermittedRoles(form) {
    const preset = form.permitted_roles.value;
    if (preset === "custom") return form.permitted_roles_custom.value.trim() || "all";
    return preset;
  }

  async function submitManualSite(form) {
    const payload = {
      name: form.name.value.trim(),
      address: form.address.value.trim(),
      radius_meters: resolveRadius(form),
      permitted_roles: resolvePermittedRoles(form),
    };
    showMessage("Adding punch site…");
    try {
      const res = await apiFetch("/admin/time-punch/sites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showMessage(data.detail || "Could not add site.");
        return;
      }
      form.reset();
      $("punch-manual-form").hidden = true;
      showMessage(`Added punch site: ${data.name}`, "ok");
      selectedSiteId = data.id;
      await loadSites();
      renderSiteDetail(data);
      updatePunchStats();
    } catch (error) {
      showMessage(error.message || "Could not add site.");
    }
  }

  async function submitAdminPunch(form) {
    const payload = {
      employee_id: Number(form.employee_id.value),
      punch_site_id: Number(form.punch_site_id.value),
      punch_type: form.punch_type.value,
      admin_note: form.admin_note.value.trim() || null,
    };
    if (form.punched_at.value) {
      payload.punched_at = new Date(form.punched_at.value).toISOString();
    }
    showMessage("Recording admin punch…");
    try {
      const res = await apiFetch("/admin/time-punch/punches/admin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showMessage(data.detail || "Could not record punch.");
        return;
      }
      form.admin_note.value = "";
      showMessage(
        `Recorded ${data.punch_type === "in" ? "clock in" : "clock out"} for ${data.employee_name}`,
        "ok"
      );
      await Promise.all([loadPunches(), loadTodayPunches(), loadWeekPunches()]);
      if (selectedSiteId) renderSiteDetail(sites.find((s) => s.id === selectedSiteId));
      updatePunchStats();
    } catch (error) {
      showMessage(error.message || "Could not record punch.");
    }
  }

  async function exportPunchesCsv(useTodayOnly) {
    try {
      const params = new URLSearchParams();
      if (useTodayOnly) {
        params.set("date_from", todayIso());
        params.set("date_to", todayIso());
      } else {
        if (filters.date_from) params.set("date_from", filters.date_from);
        if (filters.date_to) params.set("date_to", filters.date_to);
        if (filters.employee_id) params.set("employee_id", filters.employee_id);
        if (filters.site_id) params.set("site_id", filters.site_id);
        if (filters.punch_type) params.set("punch_type", filters.punch_type);
      }
      const qs = params.toString();
      await downloadAuthenticated(
        `/admin/time-punch/punches/export.csv${qs ? `?${qs}` : ""}`,
        `time-punches-${new Date().toISOString().slice(0, 10)}.csv`
      );
      showMessage("Punch export downloaded.", "ok");
    } catch (error) {
      showMessage(error.message || "Export failed.");
    }
  }

  function bindEvents() {
    if (bound) return;
    bound = true;

    $("sync-punch-site-btn")?.addEventListener("click", (e) => syncFromAddress(e.currentTarget));
    $("punch-setup-sync-btn")?.addEventListener("click", (e) => syncFromAddress(e.currentTarget));

    document.querySelectorAll(".punch-view-tab").forEach((tab) => {
      tab.addEventListener("click", () => setActiveTab(tab.dataset.punchTab));
    });

    $("punch-header-export-btn")?.addEventListener("click", () => exportPunchesCsv(false));
    $("punch-header-admin-btn")?.addEventListener("click", () => {
      setActiveTab("log");
      $("punch-admin-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      $("punch-admin-employee")?.focus();
    });

    $("punch-add-site-btn")?.addEventListener("click", () => {
      $("punch-manual-form").hidden = false;
      setActiveTab("sites");
    });
    $("punch-hide-manual-btn")?.addEventListener("click", () => {
      $("punch-manual-form").hidden = true;
    });

    $("punch-radius-preset")?.addEventListener("change", (event) => {
      $("punch-radius-custom-wrap").hidden = event.target.value !== "custom";
    });
    $("punch-permitted-roles")?.addEventListener("change", (event) => {
      $("punch-roles-custom-wrap").hidden = event.target.value !== "custom";
    });

    $("punch-manual-form-el")?.addEventListener("submit", (event) => {
      event.preventDefault();
      submitManualSite(event.currentTarget);
    });

    $("punch-admin-form")?.addEventListener("submit", (event) => {
      event.preventDefault();
      submitAdminPunch(event.currentTarget);
    });

    $("punch-filter-apply")?.addEventListener("click", async () => {
      filters = {
        date_from: $("punch-filter-from")?.value || "",
        date_to: $("punch-filter-to")?.value || "",
        employee_id: $("punch-filter-employee")?.value || "",
        site_id: $("punch-filter-site")?.value || "",
        punch_type: $("punch-filter-type")?.value || "",
      };
      await loadPunches();
    });

    $("punch-filter-clear")?.addEventListener("click", async () => {
      filters = { date_from: "", date_to: "", employee_id: "", site_id: "", punch_type: "" };
      ["punch-filter-from", "punch-filter-to", "punch-filter-employee", "punch-filter-site", "punch-filter-type"].forEach(
        (id) => {
          const el = $(id);
          if (el) el.value = "";
        }
      );
      await loadPunches();
    });

    $("punch-export-csv-btn")?.addEventListener("click", () => exportPunchesCsv(false));
    $("punch-preview-export-btn")?.addEventListener("click", () => exportPunchesCsv(true));
  }

  async function initSection() {
    bindEvents();
    setActiveTab(activeTab);
    showMessage("");
    await Promise.all([
      loadTenantProfile(),
      loadEmployeeList(),
      loadSites(),
      loadPunches(),
      loadTodayPunches(),
      loadWeekPunches(),
    ]);
    updatePunchStats();
  }

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "time-punch") initSection();
  });

  if (parseHashBaseSection(window.location.hash) === "time-punch") initSection();
})();
