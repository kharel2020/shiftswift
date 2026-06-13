(function () {
  const API_BASE =
    localStorage.getItem("apiBaseUrl") ||
    (window.ShiftSwiftBrand?.resolveApiBase ? window.ShiftSwiftBrand.resolveApiBase() : "http://localhost:3000");
  const token = localStorage.getItem("token");

  if (!token) {
    window.location.replace("./business-login.html");
    return;
  }

  function setModalStatus(message) {
    const status = document.getElementById("employee-gdpr-status");
    if (!status) return;
    if (message) {
      status.textContent = message;
      status.hidden = false;
    } else {
      status.textContent = "";
      status.hidden = true;
    }
  }

  function showGdprModal(employerName) {
    const modal = document.getElementById("employee-gdpr-modal");
    const employerEl = document.getElementById("employee-gdpr-employer");
    if (employerEl && employerName) {
      employerEl.textContent = employerName;
    }
    if (modal) modal.hidden = false;
    document.body.classList.add("employee-gdpr-locked");
  }

  function hideGdprModal() {
    const modal = document.getElementById("employee-gdpr-modal");
    if (modal) modal.hidden = true;
    document.body.classList.remove("employee-gdpr-locked");
  }

  async function submitGdprConsent() {
    const checkbox = document.getElementById("employee-gdpr-checkbox");
    if (!checkbox?.checked) {
      setModalStatus(
        "Please confirm you understand your employer manages your data and agree to the privacy policy.",
      );
      return;
    }
    setModalStatus("");
    const button = document.getElementById("employee-gdpr-submit");
    if (button) button.disabled = true;
    try {
      const response = await fetch(`${API_BASE}/auth/employee/gdpr-consent`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ accept_employee_gdpr: true }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Could not save your consent.");
      }
      hideGdprModal();
    } catch (error) {
      setModalStatus(error.message || "Could not save your consent.");
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function loadProfile() {
    const welcome = document.getElementById("employee-welcome");
    try {
      const response = await fetch(`${API_BASE}/auth/verify`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.status === 401) {
        localStorage.clear();
        window.location.replace("./business-login.html");
        return;
      }
      const user = await response.json();
      if (user.role !== "employee") {
        window.location.replace("./admin.html");
        return;
      }
      if (welcome) {
        welcome.textContent = `Signed in as ${user.username} · business ${user.tenant_id}`;
      }
      if (user.gdpr_consent_required) {
        showGdprModal(user.employer_name);
      }
    } catch {
      if (welcome) welcome.textContent = "Could not load your account.";
    }
  }

  function signOut(event) {
    event.preventDefault();
    localStorage.removeItem("token");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("tenantId");
    localStorage.removeItem("userRole");
    window.location.href = "./business-login.html";
  }

  document.querySelectorAll("[data-sign-out]").forEach((el) => {
    el.addEventListener("click", signOut);
  });

  document.getElementById("employee-gdpr-submit")?.addEventListener("click", submitGdprConsent);

  if (window.MobileShell) {
    const sidebar = window.MobileShell.initSidebar();
    window.MobileShell.initHashSections({
      defaultSection: "overview",
      sectionEvent: "employee:section",
      sidebar,
    });
  }

  loadProfile();
})();
