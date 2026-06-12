/** Offboarding workflows — leaver register with detail panel. */
(function () {
  const { apiFetch, renderTableBody, escapeHtml, statusPill, parseHashBaseSection } = window.Admin;

  let workflows = [];
  let selectedWorkflowId = null;
  let startBound = false;

  function $(id) {
    return document.getElementById(id);
  }

  function formatDate(value) {
    if (!value) return "Not set";
    try {
      return new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
    } catch {
      return value;
    }
  }

  function renderWorkflowsTable() {
    const tbody = $("offboarding-body");
    if (!tbody) return;
    if (!workflows.length) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="muted">No offboarding workflows yet. Start a leaver workflow above when an employee is leaving.</td></tr>';
      return;
    }
    tbody.innerHTML = workflows
      .map((row) => {
        const selected = selectedWorkflowId === row.id ? " hr-register-row--selected" : "";
        const cessation = row.sponsorship_cessation_required
          ? row.sponsorship_cessation_reference
            ? escapeHtml(row.sponsorship_cessation_reference)
            : '<span class="muted">Required</span>'
          : "Not required";
        return `<tr class="hr-register-row${selected}" data-workflow-id="${row.id}">
          <td><strong>OFF-${escapeHtml(row.id)}</strong><div class="muted">${formatDate(row.started_at)}</div></td>
          <td>${escapeHtml(row.employee_name || row.employee_id)}<div class="muted">${escapeHtml(row.employee_department || "")}</div></td>
          <td>${escapeHtml(row.reason)}</td>
          <td>${statusPill(row.status)}</td>
          <td>${escapeHtml(formatDate(row.acas_appeal_deadline))}</td>
          <td>${cessation}</td>
        </tr>`;
      })
      .join("");

    tbody.querySelectorAll(".hr-register-row").forEach((row) => {
      row.addEventListener("click", () => selectWorkflow(Number(row.dataset.workflowId)));
    });
  }

  function renderDetailPanel(row) {
    const empty = $("offboarding-detail-empty");
    const content = $("offboarding-detail-content");
    if (!content) return;
    empty?.setAttribute("hidden", "");
    content.hidden = false;
    content.innerHTML = `
      <div class="hr-detail-head">
        <div>
          <h3>OFF-${escapeHtml(row.id)}</h3>
          ${statusPill(row.status)}
        </div>
      </div>
      <dl class="hr-detail-grid">
        <div><dt>Employee</dt><dd>${escapeHtml(row.employee_name || row.employee_id)} · ${escapeHtml(row.employee_department || "Not set")}</dd></div>
        <div><dt>Reason</dt><dd>${escapeHtml(row.reason)}</dd></div>
        <div><dt>Started</dt><dd>${escapeHtml(formatDate(row.started_at))}</dd></div>
        <div><dt>ACAS appeal by</dt><dd>${escapeHtml(formatDate(row.acas_appeal_deadline))}</dd></div>
        <div><dt>Sponsor cessation</dt><dd>${row.sponsorship_cessation_required ? (row.sponsorship_cessation_reference ? escapeHtml(row.sponsorship_cessation_reference) : "Required — not yet reported") : "Not required"}</dd></div>
        ${row.grievance_case_id ? `<div><dt>Linked grievance</dt><dd><a href="#grievance">Case #${escapeHtml(row.grievance_case_id)}</a></dd></div>` : ""}
      </dl>
      <div class="hr-detail-foot">
        ${row.sponsorship_cessation_required && !row.sponsorship_cessation_reference ? `<button type="button" class="btn" id="offboarding-cessation-btn">Report cessation</button>` : ""}
        <a class="btn ghost" href="#employees/${escapeHtml(row.employee_id)}/offboarding">Open employee offboarding</a>
      </div>`;
    content.querySelector("#offboarding-cessation-btn")?.addEventListener("click", () => reportCessation(row.id));
  }

  async function selectWorkflow(workflowId) {
    selectedWorkflowId = workflowId;
    renderWorkflowsTable();
    const row = workflows.find((w) => w.id === workflowId);
    if (row) renderDetailPanel(row);
  }

  async function reportCessation(workflowId) {
    const ref = window.prompt("Home Office cessation report reference:");
    if (!ref) return;
    const res = await apiFetch(`/offboarding/workflows/${workflowId}/cessation-reported`, {
      method: "POST",
      body: JSON.stringify({ report_reference: ref }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || "Update failed");
      return;
    }
    await loadWorkflows();
    await selectWorkflow(workflowId);
  }

  async function loadWorkflows() {
    try {
      const res = await apiFetch("/offboarding/workflows");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      workflows = data.items || [];
      renderWorkflowsTable();
    } catch {
      workflows = [];
      renderWorkflowsTable();
    }
  }

  async function loadEmployeeSelect() {
    const select = $("offboarding-employee");
    if (!select) return;
    try {
      const res = await apiFetch("/admin/employees");
      const data = await res.json();
      select.innerHTML = (data.items || [])
        .map((emp) => `<option value="${emp.id}">${escapeHtml(emp.first_name)} ${escapeHtml(emp.last_name)}</option>`)
        .join("");
    } catch {
      select.innerHTML = `<option value="">Could not load employees</option>`;
    }
  }

  function bindStartForm() {
    if (startBound) return;
    $("offboarding-start-btn")?.addEventListener("click", async () => {
      const employeeId = $("offboarding-employee")?.value;
      const reason = $("offboarding-reason")?.value?.trim();
      if (!employeeId || !reason) {
        alert("Select employee and enter a reason.");
        return;
      }
      if (!window.confirm("Start offboarding for this employee? An ACAS appeal window will be recorded.")) return;
      const res = await apiFetch("/offboarding/workflows", {
        method: "POST",
        body: JSON.stringify({ employee_id: Number(employeeId), reason }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || "Could not start workflow");
        return;
      }
      $("offboarding-reason").value = "";
      await loadWorkflows();
      if (data.id) await selectWorkflow(data.id);
    });
    startBound = true;
  }

  async function initOffboardingSection() {
    bindStartForm();
    await loadEmployeeSelect();
    await loadWorkflows();
  }

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "offboarding") initOffboardingSection();
  });

  if (parseHashBaseSection(window.location.hash) === "offboarding") initOffboardingSection();
})();
