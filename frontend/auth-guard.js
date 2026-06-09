(function () {
  const token = localStorage.getItem("token");
  if (!token) {
    window.location.replace("./business-login.html");
  }
})();

function signOut() {
  localStorage.removeItem("token");
  localStorage.removeItem("tenantId");
  window.location.href = "./business-login.html";
}

document.querySelectorAll("[data-sign-out]").forEach((el) => {
  el.addEventListener("click", (event) => {
    event.preventDefault();
    signOut();
  });
});
