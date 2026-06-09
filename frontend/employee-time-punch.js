(function () {
  const API_BASE =
    localStorage.getItem("apiBaseUrl") ||
    (window.ShiftSwiftBrand?.resolveApiBase ? window.ShiftSwiftBrand.resolveApiBase() : "http://localhost:3000");
  const token = localStorage.getItem("token");
  const tenantId = localStorage.getItem("tenantId");

  if (!token || !tenantId) return;

  const statusEl = document.getElementById("punch-status");
  const sitesEl = document.getElementById("punch-sites");
  const messageEl = document.getElementById("punch-message");
  const clockInBtn = document.getElementById("punch-in-btn");
  const clockOutBtn = document.getElementById("punch-out-btn");

  function authHeaders() {
    return {
      Authorization: `Bearer ${token}`,
      "X-Tenant-Id": tenantId,
      "Content-Type": "application/json",
    };
  }

  function setMessage(text, type) {
    if (!messageEl) return;
    messageEl.textContent = text || "";
    messageEl.className = type ? `punch-message punch-message--${type}` : "punch-message";
  }

  function formatTime(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
    } catch {
      return iso;
    }
  }

  async function loadStatus() {
    if (!statusEl) return;
    try {
      const response = await fetch(`${API_BASE}/time-punch/status`, { headers: authHeaders() });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        statusEl.textContent = err.detail || "Could not load punch status.";
        return;
      }
      const data = await response.json();
      const last = data.last_punch;
      statusEl.innerHTML = data.clocked_in
        ? `<strong>Clocked in</strong> since ${formatTime(last?.punched_at)} at ${last?.site_name || "work site"}.`
        : last
          ? `Last punch: ${last.punch_type === "in" ? "in" : "out"} at ${formatTime(last.punched_at)}.`
          : "Not clocked in yet today.";
      if (sitesEl) {
        const sites = data.assigned_sites || [];
        sitesEl.innerHTML = sites.length
          ? sites.map((s) => `<li>${s.name} — ${s.address} (${s.radius_meters}m radius)</li>`).join("")
          : "<li>No punch sites configured — ask HR.</li>";
      }
      if (clockInBtn) clockInBtn.disabled = Boolean(data.clocked_in);
      if (clockOutBtn) clockOutBtn.disabled = !data.clocked_in;
    } catch {
      statusEl.textContent = "Could not reach the time punch service.";
    }
  }

  function readLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Location is not supported on this device."));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) =>
          resolve({
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            accuracy_meters: pos.coords.accuracy,
          }),
        (err) => reject(new Error(err.message || "Could not read your location.")),
        { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
      );
    });
  }

  async function submitPunch(punchType) {
    setMessage("Reading your location…", "info");
    try {
      const location = await readLocation();
      setMessage("Submitting punch…", "info");
      const response = await fetch(`${API_BASE}/time-punch/punch`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ punch_type: punchType, ...location }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setMessage(data.detail || "Punch failed.", "error");
        return;
      }
      setMessage(
        `${punchType === "in" ? "Clocked in" : "Clocked out"} at ${data.site_name} (${Math.round(data.distance_meters)}m from site).`,
        "success"
      );
      loadStatus();
    } catch (error) {
      setMessage(error.message || "Punch failed.", "error");
    }
  }

  clockInBtn?.addEventListener("click", () => submitPunch("in"));
  clockOutBtn?.addEventListener("click", () => submitPunch("out"));

  loadStatus();
})();
