/** Admin — geofenced time punch sites and punch log. */
(function () {
  const { apiFetch, escapeHtml, parseHashBaseSection } = window.Admin;

  let sites = [];
  let punches = [];
  let selectedSiteId = null;
  let selectedPunchId = null;
  let syncBound = false;

  function $(id) {
    return document.getElementById(id);
  }

  function updatePunchStats() {
    const siteItems = sites || [];
    const punchItems = punches || [];
    $("punch-stat-sites").textContent = String(siteItems.length);
    $("punch-stat-punches").textContent = String(punchItems.length);
    const primary = siteItems.find((s) => s.is_primary) || siteItems[0];
    $("punch-stat-primary").textContent = primary ? (primary.is_active ? "Set" : "Inactive") : "None";
    $("punch-stat-primary-sub").textContent = primary ? primary.name : "Sync from business address";
  }

  function renderSiteDetail(site) {
    const empty = $("punch-detail-empty");
    const content = $("punch-detail-content");
    if (!content) return;
    empty?.setAttribute("hidden", "");
    content.hidden = false;
    content.innerHTML = `
      <div class="hr-detail-head"><div><h3>${escapeHtml(site.name)}</h3><span class="contracts-status-pill contracts-status-pill--${site.is_active ? "signed" : "draft"}">${site.is_active ? "Active" : "Inactive"}</span></div></div>
      <dl class="hr-detail-grid">
        <div><dt>Address</dt><dd>${escapeHtml(site.address)}</dd></div>
        <div><dt>Coordinates</dt><dd>${Number(site.latitude).toFixed(5)}, ${Number(site.longitude).toFixed(5)}</dd></div>
        <div><dt>Geofence radius</dt><dd>${escapeHtml(site.radius_meters)}m</dd></div>
        <div><dt>Role</dt><dd>${site.is_primary ? "Primary site" : "Secondary site"}</dd></div>
      </dl>
      <p class="muted">Staff must be within the geofence to clock in or out at this site.</p>`;
  }

  function renderPunchDetail(punch) {
    const empty = $("punch-detail-empty");
    const content = $("punch-detail-content");
    if (!content) return;
    empty?.setAttribute("hidden", "");
    content.hidden = false;
    let when = punch.punched_at;
    try {
      when = new Date(punch.punched_at).toLocaleString("en-GB");
    } catch {
      /* keep raw */
    }
    content.innerHTML = `
      <div class="hr-detail-head"><div><h3>${punch.punch_type === "in" ? "Clock in" : "Clock out"}</h3></div></div>
      <dl class="hr-detail-grid">
        <div><dt>When</dt><dd>${escapeHtml(when)}</dd></div>
        <div><dt>Employee</dt><dd>${escapeHtml(punch.employee_name)}</dd></div>
        <div><dt>Site</dt><dd>${escapeHtml(punch.site_name)}</dd></div>
        <div><dt>Distance from site</dt><dd>${punch.distance_meters != null ? `${Math.round(punch.distance_meters)}m` : "Not set"}</dd></div>
      </dl>`;
  }

  function renderSitesTable() {
    const tbody = $("punch-sites-body");
    if (!tbody) return;
    if (!sites.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="muted">No punch sites yet. Sync from your business address above.</td></tr>';
      return;
    }
    tbody.innerHTML = sites
      .map((row) => {
        const selected = selectedSiteId === row.id && !selectedPunchId ? " hr-register-row--selected" : "";
        return `<tr class="hr-register-row${selected}" data-site-id="${row.id}">
          <td><strong>${escapeHtml(row.name)}</strong></td>
          <td>${escapeHtml(row.address)}</td>
          <td>${Number(row.latitude).toFixed(5)}, ${Number(row.longitude).toFixed(5)}</td>
          <td>${row.radius_meters}m</td>
          <td>${row.is_primary ? "Primary" : "Secondary"}</td>
          <td>${row.is_active ? "Active" : "Inactive"}</td>
        </tr>`;
      })
      .join("");
    tbody.querySelectorAll("[data-site-id]").forEach((row) => {
      row.addEventListener("click", () => {
        selectedSiteId = Number(row.dataset.siteId);
        selectedPunchId = null;
        renderSitesTable();
        renderPunchesTable();
        renderSiteDetail(sites.find((s) => s.id === selectedSiteId));
      });
    });
  }

  function renderPunchesTable() {
    const tbody = $("recent-punches-body");
    if (!tbody) return;
    if (!punches.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="muted">No punches recorded yet.</td></tr>';
      return;
    }
    tbody.innerHTML = punches
      .map((row, index) => {
        const selected = selectedPunchId === index ? " hr-register-row--selected" : "";
        let when = row.punched_at;
        try {
          when = new Date(row.punched_at).toLocaleString("en-GB");
        } catch {
          /* keep */
        }
        return `<tr class="hr-register-row${selected}" data-punch-index="${index}">
          <td>${escapeHtml(when)}</td>
          <td>${escapeHtml(row.employee_name)}</td>
          <td>${row.punch_type === "in" ? "Clock in" : "Clock out"}</td>
          <td>${escapeHtml(row.site_name)}</td>
          <td>${row.distance_meters != null ? `${Math.round(row.distance_meters)}m` : "Not set"}</td>
        </tr>`;
      })
      .join("");
    tbody.querySelectorAll("[data-punch-index]").forEach((row) => {
      row.addEventListener("click", () => {
        selectedPunchId = Number(row.dataset.punchIndex);
        selectedSiteId = null;
        renderSitesTable();
        renderPunchesTable();
        renderPunchDetail(punches[selectedPunchId]);
      });
    });
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
  }

  async function loadPunches() {
    try {
      const res = await apiFetch("/admin/time-punch/punches?limit=50");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      punches = data.items || [];
    } catch {
      punches = [];
    }
    renderPunchesTable();
  }

  async function syncFromAddress() {
    const btn = $("sync-punch-site-btn");
    const msg = $("punch-admin-message");
    if (btn) btn.disabled = true;
    if (msg) msg.textContent = "Syncing from registered business address…";
    try {
      const res = await apiFetch("/admin/time-punch/sites/sync-from-address", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (msg) msg.textContent = data.detail || "Sync failed.";
        return;
      }
      if (msg) msg.textContent = `Synced primary site: ${data.name}`;
      await loadSites();
      updatePunchStats();
    } catch (error) {
      if (msg) msg.textContent = error.message || "Sync failed.";
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function initSection() {
    if (!syncBound) {
      $("sync-punch-site-btn")?.addEventListener("click", syncFromAddress);
      syncBound = true;
    }
    await Promise.all([loadSites(), loadPunches()]);
    updatePunchStats();
  }

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "time-punch") initSection();
  });

  if (parseHashBaseSection(window.location.hash) === "time-punch") initSection();
})();
