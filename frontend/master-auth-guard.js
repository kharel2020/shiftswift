(function () {
  const token = localStorage.getItem("token");
  const role = localStorage.getItem("userRole");
  const masterId = localStorage.getItem("masterTenantId") || "999";

  if (!token || role !== "admin") {
    window.location.replace("./ops-9x7k2.html");
    return;
  }

  if (localStorage.getItem("tenantId") !== masterId && localStorage.getItem("masterTenantId") !== masterId) {
    window.location.replace("./ops-9x7k2.html");
  }
})();

function masterSignOut() {
  localStorage.removeItem("token");
  localStorage.removeItem("refreshToken");
  localStorage.removeItem("tenantId");
  localStorage.removeItem("masterTenantId");
  localStorage.removeItem("userRole");
  window.location.href = "./ops-9x7k2.html";
}

document.querySelectorAll("[data-master-sign-out]").forEach((el) => {
  el.addEventListener("click", (event) => {
    event.preventDefault();
    masterSignOut();
  });
});
