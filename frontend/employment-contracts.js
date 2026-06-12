/** Employment contracts — generate from ACAS-aligned templates, send to employees, store signed copies. */
(function () {
  const { apiFetch, loadFormOptions, loadEmployees, escapeHtml, parseHashBaseSection } = window.Admin;

  let contracts = [];
  let templates = [];
  let selectedContractId = null;
  let generateBound = false;
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

  function sourceBadge(row) {
    if (row.template_source === "acas") {
      return `<span class="status-pill status-ok">ACAS-aligned</span>`;
    }
    return `<span class="status-pill">ShiftSwift</span>`;
  }

  async function loadTemplates() {
    try {
      const res = await apiFetch("/employment-contracts/templates");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      templates = data.items || [];
      renderTemplateLibrary();
    } catch {
      templates = [];
      const list = $("employment-template-list");
      if (list) list.innerHTML = '<p class="muted">Could not load contract templates.</p>';
    }
  }

  function renderTemplateLibrary() {
    const list = $("employment-template-list");
    if (!list) return;
    if (!templates.length) {
      list.innerHTML = '<p class="muted">No employment contract templates seeded. Run scripts/seed_hr_templates.py after migration 048.</p>';
      return;
    }
    list.innerHTML = templates
      .map(
        (tpl) => `<div class="hr-template-card">
          <div class="hr-template-card__head">
            <strong>${escapeHtml(tpl.title)}</strong>
            ${tpl.update_available ? '<span class="status-pill status-warning">Update available</span>' : ""}
          </div>
          <p class="muted">${escapeHtml(tpl.description || "")}</p>
          <p class="muted" style="font-size:0.85rem;">Platform v${escapeHtml(tpl.platform_version)} · ${sourceBadge({ template_source: tpl.source })}</p>
          ${tpl.source_url ? `<p class="muted" style="font-size:0.85rem;"><a href="${escapeHtml(tpl.source_url)}" target="_blank" rel="noopener">ACAS source →</a></p>` : ""}
        </div>`
      )
      .join("");
  }

  function renderContractsTable() {
    const tbody = $("employment-contracts-body");
    if (!tbody) return;
    if (!contracts.length) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="muted">No employment contracts yet. Generate one for an employee using a template above.</td></tr>';
      return;
    }
    tbody.innerHTML = contracts
      .map((row) => {
        const selected = selectedContractId === row.id ? " contracts-case-row--selected" : "";
        return `<tr class="contracts-case-row hr-register-row${selected}" data-contract-id="${row.id}">
          <td><strong>${escapeHtml(row.contract_number)}</strong><div class="muted">${formatDate(row.created_at)}</div></td>
          <td>${escapeHtml(row.employee_name)}</td>
          <td>${escapeHtml(row.title)}</td>
          <td>${statusBadge(row.status)}</td>
          <td>v${escapeHtml(row.platform_template_version || "?")}</td>
          <td>${row.signed_at ? escapeHtml(formatDate(row.signed_at)) : row.sent_at ? '<span class="muted">Awaiting signature</span>' : '<span class="muted">Not sent</span>'}</td>
        </tr>`;
      })
      .join("");
    tbody.querySelectorAll(".contracts-case-row").forEach((row) => {
      row.addEventListener("click", () => selectContract(Number(row.dataset.contractId)));
    });
  }

  async function loadContracts() {
    const tbody = $("employment-contracts-body");
    if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="muted">Loading employment contracts…</td></tr>';
    try {
      const res = await apiFetch("/employment-contracts");
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
        tbody.innerHTML = '<tr><td colspan="6" class="muted">Could not load employment contracts.</td></tr>';
      }
    }
  }

  function renderDetailPanel(data) {
    const empty = $("employment-contracts-detail-empty");
    const content = $("employment-contracts-detail-content");
    if (!content) return;
    empty?.setAttribute("hidden", "");
    content.hidden = false;
    const preview = data.html
      ? `<div class="contracts-preview-wrap"><div class="contracts-preview">${data.html}</div></div>`
      : '<p class="muted">No preview available.</p>';
    content.innerHTML = `
      <div class="hr-detail-head">
        <div>
          <h3>${escapeHtml(data.contract_number)}</h3>
          ${statusBadge(data.status)}
        </div>
      </div>
      <dl class="hr-detail-grid">
        <div><dt>Employee</dt><dd>${escapeHtml(data.employee_name)}</dd></div>
        <div><dt>Email</dt><dd>${escapeHtml(data.employee_email || "Not set")}</dd></div>
        <div><dt>Template</dt><dd>${escapeHtml(data.title)} (v${escapeHtml(data.platform_template_version)})</dd></div>
        <div><dt>Source</dt><dd>${data.template_source === "acas" ? "ACAS-aligned" : "ShiftSwift"}${data.template_source_url ? ` · <a href="${escapeHtml(data.template_source_url)}" target="_blank" rel="noopener">View guidance</a>` : ""}</dd></div>
        ${data.employee_document_id ? `<div><dt>Employee file</dt><dd>Saved to document store (#${escapeHtml(data.employee_document_id)})</dd></div>` : ""}
      </dl>
      ${preview}
      <div class="hr-detail-foot">
        ${data.status !== "signed" ? `<button type="button" class="btn" id="employment-contract-send-btn">Send for signature</button>` : ""}
        <a class="btn ghost" href="#employees/${escapeHtml(data.employee_id)}/document_store">Open employee documents</a>
      </div>
      <div id="employment-signing-link-box" class="signing-link-box" hidden></div>
      <p class="muted" id="employment-contract-action-status"></p>`;
    content.querySelector("#employment-contract-send-btn")?.addEventListener("click", () => sendContract(data.id));
  }

  async function selectContract(id, { scroll = true } = {}) {
    selectedContractId = id;
    renderContractsTable();
    try {
      const res = await apiFetch(`/employment-contracts/${id}`);
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      renderDetailPanel(data);
      if (scroll) $("employment-contracts-detail-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) {
      const status = $("employment-contract-action-status");
      if (status) status.textContent = error.message || "Could not load contract";
    }
  }

  async function sendContract(id) {
    const status = $("employment-contract-action-status");
    if (status) status.textContent = "Sending signing link…";
    try {
      const res = await apiFetch(`/employment-contracts/${id}/send`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Send failed");
      const box = $("employment-signing-link-box");
      if (box) {
        box.hidden = false;
        box.innerHTML = `<p><strong>Signing link</strong> (also emailed to employee):</p>
          <input type="text" readonly value="${escapeHtml(data.signing_url)}" style="width:100%;" onclick="this.select()" />`;
      }
      if (status) status.textContent = "Sent for signature.";
      await loadContracts();
      await selectContract(id, { scroll: false });
    } catch (error) {
      if (status) status.textContent = error.message || "Send failed";
    }
  }

  function bindGenerateForm() {
    if (generateBound) return;
    const form = $("employment-contract-generate-form");
    if (!form) return;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const status = $("employment-contract-generate-status");
      const employeeId = form.employee_id.value;
      const templateId = form.template_id.value;
      if (!employeeId || !templateId) {
        if (status) status.textContent = "Select an employee and template.";
        return;
      }
      if (status) status.textContent = "Generating…";
      try {
        const res = await apiFetch("/employment-contracts/generate", {
          method: "POST",
          body: JSON.stringify({ employee_id: Number(employeeId), template_id: templateId }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Generation failed");
        if (status) status.textContent = "Contract generated.";
        form.reset();
        await loadContracts();
        if (data.contract?.id) await selectContract(data.contract.id);
      } catch (error) {
        if (status) status.textContent = error.message || "Generation failed";
      }
    });
    generateBound = true;
  }

  async function populateGenerateSelects() {
    await loadFormOptions();
    const employees = await loadEmployees();
    const employeeSelect = $("employment-contract-employee");
    const templateSelect = $("employment-contract-template");
    if (employeeSelect) {
      employeeSelect.innerHTML =
        `<option value="">Select employee…</option>` +
        employees.map((emp) => `<option value="${escapeHtml(emp.value)}">${escapeHtml(emp.label)}</option>`).join("");
    }
    if (templateSelect) {
      templateSelect.innerHTML =
        `<option value="">Select template…</option>` +
        templates
          .map(
            (tpl) =>
              `<option value="${escapeHtml(tpl.id)}">${escapeHtml(tpl.title)} (v${escapeHtml(tpl.platform_version)})</option>`
          )
          .join("");
    }
  }

  async function initEmploymentContractsSection() {
    bindGenerateForm();
    await loadTemplates();
    await populateGenerateSelects();
    await loadContracts();
  }

  function bindSectionEvents() {
    if (sectionBound) return;
    sectionBound = true;
    window.addEventListener("admin:section", (event) => {
      if (event.detail?.section === "employment-contracts") initEmploymentContractsSection();
    });
    if (parseHashBaseSection(window.location.hash) === "employment-contracts") initEmploymentContractsSection();
  }

  bindSectionEvents();
})();
