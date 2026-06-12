/** Recruitment pipeline — 10-step vacancy flow with pipeline cards and side panel. */
(function () {
  const { apiFetch, escapeHtml, mountEditForm, renderTableBody, loadFormOptions } = window.Admin;

  const PIPELINE_SHORT = {
    vacancy_identified: "Vacancy",
    job_description: "Description",
    multi_channel_posting: "Advert",
    application_intake: "Applications",
    automated_screening: "Screening",
    candidate_pipeline: "Shortlist",
    interview_scheduling: "Interview",
    hiring_decision: "Decision",
    offer_management: "Offer",
    offer_accepted: "Onboard",
  };

  const CLOSED_STATUSES = new Set(["closed", "rejected", "onboarding_started"]);

  const SECTION_SCHEMAS = {
    vacancy_identified: {
      id: "vacancy-identified",
      columns: 2,
      submitLabel: "Create vacancy",
      successMessage: "Vacancy created.",
      fields: [
        { name: "job_title", label: "Job title", type: "text", required: true, placeholder: "e.g. Kitchen Porter, Floor Supervisor" },
        { name: "reference", label: "Vacancy reference", type: "text", placeholder: "Auto-generated if blank" },
        {
          name: "department",
          label: "Department",
          type: "select",
          optionsKey: "recruitment_departments",
          defaultValue: "kitchen",
        },
        { name: "department_other", label: "Department (other)", type: "text", placeholder: "Specify department" },
        { name: "location", label: "Location", type: "text", placeholder: "e.g. Nottingham" },
        {
          name: "worker_type",
          label: "Role type",
          type: "select",
          optionsKey: "worker_types",
          defaultValue: "standard",
        },
      ],
    },
    job_description: {
      id: "job-description",
      columns: 2,
      submitLabel: "Save job description",
      successMessage: "Job description saved.",
      fields: [
        { name: "job_description", label: "Description", type: "textarea", span: 2, rows: 4, required: true },
        { name: "required_skills", label: "Required skills & experience", type: "textarea", span: 2, rows: 3 },
        { name: "salary_range_min", label: "Salary from (£)", type: "number", placeholder: "24000" },
        { name: "salary_range_max", label: "Salary to (£)", type: "number", placeholder: "32000" },
      ],
    },
    application_intake: {
      id: "application-intake",
      columns: 2,
      submitLabel: "Save application",
      successMessage: "Application saved.",
      fields: [
        { name: "candidate_name", label: "Candidate name", type: "text", required: true },
        { name: "candidate_email", label: "Candidate email", type: "email", required: true },
        { name: "candidate_phone", label: "Phone", type: "tel" },
        { name: "application_source", label: "Source", type: "text", placeholder: "Indeed, referral…" },
        { name: "candidate_cv_url", label: "CV / application URL", type: "url", span: 2 },
      ],
    },
    automated_screening: {
      id: "automated-screening",
      columns: 2,
      submitLabel: "Save screening rules",
      successMessage: "Screening rules saved.",
      fields: [
        { name: "screening_keywords", label: "Keyword matching", type: "textarea", span: 2, placeholder: "Required skills, certifications…" },
        { name: "knockout_questions", label: "Knockout questions", type: "textarea", span: 2, placeholder: "Right to work? Notice period?" },
      ],
    },
    candidate_pipeline: {
      id: "candidate-pipeline",
      columns: 2,
      submitLabel: "Save pipeline review",
      successMessage: "Pipeline updated.",
      fields: [
        { name: "candidate_rating", label: "Rating (1–5)", type: "number", placeholder: "4" },
        { name: "pipeline_notes", label: "Shortlist notes", type: "textarea", span: 2, rows: 4 },
      ],
    },
    interview_scheduling: {
      id: "interview-scheduling",
      columns: 2,
      submitLabel: "Save interview details",
      successMessage: "Interview details saved.",
      fields: [
        { name: "interview_at", label: "Interview date & time", type: "datetime-local" },
        { name: "interview_video_link", label: "Video interview link", type: "url" },
        { name: "scorecard_notes", label: "Scorecard / feedback", type: "textarea", span: 2, rows: 4 },
      ],
    },
    hiring_decision: {
      id: "hiring-decision",
      columns: 2,
      submitLabel: "Save hiring decision",
      successMessage: "Decision saved.",
      fields: [
        { name: "hiring_decision", label: "Decision", type: "select", optionsKey: "hiring_decisions", defaultValue: "pending" },
        { name: "rejection_reason", label: "Rejection reason (if rejected)", type: "textarea", span: 2, rows: 2 },
      ],
    },
    offer_management: {
      id: "offer-management",
      columns: 2,
      submitLabel: "Save offer details",
      successMessage: "Offer details saved.",
      fields: [
        { name: "offer_status", label: "Offer status", type: "select", optionsKey: "offer_statuses", defaultValue: "draft" },
        { name: "offer_letter_url", label: "Offer letter URL", type: "url", placeholder: "https://..." },
      ],
    },
  };

  const RECRUITMENT_HINTS = {
    vacancy_identified: "Job title is required. Choose sponsored if this role needs a Certificate of Sponsorship.",
    job_description: "Description plus a salary range (from or to) required to complete this step.",
    application_intake: "Candidate name and email required. CV URL is optional but recommended.",
    automated_screening: "Record keywords or knockout questions used for shortlisting.",
    candidate_pipeline: "Add a rating (1–5) or shortlist notes after review.",
    interview_scheduling: "Interview date/time required. Add video link and scorecard notes when available.",
    hiring_decision: "Choose <strong>Proceed to offer</strong> or <strong>Reject</strong>. Reject closes offer steps.",
    offer_management: "Mark offer as sent when the letter goes out. Skip if candidate was rejected.",
  };

  let activeVacancyId = null;
  let selectedVacancyId = null;
  let openVacancyRequest = 0;
  let activeSection = "vacancy_identified";
  let sectionLoaded = false;
  let vacancies = [];
  let viewMode = "pipeline";
  let statusFilter = "open";
  let createFormBound = false;
  let defaultLocation = "";

  function $(id) {
    return document.getElementById(id);
  }

  function pipelineSteps() {
    return window.Admin.formOptions?.recruitment_pipeline || [];
  }

  function departmentLabel(value) {
    const opts = window.Admin.formOptions?.recruitment_departments || [];
    return opts.find((o) => o.value === value)?.label || value || "Not set";
  }

  function isClosedVacancy(row) {
    return CLOSED_STATUSES.has(row.status);
  }

  function filteredVacancies() {
    return vacancies.filter((row) => (statusFilter === "closed" ? isClosedVacancy(row) : !isClosedVacancy(row)));
  }

  function inferLocationFromProfile(profile) {
    const address = String(profile?.registered_address || "").trim();
    if (!address) return "";
    const parts = address.split(",").map((p) => p.trim()).filter(Boolean);
    return parts[parts.length - 1] || address;
  }

  function showListView() {
    $("recruitment-list-view")?.removeAttribute("hidden");
    $("recruitment-detail-view")?.setAttribute("hidden", "");
    activeVacancyId = null;
    if (!window.location.hash.replace("#", "").startsWith("recruitment/")) {
      window.location.hash = "recruitment";
    }
  }

  function showDetailView() {
    $("recruitment-list-view")?.setAttribute("hidden", "");
    $("recruitment-detail-view")?.removeAttribute("hidden");
  }

  function sectionLabel(key) {
    return pipelineSteps().find((s) => s.value === key)?.label || key;
  }

  function normalizePayload(section, payload) {
    const body = { ...payload };
    if (body.department === "other" && body.department_other) {
      body.department = body.department_other;
    }
    delete body.department_other;
    ["salary_range_min", "salary_range_max", "candidate_rating"].forEach((field) => {
      if (body[field] !== undefined && body[field] !== "") body[field] = Number(body[field]);
      else if (body[field] === "") body[field] = null;
    });
    if (body.interview_at) body.interview_at = new Date(body.interview_at).toISOString();
    Object.keys(body).forEach((key) => {
      if (body[key] === "") body[key] = null;
    });
    return body;
  }

  function renderGlobalStepper() {
    const host = $("recruitment-pipeline-stepper");
    if (!host) return;
    const steps = pipelineSteps();
    host.innerHTML = steps
      .map((step, index) => {
        const short = PIPELINE_SHORT[step.value] || step.label;
        return `<div class="recruitment-stepper-item">
          <span class="recruitment-stepper-dot">${index + 1}</span>
          <span class="recruitment-stepper-label">${escapeHtml(short)}</span>
        </div>${index < steps.length - 1 ? '<span class="recruitment-stepper-line" aria-hidden="true"></span>' : ""}`;
      })
      .join("");
  }

  function progressSegments(completedSteps, totalSteps = 10) {
    const done = Math.min(completedSteps || 0, totalSteps);
    return Array.from({ length: totalSteps }, (_, i) =>
      `<span class="recruitment-progress-seg${i < done ? " recruitment-progress-seg--done" : ""}"></span>`
    ).join("");
  }

  function workerBadge(row) {
    if (row.worker_type === "sponsored") {
      return `<span class="recruitment-badge recruitment-badge--sponsored">Sponsored</span>`;
    }
    return `<span class="recruitment-badge">Standard</span>`;
  }

  function renderPipelineCards() {
    const host = $("recruitment-pipeline-cards");
    if (!host) return;
    const rows = filteredVacancies();
    $("recruitment-open-count").textContent =
      statusFilter === "open" ? `${rows.length} active` : `${rows.length} closed`;

    if (!rows.length) {
      host.innerHTML = `<div class="recruitment-empty card hr-workspace">
        <div class="hr-workspace-body">
          <p class="muted">${statusFilter === "open"
            ? "No open roles yet. Click <strong>+ New vacancy</strong> to start the recruitment pipeline."
            : "No closed or filled roles yet."}</p>
        </div>
      </div>`;
      return;
    }

    host.innerHTML = rows
      .map((row) => {
        const selected = selectedVacancyId === row.id ? " recruitment-vacancy-card--selected" : "";
        const step = row.current_step || 1;
        return `<article class="recruitment-vacancy-card${selected}" data-vacancy-id="${row.id}">
          <div class="recruitment-vacancy-card__head">
            <div>
              <h4>${escapeHtml(row.job_title)}</h4>
              <p class="muted">${escapeHtml(row.reference || "")} · ${escapeHtml(departmentLabel(row.department))} · ${escapeHtml(row.location || "Not set")}</p>
            </div>
            ${workerBadge(row)}
          </div>
          <div class="recruitment-vacancy-card__progress">${progressSegments(row.completed_steps, row.total_steps || 10)}</div>
          <div class="recruitment-vacancy-card__meta">
            <span class="recruitment-step-badge">Step ${escapeHtml(step)}</span>
            <span class="muted">${escapeHtml(row.candidate_count || 0)} candidates · ${escapeHtml(row.shortlisted_count || 0)} shortlisted</span>
            <button type="button" class="btn ghost recruitment-card-open" data-open-vacancy="${row.id}">Open →</button>
          </div>
        </article>`;
      })
      .join("");

    host.querySelectorAll(".recruitment-vacancy-card").forEach((card) => {
      card.addEventListener("click", (event) => {
        if (event.target.closest(".recruitment-card-open")) return;
        selectVacancy(Number(card.dataset.vacancyId));
      });
    });
    host.querySelectorAll("[data-open-vacancy]").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        openVacancy(Number(btn.dataset.openVacancy));
      });
    });
  }

  async function renderSidePanel(vacancyId) {
    const empty = $("recruitment-side-panel-empty");
    const content = $("recruitment-side-panel-content");
    if (!content) return;
    if (!vacancyId) {
      empty?.removeAttribute("hidden");
      content.hidden = true;
      return;
    }
    empty?.setAttribute("hidden", "");
    content.hidden = false;
    content.innerHTML = `<p class="muted">Loading pipeline…</p>`;
    try {
      const res = await apiFetch(`/admin/recruitment/vacancies/${vacancyId}/workspace`);
      const workspace = await res.json();
      if (!res.ok) throw new Error(workspace.detail || "Load failed");
      const vacancy = workspace.vacancy || {};
      const nextStep = workspace.current_step || 1;
      const nextSection = workspace.next_section;
      content.innerHTML = `
        <div class="recruitment-side-panel__head">
          <h3>${escapeHtml(vacancy.job_title || "Vacancy")}</h3>
          <p class="muted">${escapeHtml(vacancy.reference || "")} · ${workerBadge(vacancy)}</p>
          <p class="muted">${escapeHtml(departmentLabel(vacancy.department))} · ${escapeHtml(vacancy.location || "Not set")}</p>
          <p class="muted">Created ${escapeHtml((vacancy.created_at || "").slice(0, 10) || "Not set")} · ${escapeHtml(workspace.candidate_count || 0)} candidates · ${escapeHtml(workspace.shortlisted_count || 0)} shortlisted</p>
        </div>
        <ol class="recruitment-side-steps">
          ${(workspace.sections || [])
            .map((section) => {
              const state = section.complete ? "done" : section.key === nextSection ? "current" : "todo";
              return `<li class="recruitment-side-step recruitment-side-step--${state}">
                <span class="recruitment-side-step__marker">${section.complete ? "✓" : section.step}</span>
                <span>
                  <strong>${escapeHtml(section.label)}</strong>
                  ${state === "current" ? '<span class="recruitment-side-step__tag">Current</span>' : ""}
                </span>
              </li>`;
            })
            .join("")}
        </ol>
        <div class="recruitment-side-panel__foot">
          <button type="button" class="btn ghost" data-close-vacancy="${vacancyId}">Close role</button>
          ${nextSection
            ? `<button type="button" class="btn" data-progress-vacancy="${vacancyId}" data-progress-section="${escapeHtml(nextSection)}">→ Progress to step ${escapeHtml(nextStep)}</button>`
            : `<button type="button" class="btn" data-open-vacancy-panel="${vacancyId}">View pipeline</button>`}
        </div>`;
      content.querySelector("[data-close-vacancy]")?.addEventListener("click", () => closeVacancy(vacancyId));
      content.querySelector("[data-progress-vacancy]")?.addEventListener("click", (event) => {
        const btn = event.currentTarget;
        openVacancy(Number(btn.dataset.progressVacancy), btn.dataset.progressSection);
      });
      content.querySelector("[data-open-vacancy-panel]")?.addEventListener("click", () => {
        openVacancy(vacancyId);
      });
    } catch (error) {
      content.innerHTML = `<p class="muted">${escapeHtml(error.message || "Could not load pipeline.")}</p>`;
    }
  }

  async function selectVacancy(vacancyId) {
    selectedVacancyId = vacancyId;
    renderPipelineCards();
    await renderSidePanel(vacancyId);
  }

  async function closeVacancy(vacancyId) {
    if (!window.confirm("Close this vacancy? It will move to Closed roles.")) return;
    const res = await apiFetch(`/admin/recruitment/vacancies/${vacancyId}/close`, { method: "POST" });
    if (!res.ok) {
      const data = await res.json();
      alert(data.detail || "Could not close vacancy");
      return;
    }
    selectedVacancyId = null;
    await refreshVacancies();
    renderSidePanel(null);
  }

  function renderProgress(workspace) {
    const pct = workspace.completion_pct || 0;
    $("recruitment-progress-fill").style.width = `${pct}%`;
    $("recruitment-progress-label").textContent = `Pipeline ${pct}% · next: ${sectionLabel(workspace.next_section || "Complete")}`;
  }

  function lifecycleAccordionHost() {
    return $("recruitment-lifecycle-accordion");
  }

  function renderLifecycleAccordion(workspace) {
    const accordion = lifecycleAccordionHost();
    if (!accordion) return;

    accordion.innerHTML = (workspace.sections || [])
      .map((section) => {
        const isOpen = section.key === activeSection;
        const state = section.complete ? "complete" : "pending";
        const branch = section.branch ? `<span class="lifecycle-tag">${escapeHtml(section.branch)}</span>` : "";
        const stepLabel = section.complete && !isOpen ? "✓" : section.step;
        return `<section class="lifecycle-accordion-item lifecycle-accordion-item--${state}${isOpen ? " is-open" : ""}" data-section="${escapeHtml(section.key)}">
          <button type="button" class="lifecycle-accordion-header" data-section="${escapeHtml(section.key)}" aria-expanded="${isOpen}">
            <span class="lifecycle-accordion-num">${stepLabel}</span>
            <span class="lifecycle-accordion-copy">
              <strong>${escapeHtml(section.label)}</strong>
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
        window.location.hash = `recruitment/${activeVacancyId}/${activeSection}`;
        renderLifecycleAccordion(workspace);
      });
    });

    const contentHost = accordion.querySelector(`[data-section-content="${activeSection}"]`);
    if (contentHost) renderSectionContent(workspace, activeSection, contentHost);
  }

  function renderPostingPanel(workspace, container) {
    const vacancy = workspace.vacancy || {};
    container.innerHTML = `
      <div class="employee-section-intro">
        <h4>Multi-channel posting</h4>
        <span class="lifecycle-tag">Indeed, LinkedIn, Reed, Glassdoor</span>
        <p class="muted">Post this vacancy on job boards and link advert records for RLMT evidence.</p>
      </div>
      <div id="recruitment-advert-form"></div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Platform</th><th>Posted</th><th>Link</th></tr></thead>
          <tbody id="recruitment-adverts-body"></tbody>
        </table>
      </div>`;

    mountEditForm(container.querySelector("#recruitment-advert-form"), {
      id: "recruitment-advert",
      columns: 2,
      submitLabel: "Add advert record",
      successMessage: "Advert posted.",
      fields: [
        { name: "platform", label: "Platform", type: "select", optionsKey: "recruitment_posting_platforms", required: true },
        { name: "posted_date", label: "Posted date", type: "date", required: true },
        { name: "advert_url", label: "Advert URL", type: "url", required: true, span: 2 },
        { name: "job_title", label: "Job title on advert", type: "text", defaultValue: vacancy.job_title },
      ],
    }, {
      values: { job_title: vacancy.job_title, posted_date: new Date().toISOString().slice(0, 10) },
      onSubmit: async (payload) => {
        const res = await apiFetch("/compliance/sponsor-licence/advertisement-records", {
          method: "POST",
          body: JSON.stringify({
            job_title: payload.job_title || vacancy.job_title,
            platform: payload.platform,
            advert_url: payload.advert_url,
            posted_date: payload.posted_date,
            vacancy_id: activeVacancyId,
            is_sponsored_vacancy: vacancy.worker_type === "sponsored",
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Save failed");
        await openVacancy(activeVacancyId, "multi_channel_posting");
      },
    });

    renderTableBody(container.querySelector("#recruitment-adverts-body"), {
      emptyMessage: "No adverts linked yet. Add your first posting above.",
      columns: [
        { key: "platform", render: (row) => escapeHtml(row.platform) },
        { key: "posted_date", render: (row) => escapeHtml(row.posted_date || "Not set") },
        {
          key: "url",
          render: (row) =>
            row.advert_url ? `<a href="${escapeHtml(row.advert_url)}" target="_blank" rel="noopener">Open</a>` : "Not set",
        },
      ],
      rows: workspace.adverts || [],
    });
  }

  function renderOfferAcceptedPanel(workspace, container) {
    const vacancy = workspace.vacancy || {};
    if (vacancy.employee_id) {
      container.innerHTML = `
        <div class="employee-section-intro">
          <h4>Offer accepted: onboarding started</h4>
          <span class="lifecycle-tag">Recruitment analytics · time-to-hire</span>
          <p class="muted">This candidate is now an employee. Continue the employee lifecycle from on-boarding.</p>
          <p class="link-row"><a class="btn" href="#employees/${vacancy.employee_id}/onboarding">Continue onboarding</a></p>
        </div>`;
      return;
    }

    container.innerHTML = `
      <div class="employee-section-intro">
        <h4>Offer accepted</h4>
        <p class="muted">Confirm acceptance to create the employee record and trigger the onboarding workflow.</p>
        <p class="link-row"><button type="button" class="btn" id="recruitment-accept-offer-btn">Accept offer &amp; start onboarding</button></p>
        <p class="edit-form-status muted" id="recruitment-accept-status"></p>
      </div>`;

    container.querySelector("#recruitment-accept-offer-btn")?.addEventListener("click", async () => {
      const status = $("recruitment-accept-status");
      if (status) status.textContent = "Creating employee record…";
      try {
        const res = await apiFetch(`/admin/recruitment/vacancies/${activeVacancyId}/accept-offer`, { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Could not accept offer");
        window.dispatchEvent(new CustomEvent("admin:features-refresh"));
        if (data.onboarding_url) window.location.hash = data.onboarding_url;
        renderOfferAcceptedPanel(data, container);
      } catch (error) {
        if (status) status.textContent = error.message || "Failed";
      }
    });
  }

  function renderSectionContent(workspace, sectionKey, container) {
    if (!container) return;
    if (sectionKey === "multi_channel_posting") {
      renderPostingPanel(workspace, container);
      return;
    }
    if (sectionKey === "offer_accepted") {
      renderOfferAcceptedPanel(workspace, container);
      return;
    }

    const schema = SECTION_SCHEMAS[sectionKey];
    const section = (workspace.sections || []).find((s) => s.key === sectionKey);
    if (!schema || !section) {
      container.innerHTML = `<p class="muted">This step is not available.</p>`;
      return;
    }

    container.innerHTML = `
      <div class="employee-section-intro">
        <h4>${escapeHtml(section.label)}</h4>
        <p class="muted">${escapeHtml(section.description || "")}</p>
        ${section.branch ? `<span class="lifecycle-tag">${escapeHtml(section.branch)}</span>` : ""}
        ${RECRUITMENT_HINTS[sectionKey] ? `<p class="employee-section-hint">${RECRUITMENT_HINTS[sectionKey]}</p>` : ""}
      </div>
      <div id="recruitment-section-form"></div>`;

    mountEditForm(container.querySelector("#recruitment-section-form"), schema, {
      values: section.data || {},
      onSubmit: async (payload) => {
        const res = await apiFetch(`/admin/recruitment/vacancies/${activeVacancyId}/sections/${sectionKey}`, {
          method: "PATCH",
          body: JSON.stringify(normalizePayload(sectionKey, payload)),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Save failed");
        renderWorkspace(data);
        const next = data.next_section;
        if (next && next !== sectionKey) {
          activeSection = next;
          window.location.hash = `recruitment/${activeVacancyId}/${next}`;
          renderLifecycleAccordion(data);
        }
        await refreshVacancies();
        if (selectedVacancyId === activeVacancyId) await renderSidePanel(selectedVacancyId);
      },
    });
  }

  function renderWorkspace(workspace) {
    const vacancy = workspace.vacancy || {};
    $("recruitment-workspace-title").textContent = vacancy.job_title || "Vacancy";
    $("recruitment-workspace-subtitle").textContent = [vacancy.reference, departmentLabel(vacancy.department), vacancy.location]
      .filter(Boolean)
      .join(" · ");
    renderProgress(workspace);
    const keys = (workspace.sections || []).map((s) => s.key);
    if (!keys.includes(activeSection)) activeSection = workspace.next_section || "vacancy_identified";
    renderLifecycleAccordion(workspace);
  }

  async function openVacancy(vacancyId, section = null) {
    const requestId = ++openVacancyRequest;
    const desired = section ? `recruitment/${vacancyId}/${section}` : `recruitment/${vacancyId}`;
    if (window.location.hash.replace("#", "") !== desired) window.location.hash = desired;
    activeVacancyId = vacancyId;
    selectedVacancyId = vacancyId;
    showDetailView();
    const accordion = lifecycleAccordionHost();
    if (accordion) accordion.innerHTML = `<p class="muted lifecycle-accordion-content">Loading recruitment pipeline…</p>`;
    const res = await apiFetch(`/admin/recruitment/vacancies/${vacancyId}/workspace`);
    if (requestId !== openVacancyRequest) return;
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Could not load vacancy");
      showListView();
      return;
    }
    activeSection = section || data.next_section || "vacancy_identified";
    renderWorkspace(data);
  }

  async function refreshVacancies() {
    try {
      const res = await apiFetch("/admin/recruitment/vacancies");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      vacancies = data.items || [];
      renderGlobalStepper();
      renderPipelineCards();
      renderListTable();
    } catch {
      vacancies = [];
      $("recruitment-pipeline-cards").innerHTML = `<p class="muted">Could not load vacancies.</p>`;
    }
  }

  function renderListTable() {
    const tbody = $("recruitment-table-body");
    if (!tbody) return;
    const rows = filteredVacancies();
    renderTableBody(tbody, {
      emptyMessage:
        statusFilter === "open"
          ? "No open roles yet. Click + New vacancy to start the recruitment pipeline."
          : "No closed or filled roles yet.",
      columns: [
        {
          key: "title",
          render: (row) =>
            `<strong>${escapeHtml(row.job_title)}</strong><div class="muted">${escapeHtml(row.reference || "")}</div>`,
        },
        { key: "dept", render: (row) => escapeHtml(departmentLabel(row.department)) },
        { key: "status", render: (row) => escapeHtml(row.status || "open") },
        {
          key: "progress",
          render: (row) =>
            `<span class="recruitment-step-badge">Step ${escapeHtml(row.current_step || 1)}</span> · ${escapeHtml(row.completion_pct ?? 0)}%`,
        },
        {
          key: "candidates",
          render: (row) =>
            `${escapeHtml(row.candidate_count || 0)} candidates · ${escapeHtml(row.shortlisted_count || 0)} shortlisted`,
        },
        {
          key: "actions",
          render: (row) =>
            `<button type="button" class="btn ghost" data-open-vacancy="${row.id}">Open pipeline →</button>`,
        },
      ],
      rows,
    });
    tbody.querySelectorAll("[data-open-vacancy]").forEach((btn) => {
      btn.addEventListener("click", () => openVacancy(Number(btn.dataset.openVacancy)));
    });
  }

  function toggleCreatePanel(show) {
    const panel = $("recruitment-create-panel");
    if (!panel) return;
    if (show) panel.removeAttribute("hidden");
    else panel.setAttribute("hidden", "");
  }

  function bindRlmtNotice(form) {
    const notice = $("recruitment-rlmt-notice");
    const workerField = form?.querySelector('[name="worker_type"]');
    const deptField = form?.querySelector('[name="department"]');
    const otherWrap = form?.querySelector('[name="department_other"]')?.closest(".edit-field");
    const sync = () => {
      if (notice) notice.hidden = workerField?.value !== "sponsored";
      if (otherWrap) otherWrap.hidden = deptField?.value !== "other";
    };
    workerField?.addEventListener("change", sync);
    deptField?.addEventListener("change", sync);
    sync();
  }

  async function mountQuickAdd() {
    if (createFormBound) return;
    const host = $("recruitment-quick-add-form");
    if (!host) return;

    let profile = {};
    try {
      const res = await apiFetch("/admin/tenant-profile");
      if (res.ok) profile = await res.json();
    } catch {
      /* optional */
    }
    defaultLocation = inferLocationFromProfile(profile);

    mountEditForm(host, SECTION_SCHEMAS.vacancy_identified, {
      values: { location: defaultLocation },
      onSubmit: async (payload) => {
        const body = normalizePayload("vacancy_identified", payload);
        if (!body.reference) delete body.reference;
        const res = await apiFetch("/admin/recruitment/vacancies", {
          method: "POST",
          body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Create failed");
        toggleCreatePanel(false);
        await refreshVacancies();
        await selectVacancy(data.id);
        await openVacancy(data.id, "job_description");
      },
    });

    const form = host.querySelector("form");
    bindRlmtNotice(form);
    const otherWrap = form?.querySelector('[name="department_other"]')?.closest(".edit-field");
    if (otherWrap) otherWrap.hidden = true;
    createFormBound = true;
  }

  function bindToolbar() {
    document.querySelectorAll("[data-recruitment-view]").forEach((btn) => {
      btn.addEventListener("click", () => {
        viewMode = btn.dataset.recruitmentView;
        document.querySelectorAll("[data-recruitment-view]").forEach((el) => {
          const active = el.dataset.recruitmentView === viewMode;
          el.classList.toggle("is-active", active);
          el.setAttribute("aria-selected", active ? "true" : "false");
        });
        $("recruitment-pipeline-cards").hidden = viewMode !== "pipeline";
        $("recruitment-list-table-wrap").hidden = viewMode !== "list";
      });
    });

    $("recruitment-new-vacancy-btn")?.addEventListener("click", () => {
      toggleCreatePanel(true);
      $("recruitment-create-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    $("recruitment-closed-tab-btn")?.addEventListener("click", () => {
      statusFilter = statusFilter === "closed" ? "open" : "closed";
      $("recruitment-closed-tab-btn").classList.toggle("is-active", statusFilter === "closed");
      refreshVacancies().then(() => renderSidePanel(selectedVacancyId));
    });
  }

  async function initRecruitment() {
    if (sectionLoaded) return;
    sectionLoaded = true;
    await loadFormOptions();
    bindToolbar();
    await mountQuickAdd();
    await refreshVacancies();
  }

  $("recruitment-back-btn")?.addEventListener("click", async () => {
    showListView();
    await refreshVacancies();
    if (selectedVacancyId) await renderSidePanel(selectedVacancyId);
  });

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section !== "recruitment") return;
    initRecruitment();
    const match = window.location.hash.replace("#", "").match(/^recruitment\/(\d+)(?:\/([\w_]+))?$/);
    if (match) openVacancy(Number(match[1]), match[2] || null);
    else showListView();
  });

  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "");
    if (hash === "recruitment") {
      if ($("recruitment")?.classList.contains("admin-section--active")) showListView();
      return;
    }
    if (!hash.startsWith("recruitment/")) return;
    const match = hash.match(/^recruitment\/(\d+)(?:\/([\w_]+))?$/);
    if (!match) return;
    const id = Number(match[1]);
    const section = match[2] || null;
    if (id === activeVacancyId && section && section !== activeSection) {
      activeSection = section;
      const accordion = lifecycleAccordionHost();
      if (accordion && !accordion.textContent.includes("Loading")) {
        apiFetch(`/admin/recruitment/vacancies/${id}/workspace`)
          .then((res) => res.json())
          .then((data) => renderLifecycleAccordion(data));
      }
      return;
    }
    if (id !== activeVacancyId) openVacancy(id, section);
  });
})();
