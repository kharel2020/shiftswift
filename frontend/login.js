function getApiBase() {
  if (window.ShiftSwiftBrand?.getApiBase) {
    return window.ShiftSwiftBrand.getApiBase();
  }
  if (window.ShiftSwiftBrand?.resolveApiBase) {
    return window.ShiftSwiftBrand.resolveApiBase();
  }
  return localStorage.getItem("apiBaseUrl") || "http://localhost:3000";
}

const LOGIN_MODES = {
  business: {
    endpoint: "/auth/business-login",
    redirect: "./admin.html",
    lead: "Welcome back. Enter your HR admin username and password.",
    submit: "Open HR dashboard",
    usernamePlaceholder: "hr@shiftswifthr.co.uk",
  },
  employee: {
    endpoint: "/auth/employee-login",
    redirect: "./employee.html",
    lead: "Sign in with your username and password. Your business is linked automatically.",
    submit: "Open employee portal",
    usernamePlaceholder: "employee@shiftswifthr.co.uk",
  },
};

let pendingChallenge = null;
let pendingRedirect = "./admin.html";
let activeLoginMode = "business";

function secureHostLabel() {
  const fromBrand = window.ShiftSwiftBrand?.domain;
  if (fromBrand) return fromBrand;
  if (typeof window !== "undefined" && window.location.hostname) {
    return String(window.location.hostname).replace(/^www\./i, "");
  }
  return "shiftswifthr.co.uk";
}

function setStatus(message) {
  const status = document.getElementById("login-status");
  if (!status) return;
  if (message) {
    status.textContent = message;
    status.hidden = false;
  } else {
    status.textContent = "";
    status.hidden = true;
  }
}

function friendlyLoginError(message, endpoint, username) {
  if (message === "Failed to fetch" || message === "Load failed") {
    return "Cannot reach the API. Start it with: bash scripts/start_local.sh";
  }
  if (message === "Invalid credentials for this login type") {
    if (endpoint.includes("master")) {
      return "Use your platform master account here (admin@shiftswifthr.co.uk). Business HR and employees sign in via Business sign in.";
    }
    if (endpoint.includes("employee")) {
      return "Use your employee account here. HR admins should choose the Business HR tab.";
    }
    return "Use Business sign in for HR/employee accounts. Platform master admin has a separate sign-in page.";
  }
  if (message === "Invalid username or password" || message === "Login failed") {
    return message;
  }
  return message || "Login failed";
}

