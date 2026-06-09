/** Offboarding workflows admin UI. */
(async function initAdminOffboarding() {
  const { apiFetch, loadEmployees, renderTableBody, escapeHtml, statusPill, parseHashBaseSection } = window.Admin;

  async function loadWorkflows() {
    const tbody = document.getElementById("offboarding-body");
    if (!tbody) return;
    try {
      const res = await apiFetch("/offboarding/workflows");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      renderTableBody(tbody, {
        emptyMessage: "No offboarding workflows yet.",
        columns: [
          { key: "id", render: (r) => `<strong>#${escapeHtml(r.id)}</strong>` },
          { key: "employee_id", render: (r) => escapeHtml(r.employee_id) },
          { key: "reason", render: (r) => escapeHtml(r.reason) },
          { key: "status", render: (r) => statusPill(r.status) },
          { key: "acas_appeal_deadline", render: (r) => escapeHtml(r.acas_appeal_deadline || "Not set") },
          {
            key: "cessation",
            render: (r) =>
              r.sponsorship_cessation_required
                ? r.sponsorship_cessation_reference
                  ? escapeHtml(r.sponsorship_cessation_reference)
                  : "<span class='muted'>Required</span>"
                : "Not set",
          },
          {
            key: "actions",
            render: (r) =>
              r.sponsorship_cessation_required && !r.sponsorship_cessation_reference
                ? `<button type="button" class="btn ghost" data-cessation="${r.id}">Report cessation</button>`
                : "",
          },
        ],
        rows: data.items || [],
      });

      tbody.querySelectorAll("[data-cessation]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const ref = window.prompt("Home Office cessation report reference:");
          if (!ref) return;
          const res = await apiFetch(`/offboarding/workflows/${btn.dataset.cessation}/cessation-reported`, {
            method: "POST",
            body: JSON.stringify({ report_reference: ref }),
          });
          if (!res.ok) {
            const err = await res.json();
            alert(err.detail || "Update failed");
            return;
          }
          loadWorkflows();
        });
      });
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }, { key: "f" }, { key: "g" }],
        rows: [],
        emptyMessage: "Could not load offboarding workflows.",
      });
    }
  }

  async function initOffboardingSection() {
    await loadEmployees();
    const startBtn = document.getElementById("offboarding-start-btn");
    startBtn?.addEventListener("click", async () => {
      const employeeId = document.getElementById("offboarding-employee")?.value;
      const reason = document.getElementById("offboarding-reason")?.value?.trim();
      if (!employeeId || !reason) {
        alert("Select employee and enter a reason.");
        return;
      }
      const res = await apiFetch("/offboarding/workflows", {
        method: "POST",
        body: JSON.stringify({ employee_id: Number(employeeId), reason }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || "Could not start workflow");
        return;
      }
      document.getElementById("offboarding-reason").value = "";
      loadWorkflows();
    });

    const select = document.getElementById("offboarding-employee");
    if (select) {
      try {
        const res = await apiFetch("/admin/employees");
        const data = await res.json();
        select.innerHTML = (data.items || [])
          .map(
            (emp) =>
              `<option value="${emp.id}">${escapeHtml(emp.first_name)} ${escapeHtml(emp.last_name)}</option>`
          )
          .join("");
      } catch {
        select.innerHTML = `<option value="">Could not load employees</option>`;
      }
    }

    await loadWorkflows();
  }

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "offboarding" && !sectionReady) {
      sectionReady = true;
      initOffboardingSection();
    }
  });

  if (parseHashBaseSection(window.location.hash) === "offboarding") {
    sectionReady = true;
    initOffboardingSection();
  }
})();
