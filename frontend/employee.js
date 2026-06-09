(function () {
  const API_BASE =
    localStorage.getItem("apiBaseUrl") ||
    (window.ShiftSwiftBrand?.resolveApiBase ? window.ShiftSwiftBrand.resolveApiBase() : "http://localhost:3000");
  const token = localStorage.getItem("token");

  if (!token) {
    window.location.replace("./business-login.html");
    return;
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

  loadProfile();
})();
