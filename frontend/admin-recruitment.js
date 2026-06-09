/** Recruitment pipeline — 10-step vacancy flow through offer accepted → onboarding. */
(function () {
  const { apiFetch, escapeHtml, mountEditForm, renderTableBody, loadFormOptions } = window.Admin;

  const SECTION_SCHEMAS = {
    vacancy_identified: {
      id: "vacancy-identified",
      columns: 2,
      submitLabel: "Save vacancy",
      successMessage: "Vacancy saved.",
      fields: [
        { name: "job_title", label: "Job title", type: "text", required: true },
        { name: "reference", label: "Vacancy reference", type: "text", placeholder: "VAC-2026-001" },
        { name: "department", label: "Department", type: "text" },
        { name: "location", label: "Location", type: "text" },
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
  let openVacancyRequest = 0;
  let activeSection = "vacancy_identified";
  let sectionLoaded = false;

  function $(id) {
    return document.getElementById(id);
  }

  function showListView() {
    $("recruitment-list-view")?.removeAttribute("hidden");
    $("recruitment-detail-view")?.setAttribute("hidden", "");
    activeVacancyId = null;
    window.location.hash = "recruitment";
  }

  function showDetailView() {
    $("recruitment-list-view")?.setAttribute("hidden", "");
    $("recruitment-detail-view")?.removeAttribute("hidden");
  }

  function sectionLabel(key) {
    return (window.Admin.formOptions?.recruitment_pipeline || []).find((s) => s.value === key)?.label || key;
  }

  function normalizePayload(section, payload) {
    const body = { ...payload };
    ["salary_range_min", "salary_range_max", "candidate_rating"].forEach((field) => {
      if (body[field] !== undefined && body[field] !== "") body[field] = Number(body[field]);
      else if (body[field] === "") body[field] = null;
    });
    if (body.interview_at) {
      body.interview_at = new Date(body.interview_at).toISOString();
    }
    Object.keys(body).forEach((key) => {
      if (body[key] === "") body[key] = null;
    });
    return body;
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
        const branch = section.branch
          ? `<span class="lifecycle-tag">${escapeHtml(section.branch)}</span>`
          : "";
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
    if (contentHost) {
      renderSectionContent(workspace, activeSection, contentHost);
    }
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
          <p class="link-row">
            <a class="btn" href="#employees/${vacancy.employee_id}/onboarding">Continue onboarding</a>
          </p>
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
        if (data.onboarding_url) {
          window.location.hash = data.onboarding_url;
        }
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
      },
    });
  }

  function renderWorkspace(workspace) {
    const vacancy = workspace.vacancy || {};
    $("recruitment-workspace-title").textContent = vacancy.job_title || "Vacancy";
    $("recruitment-workspace-subtitle").textContent = [vacancy.reference, vacancy.department, vacancy.location]
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
    if (window.location.hash.replace("#", "") !== desired) {
      window.location.hash = desired;
    }
    activeVacancyId = vacancyId;
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

  async function refreshVacancyTable() {
    const tbody = $("recruitment-table-body");
    if (!tbody) return;
    try {
      const res = await apiFetch("/admin/recruitment/vacancies");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      renderTableBody(tbody, {
        emptyMessage: "No vacancies yet. Create your first role above.",
        columns: [
          { key: "title", render: (row) => `<strong>${escapeHtml(row.job_title)}</strong>` },
          { key: "dept", render: (row) => escapeHtml(row.department || "Not set") },
          { key: "status", render: (row) => escapeHtml(row.status || "open") },
          {
            key: "progress",
            render: (row) =>
              `<span class="employee-profile-pill">${escapeHtml(String(row.completion_pct ?? 0))}%</span>`,
          },
          {
            key: "actions",
            render: (row) =>
              `<button type="button" class="btn" data-open-vacancy="${row.id}">Open pipeline</button>`,
          },
        ],
        rows: data.items || [],
      });
      tbody.querySelectorAll("[data-open-vacancy]").forEach((btn) => {
        btn.addEventListener("click", () => openVacancy(Number(btn.dataset.openVacancy)));
      });
    } catch {
      tbody.innerHTML = `<tr><td colspan="5" class="muted">Could not load vacancies.</td></tr>`;
    }
  }

  function mountQuickAdd() {
    mountEditForm($("recruitment-quick-add-form"), {
      id: "recruitment-quick-add",
      columns: 2,
      submitLabel: "Create vacancy",
      successMessage: "Vacancy created.",
      fields: SECTION_SCHEMAS.vacancy_identified.fields,
    }, {
      onSubmit: async (payload) => {
        const res = await apiFetch("/admin/recruitment/vacancies", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Create failed");
        await refreshVacancyTable();
        await openVacancy(data.id, "job_description");
      },
    });
  }

  async function initRecruitment() {
    if (sectionLoaded) return;
    sectionLoaded = true;
    await loadFormOptions();
    mountQuickAdd();
    await refreshVacancyTable();
  }

  $("recruitment-back-btn")?.addEventListener("click", showListView);

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
      if (document.getElementById("recruitment")?.classList.contains("admin-section--active")) {
        showListView();
      }
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
          .then((data) => {
            renderLifecycleAccordion(data);
          });
      }
      return;
    }
    if (id !== activeVacancyId) {
      openVacancy(id, section);
    }
  });
})();
