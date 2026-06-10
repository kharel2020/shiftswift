(function () {
  function apiBase() {
    if (window.ShiftSwiftBrand?.resolveApiBase) {
      return window.ShiftSwiftBrand.resolveApiBase();
    }
    return localStorage.getItem("apiBaseUrl") || "http://localhost:3000";
  }

  function setStatus(el, message, isSuccess) {
    if (!el) return;
    if (message) {
      el.textContent = message;
      el.hidden = false;
      el.classList.toggle("form-success-message", Boolean(isSuccess));
    } else {
      el.textContent = "";
      el.hidden = true;
      el.classList.remove("form-success-message");
    }
  }

  function friendlyError(message) {
    if (message === "Failed to fetch" || message === "Load failed") {
      return "Cannot reach the server. Check your connection and try again.";
    }
    return message || "Request failed";
  }

  async function postJson(path, body) {
    const response = await fetch(`${apiBase()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail;
      const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail[0]?.msg : null;
      throw new Error(message || "Request failed");
    }
    return data;
  }

  let resetRole = "hr";

  function initForgotPage() {
    const form = document.getElementById("forgot-password-form");
    if (!form) return;

    const params = new URLSearchParams(window.location.search);
    if (params.get("role") === "employee") {
      resetRole = "employee";
      document.querySelectorAll("[data-reset-tab]").forEach((tab) => {
        const active = tab.dataset.resetTab === "employee";
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
      });
    }

    document.querySelectorAll("[data-reset-tab]").forEach((tab) => {
      tab.addEventListener("click", () => {
        resetRole = tab.dataset.resetTab || "hr";
        document.querySelectorAll("[data-reset-tab]").forEach((item) => {
          const active = item === tab;
          item.classList.toggle("is-active", active);
          item.setAttribute("aria-selected", active ? "true" : "false");
        });
      });
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const status = document.getElementById("forgot-status");
      const email = new FormData(form).get("email");
      setStatus(status, "Sending reset link…", false);
      try {
        const data = await postJson("/auth/forgot-password", { email, role: resetRole });
        setStatus(status, data.message || "Check your email for a reset link.", true);
        form.querySelector('button[type="submit"]')?.setAttribute("disabled", "disabled");
      } catch (error) {
        setStatus(status, friendlyError(error.message), false);
      }
    });
  }

  function initResetPage() {
    const form = document.getElementById("reset-password-form");
    if (!form) return;

    const token = new URLSearchParams(window.location.search).get("token");
    const status = document.getElementById("reset-status");
    if (!token) {
      setStatus(status, "Missing reset token. Request a new link from the forgot password page.", false);
      return;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      if (data.new_password.length < 8) {
        setStatus(status, "Password must be at least 8 characters.", false);
        return;
      }
      if (data.new_password !== data.confirm_password) {
        setStatus(status, "Passwords do not match.", false);
        return;
      }
      setStatus(status, "Updating password…", false);
      try {
        const result = await postJson("/auth/reset-password", {
          token,
          new_password: data.new_password,
        });
        setStatus(status, result.message || "Password updated.", true);
        setTimeout(() => {
          window.location.href = "./business-login.html";
        }, 1500);
      } catch (error) {
        setStatus(status, friendlyError(error.message), false);
      }
    });
  }

  initForgotPage();
  initResetPage();
})();
