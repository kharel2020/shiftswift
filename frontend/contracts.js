/** Legal contracts workspace — generate, send, preview, upload signed PDFs. */
(function () {
  const { apiFetch, loadFormOptions, mountEditForm, FORM_SCHEMAS, escapeHtml, parseHashBaseSection } = window.Admin;

  let contracts = [];
  let selectedContractId = null;
  let formMounted = false;
  let sectionBound = false;

  function $(id) {
    return document.getElementById(id);
  }

  const STATUS_LABELS = {
    draft: "Draft",
    generated: "Draft",
    sent: "Sent",
    signed: "Signed",
    declined: "Declined",
    expired: "Expired",
  };

  function statusBadge(status) {
    const label = STATUS_LABELS[status] || status || "Draft";
    const cls =
      status === "signed"
        ? "contracts-status-pill--signed"
        : status === "sent"
          ? "contracts-status-pill--sent"
          : status === "declined" || status === "expired"
            ? "contracts-status-pill--danger"
            : "contracts-status-pill--draft";
    return `<span class="contracts-status-pill ${cls}">${escapeHtml(label)}</span>`;
  }

  function formatDate(value) {
    if (!value) return "Not set";
    try {
      return new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
    } catch {
      return value;
    }
  }

  function renderContractsTable() {
    const tbody = $("contracts-table-body");
    if (!tbody) return;
    if (!contracts.length) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="muted">No contracts yet. Generate a pack above — details are prefilled from Settings → Business info.</td></tr>';
      return;
    }
    tbody.innerHTML = contracts
      .map((row) => {
        const selected = selectedContractId === row.id ? " contracts-case-row--selected" : "";
        return `<tr class="contracts-case-row${selected}" data-contract-id="${row.id}">
          <td><strong>${escapeHtml(row.contract_number)}</strong><div class="muted">${formatDate(row.created_at)}</div></td>
          <td>${escapeHtml(row.template_name || row.template_id)}</td>
          <td>${escapeHtml(row.customer_legal_name)}</td>
          <td>${statusBadge(row.status)}</td>
          <td>${escapeHtml(row.signatory_email)}</td>
          <td>${row.signed_at ? escapeHtml(formatDate(row.signed_at)) : row.sent_at ? '<span class="muted">Awaiting signature</span>' : '<span class="muted">Not sent</span>'}</td>
        </tr>`;
      })
      .join("");

    tbody.querySelectorAll(".contracts-case-row").forEach((row) => {
      row.addEventListener("click", () => selectContract(Number(row.dataset.contractId)));
    });
  }

  async function loadContracts() {
    const tbody = $("contracts-table-body");
    if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="muted">Loading contracts…</td></tr>';
    try {
      const res = await apiFetch("/contracts");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      contracts = data.items || [];
      renderContractsTable();
      if (selectedContractId && contracts.some((c) => c.id === selectedContractId)) {
        await selectContract(selectedContractId, { scroll: false });
      }
    } catch {
      contracts = [];
      if (tbody) {
        tbody.innerHTML = '<tr><td colspan="6" class="muted">Could not load contracts. Check you are signed in and the API is running.</td></tr>';
      }
    }
  }

  function renderDetailPanel(data) {
    const empty = $("contracts-detail-empty");
    const content = $("contracts-detail-content");
    if (!content) return;
    empty?.setAttribute("hidden", "");
    content.hidden = false;

    const timeline = (data.events || []).map(
      (event) => `<li class="contracts-timeline__item">
        <span class="contracts-timeline__dot">✓</span>
        <span><strong>${escapeHtml(event.event_type)}</strong><span class="muted"> · ${escapeHtml(formatDate(event.created_at))}${event.actor ? ` · ${escapeHtml(event.actor)}` : ""}</span></span>
      </li>`
    );

    content.innerHTML = `
      <div class="contracts-detail-head">
        <div>
          <h3>${escapeHtml(data.contract_number)}</h3>
          ${statusBadge(data.status)}
        </div>
      </div>
      <dl class="contracts-detail-grid">
        <div><dt>Template</dt><dd>${escapeHtml(data.template_name || data.template_id)}</dd></div>
        <div><dt>Customer</dt><dd>${escapeHtml(data.customer_legal_name)}</dd></div>
        <div><dt>Signatory</dt><dd>${escapeHtml(data.signatory_name || "Not set")}${data.signatory_title ? ` · ${escapeHtml(data.signatory_title)}` : ""}</dd></div>
        <div><dt>Email</dt><dd>${escapeHtml(data.signatory_email)}</dd></div>
        <div><dt>Effective date</dt><dd>${escapeHtml(formatDate(data.effective_date))}</dd></div>
        <div><dt>Sent / signed</dt><dd>${data.signed_at ? escapeHtml(formatDate(data.signed_at)) : data.sent_at ? `Sent ${escapeHtml(formatDate(data.sent_at))}` : "Not sent"}</dd></div>
      </dl>
      ${timeline.length ? `<ol class="contracts-timeline">${timeline.join("")}</ol>` : ""}
      <div class="contracts-preview-wrap">
        <h4 class="hr-section-title">Contract preview</h4>
        <div class="contract-preview-panel">${data.html || "<p class=\"muted\">No preview available.</p>"}</div>
      </div>
      <div class="contracts-detail-foot">
        <button type="button" class="btn" id="contracts-send-btn" ${data.status === "signed" ? "disabled" : ""}>Send for signature</button>
        <label class="btn ghost contracts-upload-btn">
          Upload signed PDF
          <input type="file" id="contracts-upload-input" accept="application/pdf,.pdf" hidden />
        </label>
      </div>
      <div id="contracts-signing-link" class="signing-link-box" hidden></div>
      <p class="edit-form-status muted" id="contracts-detail-status"></p>`;

    content.querySelector("#contracts-send-btn")?.addEventListener("click", () => sendContract(data.id));
    content.querySelector("#contracts-upload-input")?.addEventListener("change", (event) => {
      const file = event.target.files?.[0];
      if (file) uploadSignedPdf(data.id, file);
    });
  }

  async function selectContract(contractId, { scroll = true } = {}) {
    selectedContractId = contractId;
    renderContractsTable();
    const content = $("contracts-detail-content");
    if (content) content.innerHTML = '<p class="muted">Loading contract…</p>';
    try {
      const res = await apiFetch(`/contracts/${contractId}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Load failed");
      renderDetailPanel(data);
      if (scroll) content?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) {
      if (content) content.innerHTML = `<p class="muted">${escapeHtml(error.message || "Could not load contract.")}</p>`;
    }
  }

  async function sendContract(id) {
    const status = $("contracts-detail-status");
    if (status) status.textContent = "Sending for signature…";
    const res = await apiFetch(`/contracts/${id}/send`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      if (status) status.textContent = data.detail || "Send failed";
      return;
    }
    const linkBox = $("contracts-signing-link");
    if (linkBox && data.signing_url) {
      linkBox.hidden = false;
      linkBox.innerHTML = `<label class="edit-field"><span class="edit-label">Client signing link</span><input readonly value="${escapeHtml(data.signing_url)}" onclick="this.select()" /></label>`;
    }
    if (status) status.textContent = `Sent to ${data.signatory_email || "signatory"}.`;
    await loadContracts();
    await selectContract(id, { scroll: false });
  }

  async function uploadSignedPdf(id, file) {
    const status = $("contracts-detail-status");
    if (status) status.textContent = "Uploading signed PDF…";
    const formData = new FormData();
    formData.append("signed_pdf", file);
    try {
      const res = await apiFetch(`/contracts/${id}/upload-signed`, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");
      if (status) status.textContent = "Signed PDF stored.";
      await loadContracts();
      await selectContract(id, { scroll: false });
    } catch (error) {
      if (status) status.textContent = error.message || "Upload failed";
    }
  }

  async function mountContractForm() {
    const host = $("contract-generate-form");
    if (!host || formMounted) return;

    let profileValues = { effective_date: new Date().toISOString().slice(0, 10) };
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
          template_id: "pack",
          effective_date: new Date().toISOString().slice(0, 10),
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
        await loadContracts();
        const created = data.contract || (data.contracts || [])[0];
        if (created?.id) await selectContract(created.id);
        return data;
      },
    });
    formMounted = true;
  }

  async function initContractsSection() {
    await mountContractForm();
    await loadContracts();
  }

  function bindSectionEvents() {
    if (sectionBound) return;
    sectionBound = true;
    window.addEventListener("admin:section", (event) => {
      if (event.detail?.section === "contracts") initContractsSection();
    });
    if (parseHashBaseSection(window.location.hash) === "contracts") initContractsSection();
  }

  bindSectionEvents();
})();
