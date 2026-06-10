/** Employee workspace — lifecycle flow aligned to HR chart (recruitment → off-boarding). */
(function () {
  const { apiFetch, escapeHtml, mountEditForm, renderTableBody, statusPill, loadFormOptions, isFeatureEnabled } = window.Admin;

  const SECTION_SCHEMAS = {
    recruitment: {
      id: "employee-recruitment",
      columns: 2,
      submitLabel: "Save recruitment details",
      successMessage: "Recruitment details saved.",
      fields: [
        { name: "first_name", label: "First name", type: "text", required: true },
        { name: "last_name", label: "Last name", type: "text", required: true },
        { name: "email", label: "Work email", type: "email" },
        {
          name: "worker_type",
          label: "Employee type",
          type: "select",
          optionsKey: "worker_types",
          defaultValue: "standard",
        },
      ],
    },
    onboarding: {
      id: "employee-onboarding",
      columns: 2,
      submitLabel: "Save on-boarding details",
      successMessage: "On-boarding details saved.",
      fields: [
        { name: "job_title", label: "Job title", type: "text", required: true },
        { name: "start_date", label: "Start date", type: "date", required: true },
        { name: "status", label: "Status", type: "select", optionsKey: "employee_statuses", defaultValue: "onboarding" },
        { name: "department", label: "Department", type: "text", placeholder: "Kitchen, Front of house…" },
        { name: "employment_type", label: "Employment type", type: "select", optionsKey: "employment_types", defaultValue: "full_time" },
        { name: "work_location", label: "Work location", type: "text", placeholder: "London site" },
        { name: "probation_end_date", label: "Probation end date", type: "date" },
      ],
    },
    induction: {
      id: "employee-induction",
      columns: 2,
      submitLabel: "Save personal information",
      successMessage: "Personal information saved.",
      fields: [
        { name: "phone", label: "Mobile phone", type: "tel", required: true },
        { name: "date_of_birth", label: "Date of birth", type: "date" },
        { name: "ni_number", label: "National Insurance number", type: "text", placeholder: "AB 12 34 56 A" },
        { name: "home_address", label: "Home address", type: "textarea", span: 2, rows: 3, required: true },
        { name: "emergency_contact_name", label: "Emergency contact name", type: "text", required: true },
        { name: "emergency_contact_phone", label: "Emergency contact phone", type: "tel", required: true },
        { name: "emergency_contact_relationship", label: "Relationship", type: "text", placeholder: "Partner, parent…" },
      ],
    },
    job_performance: {
      id: "employee-job-performance",
      columns: 2,
      submitLabel: "Save salary details",
      successMessage: "Salary details saved.",
      fields: [
        { name: "salary", label: "Annual salary (£)", type: "number", placeholder: "28000", required: true },
      ],
    },
    compliance_reporting: {
      id: "employee-compliance",
      columns: 2,
      submitLabel: "Save compliance details",
      successMessage: "Compliance details saved.",
      fields: [
        { name: "visa_type", label: "Visa type", type: "text", placeholder: "Skilled Worker", required: true },
        { name: "visa_expiry_date", label: "Visa expiry date", type: "date" },
        { name: "share_code", label: "GOV.UK share code", type: "text" },
        { name: "cos_reference", label: "CoS reference", type: "text" },
        { name: "rtw_status", label: "Right to work status", type: "select", optionsKey: "rtw_statuses", defaultValue: "pending" },
      ],
    },
    offboarding: {
      id: "employee-offboarding",
      columns: 2,
      submitLabel: "Save off-boarding details",
      successMessage: "Off-boarding details saved.",
      fields: [
        { name: "termination_date", label: "Leave date", type: "date" },
        { name: "termination_reason", label: "Reason", type: "textarea", span: 2, rows: 3 },
      ],
    },
  };

  const SECTION_HINTS = {
    recruitment: "Set employee type here. Sponsor compliance (step 9) unlocks only for sponsored workers.",
    onboarding: "Set status to <strong>Onboarding</strong> for new starters. Probation end must be on or after start date.",
    induction: "Phone, home address, and emergency contact are required. NI number is validated when provided.",
    job_performance: "Salary is exported to BrightPay or Xero with employee CSV.",
    compliance_reporting: "Visa type plus a GOV.UK share code <em>or</em> CoS reference required.",
    offboarding: "Set employee status to <strong>Terminated</strong> in on-boarding (or off-boarding workflow) to unlock this step.",
  };

  const LINK_SECTIONS = {
    development: {
      title: "Development",
      body: "Training and career path planning. Use HR templates to assign development plans and role progression documents.",
      links: [{ href: "#templates", label: "HR Templates & AI" }],
    },
    support: {
      title: "Support",
      branch: "Health & wellbeing",
      body: "Mentoring, workplace assistance, and wellbeing resources. Link grievance or compliance workflows when needed.",
      links: [
        { href: "#grievance", label: "Grievance cases" },
        { href: "#compliance", label: "Sponsor compliance" },
      ],
    },
    performance_improvement: {
      title: "Performance improvement",
      branch: "Training & CPD",
      body: "Review sessions, feedback, and continuing professional development records.",
      links: [{ href: "#templates", label: "Training templates" }],
    },
  };

  const QUICK_ADD_SCHEMA = {
    id: "employee-quick-add",
    columns: 2,
    submitLabel: "Create employee",
    successMessage: "Employee created. Continue the lifecycle from step 1.",
    fields: [
      { name: "first_name", label: "First name", type: "text", required: true },
      { name: "last_name", label: "Last name", type: "text", required: true },
      { name: "email", label: "Work email", type: "email" },
    ],
  };

  let activeEmployeeId = null;
  let activeSection = "recruitment";
  let workspaceCache = null;
  let sectionLoaded = false;
  let openEmployeeRequest = 0;

  function $(id) {
    return document.getElementById(id);
  }

  function showListView() {
    $("employees-list-view")?.removeAttribute("hidden");
    $("employees-detail-view")?.setAttribute("hidden", "");
    activeEmployeeId = null;
    workspaceCache = null;
    window.location.hash = "employees";
  }

  function showDetailView() {
    $("employees-list-view")?.setAttribute("hidden", "");
    $("employees-detail-view")?.removeAttribute("hidden");
    $("employee-advanced-links")?.removeAttribute("hidden");
  }

  function renderAdvancedLinks(employee) {
    const host = $("employee-advanced-link-row");
    if (!host) return;
    const sponsored = Boolean(employee?.is_sponsored);
    const payroll = isFeatureEnabled("payroll");
    host.innerHTML = `
      ${sponsored ? '<a href="#compliance" class="btn ghost">Sponsor compliance</a>' : ""}
      ${payroll ? '<a href="#payroll" class="btn ghost">Payroll</a>' : ""}
      <a href="#grievance" class="btn ghost">Grievance cases</a>
      <a href="#offboarding" class="btn ghost">Off-boarding workflow</a>
      <a href="#time-punch" class="btn ghost">Time punch</a>`;
  }

  function normalizePayload(section, payload) {
    const body = { ...payload };
    if (section === "job_performance" && body.salary !== undefined && body.salary !== "") {
      body.salary = Number(body.salary);
    } else if (section === "job_performance") {
      body.salary = null;
    }
    Object.keys(body).forEach((key) => {
      if (body[key] === "") body[key] = null;
    });
    return body;
  }

  function sectionMeta(key) {
    return (window.Admin.formOptions?.employee_sections || []).find((item) => item.value === key);
  }

  function sectionLabel(key) {
    return sectionMeta(key)?.label || key;
  }

  function sectionKindTag(section) {
    if (section.kind === "link") return `<span class="lifecycle-kind">Guidance</span>`;
    if (section.kind === "documents") return `<span class="lifecycle-kind">Documents</span>`;
    return "";
  }

  function lifecycleAccordionHost() {
    return $("employee-lifecycle-accordion");
  }

  function renderLifecycleAccordion(workspace) {
    const accordion = lifecycleAccordionHost();
    if (!accordion) return;

    accordion.innerHTML = (workspace.sections || [])
      .map((section) => {
        const isOpen = section.key === activeSection;
        const state = section.complete ? "complete" : "pending";
        const kindTag = sectionKindTag(section);
        const branch = section.branch
          ? `<span class="lifecycle-tag">${escapeHtml(section.branch)}</span>`
          : "";
        const stepLabel = section.complete && !isOpen ? "✓" : section.step;
        return `<section class="lifecycle-accordion-item lifecycle-accordion-item--${state}${isOpen ? " is-open" : ""}" data-section="${escapeHtml(section.key)}">
          <button type="button" class="lifecycle-accordion-header" data-section="${escapeHtml(section.key)}" aria-expanded="${isOpen}">
            <span class="lifecycle-accordion-num">${stepLabel}</span>
            <span class="lifecycle-accordion-copy">
              <strong>${escapeHtml(section.label)}</strong>
              ${kindTag}
              <span class="muted">${escapeHtml(section.description || "")}</span>
              ${branch}
            </span>
            <span class="lifecycle-accordion-chevron" aria-hidden="true"></span>
          </button>
          <div class="lifecycle-accordion-body"${isOpen ? "" : " hidden"}>
            <div class="lifecycle-accordion-content" data-section-content="${escapeHtml(section.key)}"></div>
          </div>
        </section>`;
      })
      .join("");

    accordion.querySelectorAll(".lifecycle-accordion-header").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.section;
        const item = btn.closest(".lifecycle-accordion-item");
        if (key === activeSection && item?.classList.contains("is-open")) {
          item.classList.remove("is-open");
          btn.setAttribute("aria-expanded", "false");
          item.querySelector(".lifecycle-accordion-body")?.setAttribute("hidden", "");
          return;
        }
        activeSection = key;
        window.location.hash = `employees/${activeEmployeeId}/${activeSection}`;
        renderLifecycleAccordion(workspace);
      });
    });

    const contentHost = accordion.querySelector(`[data-section-content="${activeSection}"]`);
    if (contentHost) {
      renderSectionContent(workspace, activeSection, contentHost);
    }
  }

  function renderProgress(workspace) {
    const pct = workspace.completion_pct || 0;
    $("employee-progress-fill").style.width = `${pct}%`;
    const next = workspace.next_section ? sectionLabel(workspace.next_section) : "Complete";
    $("employee-progress-label").textContent = `Lifecycle ${pct}% complete · next: ${next}`;
  }

  function categoryLabel(value) {
    const categories = window.Admin.formOptions?.employee_document_categories || [];
    return categories.find((item) => item.value === value)?.label || value;
  }

  function renderRequirementsChecklist(requirements) {
    if (!requirements?.items?.length) return "";
    const summary = requirements.complete
      ? `<p class="employee-doc-status employee-doc-status--ok">All required documents recorded.</p>`
      : `<p class="employee-doc-status employee-doc-status--warn">${requirements.missing_required} required document(s) still missing.</p>`;
    const list = requirements.items
      .map((item) => {
        const state = item.satisfied ? "complete" : item.required ? "missing" : "optional";
        const badge = item.satisfied ? "✓" : item.required ? "!" : "·";
        return `<li class="employee-doc-req employee-doc-req--${state}"><span>${badge}</span> ${escapeHtml(item.label)}${item.required ? "" : " <span class='muted'>(optional)</span>"}</li>`;
      })
      .join("");
    return `${summary}<ul class="employee-doc-checklist">${list}</ul>`;
  }

  function renderDocumentStorePanel(workspace, container) {
    const section = (workspace.sections || []).find((item) => item.key === "document_store");
    const requirements = workspace.document_requirements || {};
    const docs = workspace.documents || [];

    container.innerHTML = `
      <div class="employee-section-intro">
        <h4>${escapeHtml(section?.label || "Document store")}</h4>
        <p class="muted">${escapeHtml(section?.description || "")}</p>
        ${renderRequirementsChecklist(requirements)}
      </div>
      <div id="employee-document-form"></div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Title</th><th>Category</th><th>Expires</th><th>Added</th><th></th></tr></thead>
          <tbody id="employee-documents-body"></tbody>
        </table>
      </div>`;

    mountEditForm(container.querySelector("#employee-document-form"), {
      id: "employee-document",
      columns: 2,
      submitLabel: "Add document",
      successMessage: "Document added.",
      fields: [
        { name: "title", label: "Title", type: "text", required: true },
        {
          name: "category",
          label: "Category",
          type: "select",
          optionsKey: "employee_document_categories",
          defaultValue: "contract",
        },
        { name: "document_url", label: "Document URL", type: "url", placeholder: "https://..." },
        { name: "expires_at", label: "Expiry date", type: "date" },
        { name: "notes", label: "Notes", type: "textarea", span: 2 },
      ],
    }, {
      onSubmit: async (payload) => {
        const res = await apiFetch(`/admin/employees/${activeEmployeeId}/documents`, {
          method: "POST",
          body: JSON.stringify({
            ...payload,
            lifecycle_stage: "document_store",
            document_url: payload.document_url || null,
            notes: payload.notes || null,
            expires_at: payload.expires_at || null,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Save failed");
        await openEmployee(activeEmployeeId, "document_store");
        if (workspaceCache?.document_requirements?.complete && workspaceCache.next_section) {
          const next = workspaceCache.next_section;
          if (next !== "document_store") {
            activeSection = next;
            window.location.hash = `employees/${activeEmployeeId}/${next}`;
            renderLifecycleAccordion(workspaceCache);
          }
        }
      },
    });

    renderTableBody(container.querySelector("#employee-documents-body"), {
      emptyMessage: "No documents recorded yet.",
      columns: [
        { key: "title", render: (row) => `<strong>${escapeHtml(row.title)}</strong>` },
        { key: "category", render: (row) => escapeHtml(categoryLabel(row.category)) },
        { key: "expires_at", render: (row) => escapeHtml((row.expires_at || "").slice(0, 10) || "Not set") },
        { key: "created_at", render: (row) => escapeHtml((row.created_at || "").slice(0, 10) || "Not set") },
        {
          key: "actions",
          render: (row) =>
            `<div class="table-actions">
              ${row.document_url ? `<a class="btn ghost" href="${escapeHtml(row.document_url)}" target="_blank" rel="noopener">Open</a>` : ""}
              <button type="button" class="btn ghost" data-delete-doc="${row.id}">Remove</button>
            </div>`,
        },
      ],
      rows: docs,
    });

    container.querySelectorAll("[data-delete-doc]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!window.confirm("Remove this document record?")) return;
        const res = await apiFetch(`/admin/employees/${activeEmployeeId}/documents/${btn.dataset.deleteDoc}`, {
          method: "DELETE",
        });
        if (!res.ok) {
          const err = await res.json();
          alert(err.detail || "Delete failed");
          return;
        }
        await openEmployee(activeEmployeeId, "document_store");
      });
    });
  }

  function renderLinkPanel(section, container) {
    const meta = LINK_SECTIONS[section.key] || {};
    container.innerHTML = `
      <div class="employee-section-intro">
        <h4>${escapeHtml(meta.title || section.label)}</h4>
        ${meta.branch ? `<span class="lifecycle-tag">${escapeHtml(meta.branch)}</span>` : ""}
        <p class="muted">${escapeHtml(meta.body || section.description || "")}</p>
        <p class="link-row">${(meta.links || []).map((link) => `<a class="btn ghost" href="${escapeHtml(link.href)}">${escapeHtml(link.label)}</a>`).join(" ")}</p>
      </div>`;
  }

  function buildSectionIntro(section, workspace) {
    let intro = `<h4>${escapeHtml(section.label)}</h4><p class="muted">${escapeHtml(section.description || "")}</p>`;
    if (section.branch) {
      intro += `<span class="lifecycle-tag">${escapeHtml(section.branch)}</span>`;
    }
    const hint = SECTION_HINTS[section.key];
    if (hint) {
      intro += `<p class="employee-section-hint">${hint}</p>`;
    }
    if (section.key === "job_performance") {
      intro += `<p class="employee-section-hint">Include salary here so payroll CSV exports are ready for BrightPay or Xero.</p>`;
    }
    return intro;
  }

  function renderSectionContent(workspace, sectionKey, container) {
    if (!container) return;

    const section = (workspace.sections || []).find((item) => item.key === sectionKey);
    if (!section) {
      container.innerHTML = `<p class="muted">This lifecycle step is not available for this employee.</p>`;
      return;
    }

    if (section.kind === "link") {
      renderLinkPanel(section, container);
      return;
    }

    if (section.kind === "documents") {
      renderDocumentStorePanel(workspace, container);
      return;
    }

    const schema = SECTION_SCHEMAS[sectionKey];
    if (!schema) {
      container.innerHTML = `<p class="muted">This section is not available.</p>`;
      return;
    }

    const intro = buildSectionIntro(section, workspace);
    container.innerHTML = `<div class="employee-section-intro">${intro}</div><div id="employee-section-form"></div>`;

    mountEditForm(container.querySelector("#employee-section-form"), schema, {
      values: section.data || {},
      onSubmit: async (payload) => {
        const res = await apiFetch(`/admin/employees/${activeEmployeeId}/sections/${sectionKey}`, {
          method: "PATCH",
          body: JSON.stringify(normalizePayload(sectionKey, payload)),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Save failed");
        workspaceCache = data;
        if (sectionKey === "recruitment") {
          window.dispatchEvent(new CustomEvent("admin:features-refresh"));
        }
        renderWorkspace(data);
        const next = data.next_section;
        if (next && next !== sectionKey) {
          activeSection = next;
          window.location.hash = `employees/${activeEmployeeId}/${next}`;
          renderLifecycleAccordion(data);
        }
      },
    });
  }

  function renderWorkspace(workspace) {
    workspaceCache = workspace;
    const employee = workspace.employee || {};
    $("employee-workspace-title").textContent = `${employee.first_name || ""} ${employee.last_name || ""}`.trim() || "Employee";
    const typeLabel = employee.is_sponsored ? "Sponsored worker" : "Standard employee";
    $("employee-workspace-subtitle").textContent = [typeLabel, employee.job_title, employee.department, employee.email]
      .filter(Boolean)
      .join(" · ");
    renderAdvancedLinks(employee);
    renderProgress(workspace);

    const sectionKeys = (workspace.sections || []).map((s) => s.key);
    if (!sectionKeys.includes(activeSection)) {
      activeSection = workspace.next_section || "recruitment";
    }
    renderLifecycleAccordion(workspace);
  }

  async function openEmployee(employeeId, section = null) {
    const requestId = ++openEmployeeRequest;
    const desired = section ? `employees/${employeeId}/${section}` : `employees/${employeeId}`;
    if (window.location.hash.replace("#", "") !== desired) {
      window.location.hash = desired;
    }
    activeEmployeeId = employeeId;
    showDetailView();
    const accordion = lifecycleAccordionHost();
    if (accordion) accordion.innerHTML = `<p class="muted lifecycle-accordion-content">Loading employee lifecycle…</p>`;

    const res = await apiFetch(`/admin/employees/${employeeId}/workspace`);
    if (requestId !== openEmployeeRequest) return;
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Could not load employee");
      showListView();
      return;
    }

    activeSection = section || data.next_section || "recruitment";
    renderWorkspace(data);
  }

  async function refreshEmployeesTable() {
    const tbody = $("employees-table-body");
    if (!tbody) return;

    try {
      const res = await apiFetch("/admin/employees");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      renderTableBody(tbody, {
        emptyMessage: "No employees yet. Add your first team member above.",
        columns: [
          {
            key: "name",
            render: (row) =>
              `<strong>${escapeHtml(row.first_name)} ${escapeHtml(row.last_name)}</strong>${row.job_title ? `<div class="muted">${escapeHtml(row.job_title)}</div>` : ""}`,
          },
          { key: "department", render: (row) => escapeHtml(row.department || "Not set") },
          { key: "status", render: (row) => statusPill(row.status) },
          {
            key: "profile",
            render: (row) => {
              const next = row.next_section ? sectionLabel(row.next_section) : "Complete";
              return `<span class="employee-profile-pill">${escapeHtml(String(row.completion_pct ?? 0))}%</span>
                <div class="muted">${escapeHtml(next)}</div>`;
            },
          },
          {
            key: "actions",
            render: (row) =>
              `<div class="table-actions">
                <button type="button" class="btn" data-open="${row.id}">Open lifecycle</button>
                <button type="button" class="btn ghost" data-delete="${row.id}">Remove</button>
              </div>`,
          },
        ],
        rows: data.items || [],
      });

      tbody.querySelectorAll("[data-open]").forEach((btn) => {
        btn.addEventListener("click", () => openEmployee(Number(btn.dataset.open)));
      });

      tbody.querySelectorAll("[data-delete]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          if (!window.confirm("Remove this employee record?")) return;
          const res = await apiFetch(`/admin/employees/${btn.dataset.delete}`, { method: "DELETE" });
          if (!res.ok) {
            const err = await res.json();
            alert(err.detail || "Delete failed");
            return;
          }
          await refreshEmployeesTable();
        });
      });
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }],
        rows: [],
        emptyMessage: "Could not load employees.",
      });
    }
  }

  function mountQuickAddForm() {
    const host = $("employee-quick-add-form");
    if (!host) return;
    mountEditForm(host, QUICK_ADD_SCHEMA, {
      onSubmit: async (payload) => {
        const res = await apiFetch("/admin/employees", {
          method: "POST",
          body: JSON.stringify({
            ...payload,
            email: payload.email || null,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Create failed");
        await refreshEmployeesTable();
        await openEmployee(data.id, "recruitment");
      },
    });
  }

  async function initEmployeesSection() {
    if (sectionLoaded) return;
    sectionLoaded = true;
    await loadFormOptions();
    mountQuickAddForm();
    await refreshEmployeesTable();
  }

  $("employee-back-btn")?.addEventListener("click", showListView);

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section !== "employees") return;
    initEmployeesSection();

    const hash = window.location.hash.replace("#", "");
    const match = hash.match(/^employees\/(\d+)(?:\/([\w_]+))?$/);
    if (match) {
      openEmployee(Number(match[1]), match[2] || null);
    } else {
      showListView();
    }
  });

  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "");
    if (hash === "employees") {
      if (document.getElementById("employees")?.classList.contains("admin-section--active")) {
        showListView();
      }
      return;
    }
    if (!hash.startsWith("employees/")) return;
    const match = hash.match(/^employees\/(\d+)(?:\/([\w_]+))?$/);
    if (!match) return;
    const id = Number(match[1]);
    const section = match[2] || null;
    if (id === activeEmployeeId) {
      if (section && section !== activeSection && workspaceCache) {
        activeSection = section;
        renderLifecycleAccordion(workspaceCache);
      }
      return;
    }
    openEmployee(id, section);
  });
})();
