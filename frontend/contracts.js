const { apiFetch, loadFormOptions, mountEditForm, renderTableBody, FORM_SCHEMAS, escapeHtml, statusPill, parseHashBaseSection } = window.Admin;

async function loadContracts() {
  const body = document.getElementById("contracts-table-body");
  if (!body) return;
  try {
    const res = await apiFetch("/contracts");
    const data = await res.json();
    const items = data.items || [];
    renderTableBody(body, {
      emptyMessage: "No contracts yet. Generate a pack below.",
      columns: [
        {
          key: "contract_number",
          render: (c) =>
            `<strong>${escapeHtml(c.contract_number)}</strong><div class="muted">${escapeHtml(c.template_name)}</div>`,
        },
        { key: "customer_legal_name", render: (c) => escapeHtml(c.customer_legal_name) },
        { key: "status", render: (c) => statusPill(c.status) },
        { key: "signatory_email", render: (c) => escapeHtml(c.signatory_email) },
        {
          key: "signed_at",
          render: (c) =>
            c.signed_at ? escapeHtml(new Date(c.signed_at).toLocaleDateString()) : c.sent_at ? "Sent" : "Not set",
        },
        {
          key: "actions",
          render: (c) =>
            `<div class="table-actions contract-actions">
              <button type="button" class="btn ghost" data-view="${c.id}">View</button>
              <button type="button" class="btn ghost" data-send="${c.id}" ${c.status === "signed" ? "disabled" : ""}>Send</button>
            </div>`,
        },
      ],
      rows: items,
    });

    body.querySelectorAll("[data-view]").forEach((btn) => {
      btn.addEventListener("click", () => viewContract(btn.getAttribute("data-view")));
    });
    body.querySelectorAll("[data-send]").forEach((btn) => {
      btn.addEventListener("click", () => sendContract(btn.getAttribute("data-send")));
    });
  } catch {
    renderTableBody(body, {
      columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }, { key: "f" }],
      rows: [],
      emptyMessage: "Could not load contracts.",
    });
  }
}

async function viewContract(id) {
  const preview = document.getElementById("contract-preview-panel");
  const res = await apiFetch(`/contracts/${id}`);
  const data = await res.json();
  if (!res.ok) return;
  if (preview) {
    preview.hidden = false;
    preview.innerHTML = `<h3>${escapeHtml(data.contract_number)}</h3>${data.html || ""}`;
  }
}

async function sendContract(id) {
  const status = document.querySelector("#contract-generate-form [data-status]");
  if (status) status.textContent = "Sending for signature…";
  const res = await apiFetch(`/contracts/${id}/send`, { method: "POST" });
  const data = await res.json();
  if (!res.ok) {
    if (status) status.textContent = data.detail || "Send failed";
    return;
  }
  if (status) {
    status.textContent = `Sent to ${data.signatory_email}. Signing link copied below.`;
  }
  const linkBox = document.getElementById("signing-link-box");
  if (linkBox && data.signing_url) {
    linkBox.hidden = false;
    linkBox.innerHTML = `<label class="edit-field"><span class="edit-label">Client signing link</span><input readonly value="${escapeHtml(data.signing_url)}" onclick="this.select()" /></label>`;
  }
  loadContracts();
}

async function mountContractForm() {
  const host = document.getElementById("contract-generate-form");
  if (!host) return;

  let profileValues = {};
  try {
    await loadFormOptions();
    const profileRes = await apiFetch("/admin/tenant-profile");
    if (profileRes.ok) {
      const profile = await profileRes.json();
      profileValues = {
        customer_legal_name: profile.name || "",
        customer_trading_name: profile.trading_name || "",
        company_number: profile.company_number || "",
        vat_number: profile.vat_number || "",
        registered_address: profile.registered_address || "",
        signatory_email: profile.signatory_email || profile.billing_email || "",
        signatory_name: profile.signatory_name || "",
        signatory_title: profile.signatory_title || "Director",
        plan_id: profile.subscription_plan || "",
      };
    }
  } catch {
    /* prefill optional */
  }

  mountEditForm(host, FORM_SCHEMAS.contract, {
    values: profileValues,
    onSubmit: async (payload) => {
      const res = await apiFetch("/contracts/generate", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Generation failed");
      loadContracts();
    },
  });
}

let contractsReady = false;

window.addEventListener("admin:section", (event) => {
  if (event.detail?.section === "contracts" && !contractsReady) {
    contractsReady = true;
    loadContracts();
    mountContractForm();
  }
});

if (parseHashBaseSection(window.location.hash) === "contracts") {
  contractsReady = true;
  loadContracts();
  mountContractForm();
}
