/** Grievance case management admin UI. */
(async function initAdminGrievance() {
  const { apiFetch, loadFormOptions, loadEmployees, mountEditForm, renderTableBody, FORM_SCHEMAS, escapeHtml, statusPill, parseHashBaseSection } = window.Admin;

  let selectedCaseId = null;
  let sectionReady = false;

  async function loadCases() {
    const tbody = document.getElementById("grievance-cases-body");
    if (!tbody) return;
    try {
      const res = await apiFetch("/grievance/cases");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      renderTableBody(tbody, {
        emptyMessage: "No grievance cases yet.",
        columns: [
          { key: "case_reference", render: (r) => `<strong>${escapeHtml(r.case_reference)}</strong>` },
          { key: "employee_id", render: (r) => escapeHtml(r.employee_id) },
          { key: "allegation_type", render: (r) => escapeHtml(r.allegation_type) },
          { key: "status", render: (r) => statusPill(r.status) },
          { key: "acas_deadline", render: (r) => escapeHtml(r.acas_deadline || "Not set") },
          {
            key: "actions",
            render: (r) =>
              `<div class="table-actions">
                <button type="button" class="btn ghost" data-view-case="${r.id}">View</button>
                <button type="button" class="btn ghost" data-suspend="${r.id}" ${r.status === "closed" ? "disabled" : ""}>Suspend</button>
                <button type="button" class="btn ghost" data-close="${r.id}" ${r.status === "closed" ? "disabled" : ""}>Close</button>
              </div>`,
          },
        ],
        rows: data.items || [],
      });

      tbody.querySelectorAll("[data-view-case]").forEach((btn) => {
        btn.addEventListener("click", () => openCaseDetail(btn.dataset.viewCase));
      });
      tbody.querySelectorAll("[data-suspend]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const reason = window.prompt("Reason for suspension during investigation:");
          if (!reason) return;
          const res = await apiFetch(`/grievance/cases/${btn.dataset.suspend}/suspend-employee`, {
            method: "POST",
            body: JSON.stringify({ reason }),
          });
          if (!res.ok) {
            const err = await res.json();
            alert(err.detail || "Suspend failed");
            return;
          }
          loadCases();
        });
      });
      tbody.querySelectorAll("[data-close]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const outcome = window.prompt("Close outcome (upheld/rejected/withdrawn/dismissal/resignation):");
          if (!outcome) return;
          const res = await apiFetch(`/grievance/cases/${btn.dataset.close}/close`, {
            method: "POST",
            body: JSON.stringify({ close_outcome: outcome }),
          });
          if (!res.ok) {
            const err = await res.json();
            alert(err.detail || "Close failed");
            return;
          }
          loadCases();
        });
      });
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }, { key: "f" }],
        rows: [],
        emptyMessage: "Could not load grievance cases.",
      });
    }
  }

  async function openCaseDetail(caseId) {
    selectedCaseId = caseId;
    const panel = document.getElementById("grievance-case-detail");
    const notesBody = document.getElementById("grievance-notes-body");
    if (!panel) return;
    const res = await apiFetch(`/grievance/cases/${caseId}`);
    const caseData = await res.json();
    if (!res.ok) return;
    panel.hidden = false;
    panel.querySelector("[data-case-ref]").textContent = caseData.case_reference;
    panel.querySelector("[data-case-status]").innerHTML = statusPill(caseData.status);
    panel.querySelector("[data-case-deadline]").textContent = caseData.acas_deadline || "Not set";

    const notesRes = await apiFetch(`/grievance/cases/${caseId}/notes`);
    const notesData = await notesRes.json();
    renderTableBody(notesBody, {
      emptyMessage: "No encrypted notes yet.",
      columns: [
        { key: "note_type", render: (r) => escapeHtml(r.note_type) },
        { key: "created_by", render: (r) => escapeHtml(r.created_by) },
        { key: "created_at", render: (r) => escapeHtml((r.created_at || "").slice(0, 16)) },
        { key: "body", render: (r) => escapeHtml(r.body || "") },
      ],
      rows: notesData.items || [],
    });
    mountNoteForm();
  }

  function mountCaseForm() {
    const host = document.getElementById("grievance-case-form");
    if (!host || host.dataset.mounted === "true") return;
    mountEditForm(host, FORM_SCHEMAS.grievanceCase, {
      onSubmit: async (payload) => {
        const body = {
          ...payload,
          employee_id: Number(payload.employee_id),
          is_anonymous_to_manager: Boolean(payload.is_anonymous_to_manager),
        };
        const res = await apiFetch("/grievance/cases", { method: "POST", body: JSON.stringify(body) });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Could not open case");
        host.querySelector("form")?.reset();
        await loadCases();
        openCaseDetail(data.id);
      },
    });
    host.dataset.mounted = "true";
  }

  function mountNoteForm() {
    const host = document.getElementById("grievance-note-form");
    if (!host || !selectedCaseId) return;
    mountEditForm(host, FORM_SCHEMAS.grievanceNote, {
      onSubmit: async (payload) => {
        const res = await apiFetch(`/grievance/cases/${selectedCaseId}/notes`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Note failed");
        host.querySelector("form")?.reset();
        openCaseDetail(selectedCaseId);
      },
    });
  }

  async function initGrievanceSection() {
    await loadFormOptions();
    await loadEmployees();
    mountCaseForm();
    await loadCases();
  }

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "grievance" && !sectionReady) {
      sectionReady = true;
      initGrievanceSection();
    }
  });

  if (parseHashBaseSection(window.location.hash) === "grievance") {
    sectionReady = true;
    initGrievanceSection();
  }
})();