async function postJson(path, body) {
  let response;
  try {
    response = await fetch(`${getApiBase()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Failed to fetch");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail[0]?.msg : null;
    throw new Error(message || data.message || "Login failed");
  }
  return data;
}

function storeSession(data) {
  if (data.access_token) localStorage.setItem("token", data.access_token);
  if (data.refresh_token) localStorage.setItem("refreshToken", data.refresh_token);
  if (data.role) localStorage.setItem("userRole", data.role);
  if (data.tenant_id) {
    localStorage.setItem("masterTenantId", data.tenant_id);
    if (data.role === "admin" && data.tenant_id === "999") {
      localStorage.setItem("tenantId", "1");
    } else {
      localStorage.setItem("tenantId", data.tenant_id);
    }
  }
}

function redirectForRole(data, fallback) {
  if (data.role === "employee") return "./employee.html";
  return fallback;
}

function showMfaStep(username) {
  const loginTabs = document.getElementById("login-tabs");
  const loginShell = document.getElementById("login-shell");
  const loginFeatures = document.getElementById("login-features");
  const mfaPanel = document.getElementById("mfa-panel");

  if (loginTabs) loginTabs.hidden = true;
  if (loginShell) loginShell.hidden = true;
  if (loginFeatures) loginFeatures.hidden = true;
  if (mfaPanel) {
    mfaPanel.hidden = false;
    const userLabel = mfaPanel.querySelector("[data-mfa-user]");
    if (userLabel) userLabel.textContent = username;
    const codeInput = mfaPanel.querySelector('input[name="code"]');
    if (codeInput) codeInput.focus();
  }
}

function bindMfaForm() {
  const mfaForm = document.getElementById("mfa-form");
  if (!mfaForm || mfaForm.dataset.bound) return;
  mfaForm.dataset.bound = "1";

  mfaForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!pendingChallenge) {
      setStatus("Session expired. Sign in again.");
      return;
    }
    setStatus("Verifying code…");
    const code = new FormData(mfaForm).get("code");
    try {
      const data = await postJson("/auth/mfa/verify", {
        challenge_token: pendingChallenge,
        code,
      });
      storeSession(data);
      window.location.href = redirectForRole(data, pendingRedirect);
    } catch (error) {
      setStatus(error.message);
    }
  });
}

function loginPayload(form) {
  const raw = Object.fromEntries(new FormData(form).entries());
  return {
    username: raw.username,
    password: raw.password,
  };
}

function bindPortalLogin() {
  const form = document.getElementById("portal-login-form");
  if (!form) return;

  bindMfaForm();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const mode = LOGIN_MODES[activeLoginMode] || LOGIN_MODES.business;
    pendingRedirect = mode.redirect;
    setStatus("Signing in…");
    const payload = loginPayload(form);
    try {
      const data = await postJson(mode.endpoint, payload);
      if (data.mfa_required && data.challenge_token) {
        pendingChallenge = data.challenge_token;
        pendingRedirect = redirectForRole(data, mode.redirect);
        setStatus("");
        showMfaStep(data.username || payload.username);
        return;
      }
      storeSession(data);
      window.location.href = redirectForRole(data, mode.redirect);
    } catch (error) {
      setStatus(friendlyLoginError(error.message, mode.endpoint, payload.username));
    }
  });
}

function switchLoginMode(nextMode) {
  if (!LOGIN_MODES[nextMode]) return;
  activeLoginMode = nextMode;
  const mode = LOGIN_MODES[nextMode];

  const lead = document.getElementById("login-lead");
  const submit = document.getElementById("login-submit");
  const usernameInput = document.querySelector('#portal-login-form input[name="username"]');

  if (lead) lead.textContent = mode.lead;
  if (submit) submit.textContent = mode.submit;
  if (usernameInput) usernameInput.placeholder = mode.usernamePlaceholder;
  setStatus("");
}

function initBusinessLoginTabs() {
  const tabs = document.querySelectorAll("[data-login-tab]");
  if (!tabs.length) return;

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const key = tab.dataset.loginTab;
      tabs.forEach((item) => {
        const active = item === tab;
        item.classList.toggle("is-active", active);
        item.setAttribute("aria-selected", active ? "true" : "false");
      });
      switchLoginMode(key);
    });
  });

  switchLoginMode("business");
  bindPortalLogin();
}

function bindSimpleLogin(formId, endpoint, redirectUrl) {
  const form = document.getElementById(formId);
  if (!form) return;

  bindMfaForm();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    pendingRedirect = redirectUrl;
    setStatus("Signing in…");
    const payload = loginPayload(form);
    try {
      const data = await postJson(endpoint, payload);
      if (data.mfa_required && data.challenge_token) {
        pendingChallenge = data.challenge_token;
        pendingRedirect = redirectUrl;
        setStatus("");
        showMfaStep(data.username || payload.username);
        return;
      }
      storeSession(data);
      window.location.href = redirectUrl;
    } catch (error) {
      setStatus(friendlyLoginError(error.message, endpoint, payload.username));
    }
  });
}

function showLocalDevHints() {
  const host = window.location.hostname;
  if (host !== "localhost" && host !== "127.0.0.1") return;

  const staleApi = localStorage.getItem("apiBaseUrl");
  if (staleApi && !/localhost|127\.0\.0\.1/.test(staleApi)) {
    localStorage.removeItem("apiBaseUrl");
  }

  const hint = document.createElement("p");
  hint.className = "portal-login-dev-hint";
  hint.innerHTML =
    "Local dev: master → <code>admin@shiftswifthr.co.uk</code> · HR → <code>hr@shiftswifthr.co.uk</code> · passwords in README.";
  document.querySelector(".portal-login-card")?.appendChild(hint);
}

document.querySelectorAll("[data-secure-host]").forEach((el) => {
  el.textContent = secureHostLabel();
});

showLocalDevHints();
initBusinessLoginTabs();
bindSimpleLogin("master-login-form", "/auth/master-login", "./admin.html");
