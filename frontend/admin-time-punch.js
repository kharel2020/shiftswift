/** Admin — geofenced time punch sites and punch log. */
(async function initAdminTimePunch() {
  const { apiFetch, renderTableBody, escapeHtml, parseHashBaseSection } = window.Admin;

  let sectionReady = false;

  function updatePunchStats(sites, punches) {
    const siteItems = sites || [];
    const punchItems = punches || [];
    const sitesEl = document.getElementById("punch-stat-sites");
    const punchesEl = document.getElementById("punch-stat-punches");
    const primaryEl = document.getElementById("punch-stat-primary");
    const primarySubEl = document.getElementById("punch-stat-primary-sub");
    if (sitesEl) sitesEl.textContent = String(siteItems.length);
    if (punchesEl) punchesEl.textContent = String(punchItems.length);
    const primary = siteItems.find((s) => s.is_primary) || siteItems[0];
    if (primaryEl) {
      primaryEl.textContent = primary ? (primary.is_active ? "Set" : "Inactive") : "None";
    }
    if (primarySubEl) {
      primarySubEl.textContent = primary ? primary.name : "Sync from business address";
    }
  }

  async function loadSites() {
    const tbody = document.getElementById("punch-sites-body");
    if (!tbody) return [];
    try {
      const res = await apiFetch("/admin/time-punch/sites");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      const rows = data.items || [];
      renderTableBody(tbody, {
        emptyMessage: "No punch sites yet. Sync from your business address.",
        columns: [
          { key: "name", render: (r) => `<strong>${escapeHtml(r.name)}</strong>` },
          { key: "address", render: (r) => escapeHtml(r.address) },
          {
            key: "coords",
            render: (r) => `${Number(r.latitude).toFixed(5)}, ${Number(r.longitude).toFixed(5)}`,
          },
          { key: "radius_meters", render: (r) => `${r.radius_meters}m` },
          { key: "is_primary", render: (r) => (r.is_primary ? "Primary" : "Not set") },
          { key: "is_active", render: (r) => (r.is_active ? "Active" : "Inactive") },
        ],
        rows: rows,
      });
      return rows;
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }, { key: "f" }],
        rows: [],
        emptyMessage: "Could not load punch sites.",
      });
      return [];
    }
  }

  async function loadPunches() {
    const tbody = document.getElementById("recent-punches-body");
    if (!tbody) return [];
    try {
      const res = await apiFetch("/admin/time-punch/punches?limit=50");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      const rows = data.items || [];
      renderTableBody(tbody, {
        emptyMessage: "No punches recorded yet.",
        columns: [
          {
            key: "punched_at",
            render: (r) => {
              try {
                return new Date(r.punched_at).toLocaleString("en-GB");
              } catch {
                return escapeHtml(r.punched_at);
              }
            },
          },
          { key: "employee_name", render: (r) => escapeHtml(r.employee_name) },
          { key: "punch_type", render: (r) => (r.punch_type === "in" ? "Clock in" : "Clock out") },
          { key: "site_name", render: (r) => escapeHtml(r.site_name) },
          {
            key: "distance_meters",
            render: (r) => (r.distance_meters != null ? `${Math.round(r.distance_meters)}m` : "Not set"),
          },
        ],
        rows,
      });
      return rows;
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }],
        rows: [],
        emptyMessage: "Could not load punches.",
      });
      return [];
    }
  }

  async function syncFromAddress() {
    const btn = document.getElementById("sync-punch-site-btn");
    const msg = document.getElementById("punch-admin-message");
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
      const [sites, punches] = await Promise.all([loadSites(), loadPunches()]);
      updatePunchStats(sites, punches);
    } catch (error) {
      if (msg) msg.textContent = error.message || "Sync failed.";
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function initSection() {
    document.getElementById("sync-punch-site-btn")?.addEventListener("click", syncFromAddress);
    const [sites, punches] = await Promise.all([loadSites(), loadPunches()]);
    updatePunchStats(sites, punches);
  }

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "time-punch" && !sectionReady) {
      sectionReady = true;
      initSection();
    }
  });

  if (parseHashBaseSection(window.location.hash) === "time-punch") {
    sectionReady = true;
    initSection();
  }
})();
