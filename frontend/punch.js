(function () {
  const API_BASE =
    localStorage.getItem("apiBaseUrl") ||
    (window.ShiftSwiftBrand?.resolveApiBase ? window.ShiftSwiftBrand.resolveApiBase() : "http://localhost:3000");

  const loginView = document.getElementById("punch-login-view");
  const mfaView = document.getElementById("punch-mfa-view");
  const clockView = document.getElementById("punch-clock-view");
  const signOutBtn = document.getElementById("punch-sign-out");
  const loginForm = document.getElementById("punch-login-form");
  const mfaForm = document.getElementById("punch-mfa-form");
  const loginStatus = document.getElementById("punch-login-status");
  const mfaStatus = document.getElementById("punch-mfa-status");
  const statusEl = document.getElementById("punch-clock-status");
  const sitesEl = document.getElementById("punch-sites");
  const messageEl = document.getElementById("punch-message");
  const userLine = document.getElementById("punch-user-line");
  const clockInBtn = document.getElementById("punch-in-btn");
  const clockOutBtn = document.getElementById("punch-out-btn");
  const installBanner = document.getElementById("pwa-install-banner");
  const installBtn = document.getElementById("pwa-install-btn");
  const installDismiss = document.getElementById("pwa-install-dismiss");
  const installCopy = document.getElementById("pwa-install-copy");
  const offlineBanner = document.getElementById("punch-offline-banner");
  const updateBanner = document.getElementById("punch-update-banner");
  const updateBtn = document.getElementById("punch-update-btn");
  const expectedShiftEl = document.getElementById("punch-expected-shift");
  const weekShiftsEl = document.getElementById("punch-week-shifts");

  let pendingChallenge = null;
  let deferredInstallPrompt = null;
  let punchInFlight = false;
  let refreshInFlight = null;
  let clockedInState = false;
  let waitingServiceWorker = null;

  function secureHostLabel() {
    const fromBrand = window.ShiftSwiftBrand?.domain;
    if (fromBrand) return fromBrand;
    if (window.location.hostname) {
      return String(window.location.hostname).replace(/^www\./i, "");
    }
    return "shiftswifthr.co.uk";
  }

  document.querySelectorAll("[data-secure-host]").forEach((el) => {
    el.textContent = secureHostLabel();
  });

  function token() {
    return localStorage.getItem("token");
  }

  function tenantId() {
    return localStorage.getItem("tenantId");
  }

  function authHeaders(json = true) {
    const headers = {
      Authorization: `Bearer ${token()}`,
      "X-Tenant-Id": tenantId() || "",
    };
    if (json) headers["Content-Type"] = "application/json";
    return headers;
  }

  function parseApiError(data, fallback) {
    const detail = data?.detail;
    if (typeof detail === "string") return detail;
    if (typeof detail === "object" && detail?.message) return detail.message;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
    return data?.message || fallback;
  }

  function setInlineStatus(el, message) {
    if (!el) return;
    if (message) {
      el.textContent = message;
      el.hidden = false;
    } else {
      el.textContent = "";
      el.hidden = true;
    }
  }

  function showView(view) {
    [loginView, mfaView, clockView].forEach((node) => {
      if (!node) return;
      node.hidden = node !== view;
    });
    if (signOutBtn) signOutBtn.hidden = view !== clockView;
  }

  function clearSession() {
    localStorage.removeItem("token");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("tenantId");
    localStorage.removeItem("userRole");
  }

  function storeSession(data) {
    if (data.access_token) localStorage.setItem("token", data.access_token);
    if (data.refresh_token) localStorage.setItem("refreshToken", data.refresh_token);
    if (data.role) localStorage.setItem("userRole", data.role);
    if (data.tenant_id) localStorage.setItem("tenantId", String(data.tenant_id));
  }

  function setOnlineState(online) {
    if (offlineBanner) offlineBanner.hidden = online;
    syncClockButtons();
  }

  function syncClockButtons() {
    const online = navigator.onLine;
    if (clockInBtn) {
      clockInBtn.disabled = punchInFlight || !online || clockedInState;
    }
    if (clockOutBtn) {
      clockOutBtn.disabled = punchInFlight || !online || !clockedInState;
    }
  }

  async function refreshAccessToken() {
    if (refreshInFlight) return refreshInFlight;
    const refresh = localStorage.getItem("refreshToken");
    if (!refresh) return false;

    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) return false;
        storeSession(data);
        return true;
      } catch {
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();

    return refreshInFlight;
  }

  async function apiFetch(path, options = {}) {
    const request = async () =>
      fetch(`${API_BASE}${path}`, {
        ...options,
        headers: { ...authHeaders(options.body != null), ...(options.headers || {}) },
      });

    let response;
    try {
      response = await request();
    } catch {
      throw new Error("Cannot reach the API. Check your connection and try again.");
    }

    if (response.status === 401) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        try {
          response = await request();
        } catch {
          throw new Error("Cannot reach the API. Check your connection and try again.");
        }
      }
    }
    return response;
  }

  async function postJson(path, body) {
    const response = await apiFetch(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(parseApiError(data, "Request failed"));
    }
    return data;
  }

  function friendlyLoginError(message) {
    if (message === "Failed to fetch" || message === "Load failed") {
      return "Cannot reach the API. Check your connection and try again.";
    }
    if (message === "Invalid credentials for this login type") {
      return "Use your employee account here. HR admins should sign in via the business portal.";
    }
    return message || "Sign in failed";
  }

  function formatTime(iso) {
    if (!iso) return "Not set";
    try {
      return new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
    } catch {
      return iso;
    }
  }

  function setMessage(text, type) {
    if (!messageEl) return;
    messageEl.textContent = text || "";
    messageEl.className = type ? `punch-message punch-message--${type}` : "punch-message";
  }

  async function verifyEmployeeSession() {
    const currentToken = token();
    if (!currentToken) {
      showView(loginView);
      return false;
    }

    if (!navigator.onLine) {
      showView(clockView);
      if (userLine) userLine.textContent = "Signed in (offline — reconnect to refresh status)";
      if (statusEl) {
        statusEl.textContent = "Offline. Connect to load your latest punch status.";
        statusEl.className = "punch-clock-status is-out";
      }
      setOnlineState(false);
      maybeShowInstallBanner();
      return true;
    }

    try {
      const response = await apiFetch("/auth/verify", { method: "GET", headers: authHeaders(false) });
      if (response.status === 401) {
        clearSession();
        setInlineStatus(loginStatus, "Session expired. Sign in again.");
        showView(loginView);
        return false;
      }
      if (!response.ok) {
        throw new Error("Could not verify session");
      }
      const user = await response.json();
      if (user.role !== "employee") {
        clearSession();
        setInlineStatus(loginStatus, "This app is for employee accounts only.");
        showView(loginView);
        return false;
      }
      if (userLine) {
        userLine.textContent = `Signed in as ${user.username}`;
      }
      showView(clockView);
      setOnlineState(true);
      maybeShowInstallBanner();
      await loadStatus();
      return true;
    } catch {
      showView(clockView);
      setOnlineState(navigator.onLine);
      if (statusEl) {
        statusEl.textContent = navigator.onLine
          ? "Could not verify your session. Try signing in again."
          : "Offline. Connect to refresh your punch status.";
        statusEl.className = "punch-clock-status is-out";
      }
      maybeShowInstallBanner();
      return true;
    }
  }

  function renderRotaContext(data) {
    const expected = data.expected_shift_today;
    if (expectedShiftEl) {
      if (expected) {
        expectedShiftEl.hidden = false;
        const status = expected.attendance_status;
        const statusNote =
          status === "late"
            ? "You clocked in late for today’s shift."
            : status === "no_show"
              ? "You missed today’s scheduled shift — contact your manager."
              : status === "awaiting"
                ? "You’re on the rota today — remember to clock in."
                : status === "attended"
                  ? "Today’s shift is recorded."
                  : `Today: ${expected.start_time}–${expected.end_time}${expected.role_label ? ` (${expected.role_label})` : ""}.`;
        expectedShiftEl.innerHTML = `<strong>Today’s shift</strong> ${expected.start_time}–${expected.end_time}${expected.role_label ? ` · ${expected.role_label}` : ""}<br /><span class="punch-expected-shift__note">${statusNote}</span>`;
        expectedShiftEl.className = `punch-expected-shift punch-expected-shift--${status || "scheduled"}`;
      } else {
        expectedShiftEl.hidden = true;
      }
    }
    if (weekShiftsEl) {
      const items = data.week_shifts || [];
      weekShiftsEl.innerHTML = items.length
        ? items
            .map((s) => {
              const day = new Date(`${s.shift_date}T12:00:00`).toLocaleDateString("en-GB", {
                weekday: "short",
                day: "numeric",
              });
              return `<li><strong>${day}</strong> ${s.start_time}–${s.end_time}${s.role_label ? ` · ${s.role_label}` : ""}</li>`;
            })
            .join("")
        : "<li class=\"muted\">No published shifts this week yet.</li>";
    }
  }

  async function loadStatus() {
    if (!statusEl || !token()) return;
    if (!navigator.onLine) {
      setOnlineState(false);
      return;
    }

    try {
      const response = await apiFetch("/time-punch/status", { method: "GET", headers: authHeaders(false) });
      if (response.status === 401) {
        clearSession();
        setInlineStatus(loginStatus, "Session expired. Sign in again.");
        showView(loginView);
        return;
      }
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        statusEl.textContent = parseApiError(err, "Could not load punch status.");
        statusEl.className = "punch-clock-status is-out";
        return;
      }
      const data = await response.json();
      const last = data.last_punch;
      clockedInState = Boolean(data.clocked_in);
      if (data.clocked_in) {
        statusEl.innerHTML = `<strong>Clocked in</strong> since ${formatTime(last?.punched_at)}${last?.site_name ? ` at ${last.site_name}` : ""}.`;
        statusEl.className = "punch-clock-status is-in";
      } else if (last) {
        statusEl.textContent = `Last punch: ${last.punch_type === "in" ? "in" : "out"} at ${formatTime(last.punched_at)}.`;
        statusEl.className = "punch-clock-status is-out";
      } else {
        statusEl.textContent = "Not clocked in yet today.";
        statusEl.className = "punch-clock-status is-out";
      }
      if (sitesEl) {
        const sites = data.assigned_sites || [];
        sitesEl.innerHTML = sites.length
          ? sites.map((s) => `<li>${s.name}: ${s.address} (${s.radius_meters}m radius)</li>`).join("")
          : "<li>No punch sites configured. Ask HR.</li>";
      }
      renderRotaContext(data);
      setOnlineState(true);
      syncClockButtons();
    } catch {
      statusEl.textContent = "Could not reach the time punch service.";
      statusEl.className = "punch-clock-status is-out";
      setOnlineState(navigator.onLine);
    }
  }

  function friendlyGeoError(error) {
    const code = error?.code;
    if (code === 1) {
      return "Location permission denied. Allow location for this app in your browser or phone settings.";
    }
    if (code === 2) {
      return "Location unavailable. Try moving outdoors or turning off airplane mode.";
    }
    if (code === 3) {
      return "Location timed out. Check GPS signal and try again.";
    }
    return error?.message || "Could not read your location.";
  }

  function readLocationOnce(options) {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Location is not supported on this device."));
        return;
      }
      navigator.geolocation.getCurrentPosition(resolve, reject, options);
    });
  }

  async function readLocation() {
    const primary = { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 };
    try {
      const pos = await readLocationOnce(primary);
      return {
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
        accuracy_meters: pos.coords.accuracy,
      };
    } catch (firstError) {
      if (firstError?.code !== 3) {
        throw new Error(friendlyGeoError(firstError));
      }
      const pos = await readLocationOnce({ enableHighAccuracy: false, timeout: 25000, maximumAge: 15000 });
      return {
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
        accuracy_meters: pos.coords.accuracy,
      };
    }
  }

  async function submitPunch(punchType) {
    if (punchInFlight) return;
    if (!navigator.onLine) {
      setMessage("You are offline. Connect to the internet to clock in or out.", "error");
      return;
    }

    punchInFlight = true;
    syncClockButtons();
    setMessage("Reading your location…", "info");

    try {
      const location = await readLocation();
      setMessage("Submitting punch…", "info");
      const response = await apiFetch("/time-punch/punch", {
        method: "POST",
        body: JSON.stringify({ punch_type: punchType, ...location }),
      });
      const data = await response.json().catch(() => ({}));
      if (response.status === 401) {
        clearSession();
        setInlineStatus(loginStatus, "Session expired. Sign in again.");
        showView(loginView);
        return;
      }
      if (!response.ok) {
        setMessage(parseApiError(data, "Punch failed."), "error");
        return;
      }
      setMessage(
        `${punchType === "in" ? "Clocked in" : "Clocked out"} at ${data.site_name} (${Math.round(data.distance_meters)}m from site).`,
        "success"
      );
      await loadStatus();
    } catch (error) {
      setMessage(error.message || "Punch failed.", "error");
    } finally {
      punchInFlight = false;
      syncClockButtons();
    }
  }

  function isStandalone() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true
    );
  }

  function isIos() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent);
  }

  function installDismissed() {
    return localStorage.getItem("punchPwaInstallDismissed") === "1";
  }

  function maybeShowInstallBanner() {
    if (!installBanner || isStandalone() || installDismissed()) return;

    if (deferredInstallPrompt) {
      installBanner.hidden = false;
      if (installCopy) {
        installCopy.textContent = "Install ShiftSwift Time Clock on your home screen for quick access.";
      }
      if (installBtn) installBtn.hidden = false;
      return;
    }

    if (isIos()) {
      installBanner.hidden = false;
      if (installCopy) {
        installCopy.textContent = "On iPhone: tap Share, then Add to Home Screen to install the Time Clock app.";
      }
      if (installBtn) installBtn.hidden = true;
    }
  }

  function showUpdateBanner(worker) {
    waitingServiceWorker = worker;
    if (updateBanner) updateBanner.hidden = false;
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;

    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (sessionStorage.getItem("punchSwReloaded") === "1") return;
      sessionStorage.setItem("punchSwReloaded", "1");
      window.location.reload();
    });

    window.addEventListener("load", () => {
      navigator.serviceWorker
        .register("./app-sw.js?v=1", { scope: "./" })
        .then((registration) => {
          if (registration.waiting) {
            showUpdateBanner(registration.waiting);
          }
          registration.addEventListener("updatefound", () => {
            const worker = registration.installing;
            if (!worker) return;
            worker.addEventListener("statechange", () => {
              if (worker.state === "installed" && navigator.serviceWorker.controller) {
                showUpdateBanner(worker);
              }
            });
          });
        })
        .catch(() => null);
    });
  }

  updateBtn?.addEventListener("click", () => {
    const worker = waitingServiceWorker;
    if (!worker) return;
    worker.postMessage({ type: "SKIP_WAITING" });
    if (updateBanner) updateBanner.hidden = true;
  });

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    if (clockView && !clockView.hidden) {
      maybeShowInstallBanner();
    }
  });

  installBtn?.addEventListener("click", async () => {
    if (!deferredInstallPrompt) return;
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice.catch(() => null);
    deferredInstallPrompt = null;
    if (installBanner) installBanner.hidden = true;
  });

  installDismiss?.addEventListener("click", () => {
    localStorage.setItem("punchPwaInstallDismissed", "1");
    if (installBanner) installBanner.hidden = true;
  });

  loginForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    setInlineStatus(loginStatus, "Signing in…");
    const payload = Object.fromEntries(new FormData(loginForm).entries());
    try {
      const data = await postJson("/auth/employee-login", payload);
      if (data.mfa_required && data.challenge_token) {
        pendingChallenge = data.challenge_token;
        setInlineStatus(loginStatus, "");
        const mfaUser = mfaView?.querySelector("[data-mfa-user]");
        if (mfaUser) mfaUser.textContent = data.username || payload.username;
        showView(mfaView);
        mfaView?.querySelector('input[name="code"]')?.focus();
        return;
      }
      if (data.role && data.role !== "employee") {
        clearSession();
        setInlineStatus(loginStatus, "This app is for employee accounts only.");
        return;
      }
      storeSession(data);
      setInlineStatus(loginStatus, "");
      await verifyEmployeeSession();
    } catch (error) {
      setInlineStatus(loginStatus, friendlyLoginError(error.message));
    }
  });

  mfaForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!pendingChallenge) {
      setInlineStatus(mfaStatus, "Session expired. Sign in again.");
      showView(loginView);
      return;
    }
    setInlineStatus(mfaStatus, "Verifying code…");
    const code = new FormData(mfaForm).get("code");
    try {
      const data = await postJson("/auth/mfa/verify", {
        challenge_token: pendingChallenge,
        code,
      });
      if (data.role && data.role !== "employee") {
        clearSession();
        setInlineStatus(mfaStatus, "This app is for employee accounts only.");
        showView(loginView);
        return;
      }
      storeSession(data);
      pendingChallenge = null;
      setInlineStatus(mfaStatus, "");
      await verifyEmployeeSession();
    } catch (error) {
      setInlineStatus(mfaStatus, error.message);
    }
  });

  signOutBtn?.addEventListener("click", () => {
    clearSession();
    setMessage("", "");
    clockedInState = false;
    showView(loginView);
    if (installBanner) installBanner.hidden = true;
    syncClockButtons();
  });

  clockInBtn?.addEventListener("click", () => submitPunch("in"));
  clockOutBtn?.addEventListener("click", () => submitPunch("out"));

  window.addEventListener("online", () => {
    setOnlineState(true);
    if (token() && clockView && !clockView.hidden) {
      loadStatus();
    }
  });
  window.addEventListener("offline", () => setOnlineState(false));

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && token() && clockView && !clockView.hidden && navigator.onLine) {
      loadStatus();
    }
  });

  setInterval(() => {
    if (document.hidden || !token() || !clockView || clockView.hidden || !navigator.onLine) return;
    loadStatus();
  }, 60000);

  registerServiceWorker();
  setOnlineState(navigator.onLine);
  verifyEmployeeSession();
})();
