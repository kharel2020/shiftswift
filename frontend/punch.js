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

  let pendingChallenge = null;
  let deferredInstallPrompt = null;

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

  function authHeaders() {
    return {
      Authorization: `Bearer ${token()}`,
      "X-Tenant-Id": tenantId() || "",
      "Content-Type": "application/json",
    };
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

  async function postJson(path, body) {
    let response;
    try {
      response = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch {
      throw new Error("Cannot reach the API. Check your connection and try again.");
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail;
      const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail[0]?.msg : null;
      throw new Error(message || data.message || "Request failed");
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

    try {
      const response = await fetch(`${API_BASE}/auth/verify`, {
        headers: { Authorization: `Bearer ${currentToken}` },
      });
      if (response.status === 401) {
        clearSession();
        showView(loginView);
        return false;
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
      maybeShowInstallBanner();
      await loadStatus();
      return true;
    } catch {
      showView(clockView);
      if (statusEl) statusEl.textContent = "Could not verify your session. Try signing in again.";
      maybeShowInstallBanner();
      return true;
    }
  }

  async function loadStatus() {
    if (!statusEl) return;
    try {
      const response = await fetch(`${API_BASE}/time-punch/status`, { headers: authHeaders() });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        statusEl.textContent = err.detail || "Could not load punch status.";
        statusEl.className = "punch-clock-status is-out";
        return;
      }
      const data = await response.json();
      const last = data.last_punch;
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
      if (clockInBtn) clockInBtn.disabled = Boolean(data.clocked_in);
      if (clockOutBtn) clockOutBtn.disabled = !data.clocked_in;
    } catch {
      statusEl.textContent = "Could not reach the time punch service.";
      statusEl.className = "punch-clock-status is-out";
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
    showView(loginView);
    if (installBanner) installBanner.hidden = true;
  });

  clockInBtn?.addEventListener("click", () => submitPunch("in"));
  clockOutBtn?.addEventListener("click", () => submitPunch("out"));

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("./punch-sw.js", { scope: "./" }).catch(() => null);
    });
  }

  verifyEmployeeSession();
})();
