const API_BASE = localStorage.getItem("apiBaseUrl") || "http://localhost:3000";
const params = new URLSearchParams(window.location.search);
const token = params.get("token");
const contractType = params.get("type") || "platform";

const viewPath =
  contractType === "employment"
    ? `/employment-contracts/sign/view/${encodeURIComponent(token)}`
    : `/contracts/sign/view/${encodeURIComponent(token)}`;
const signPath =
  contractType === "employment"
    ? `/employment-contracts/sign/${encodeURIComponent(token)}`
    : `/contracts/sign/${encodeURIComponent(token)}`;

async function loadContract() {
  if (!token) {
    document.getElementById("contract-meta").textContent = "Missing signing link.";
    return;
  }
  const res = await fetch(`${API_BASE}${viewPath}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Contract unavailable");

  const isEmployment = contractType === "employment" || data.contract_type === "employment";
  const label = isEmployment ? data.title || "Employment contract" : data.template_id?.toUpperCase();
  const party = isEmployment ? data.signatory_name : data.customer_legal_name;
  document.getElementById("contract-meta").textContent =
    `${label} · ${data.contract_number}${party ? ` · ${party}` : ""}`;

  document.getElementById("contract-preview").innerHTML = data.html || "";

  const acceptLabel = document.querySelector('label.checkbox-row span');
  if (acceptLabel) {
    acceptLabel.textContent = isEmployment
      ? "I have read this employment contract and sign as the employee named above."
      : "I have read this agreement and sign on behalf of my organisation.";
  }

  if (data.signatory_name) {
    document.querySelector('[name="signature_name"]').value = data.signatory_name;
  }
}

document.getElementById("sign-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = document.getElementById("sign-status");
  const form = event.currentTarget;
  status.textContent = "Submitting signature…";
  try {
    const res = await fetch(`${API_BASE}${signPath}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        signature_name: form.signature_name.value.trim(),
        signature_title: form.signature_title.value.trim() || null,
        accept_terms: form.accept_terms.checked,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Signing failed");
    status.textContent = `Signed successfully. Reference ${data.contract_number}. You may close this page.`;
    form.querySelector("button").disabled = true;
  } catch (error) {
    status.textContent = error.message;
  }
});

loadContract().catch((error) => {
  document.getElementById("contract-meta").textContent = error.message;
});
