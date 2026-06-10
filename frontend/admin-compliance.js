/** Compliance admin tools — RTW, absence, calendar, audit export, reporting triggers. */
(async function initAdminComplianceTools() {
  const { apiFetch, loadFormOptions, loadEmployees, mountEditForm, renderTableBody, FORM_SCHEMAS, escapeHtml, statusPill, downloadAuthenticated, authHeaders, API_BASE, parseHashBaseSection } = window.Admin;

  let complianceReady = false;
  let ackPanelBound = false;

  function renderSponsorDutyGrid(container, duties) {
    if (!container || !Array.isArray(duties)) return;
    container.innerHTML = duties
      .map(
        (item) => `<article class="sponsor-duty-item">
          <h4>${escapeHtml(item.title)}</h4>
          <p><strong>Your duty:</strong> ${escapeHtml(item.customer_duty)}</p>
          <p class="muted"><strong>ShiftSwift HR:</strong> ${escapeHtml(item.software_role)}</p>
        </article>`
      )
      .join("");
  }

  function applySponsorDutyCopy(data) {
    const toolsNotice = document.getElementById("sponsor-licence-tools-notice");
    if (toolsNotice && data.tools_notice) toolsNotice.textContent = data.tools_notice;

    renderSponsorDutyGrid(document.getElementById("sponsor-licence-duties-list"), data.duties);

    const reminder = document.getElementById("sponsor-duty-reminder");
    const reminderNotice = document.getElementById("sponsor-duty-reminder-notice");
    if (reminderNotice && data.tools_notice) reminderNotice.textContent = data.tools_notice;
    renderSponsorDutyGrid(document.getElementById("sponsor-duty-reminder-list"), data.duties);
    if (reminder && data.acknowledged) reminder.hidden = false;
  }

  async function ensureSponsorLicenceAcknowledged() {
    const panel = document.getElementById("sponsor-licence-ack-panel");
    const content = document.getElementById("compliance-tools-content");
    if (!panel || !content) return true;

    try {
      const res = await apiFetch("/compliance/sponsor-licence/acknowledgement");
      if (res.status === 403) {
        panel.hidden = true;
        content.hidden = false;
        return true;
      }
      if (!res.ok) return false;
      const data = await res.json();
      applySponsorDutyCopy(data);
      const ackText = document.getElementById("sponsor-licence-ack-text");
      if (ackText && data.ack_text) ackText.textContent = data.ack_text;
      if (data.acknowledged) {
        panel.hidden = true;
        content.hidden = false;
        return true;
      }
      panel.hidden = false;
      content.hidden = true;
      bindAckPanel();
      return false;
    } catch {
      return false;
    }
  }

  function bindAckPanel() {
    if (ackPanelBound) return;
    ackPanelBound = true;
    document.getElementById("sponsor-licence-ack-btn")?.addEventListener("click", async () => {
      const status = document.getElementById("sponsor-licence-ack-status");
      const holds = document.getElementById("sponsor-licence-holds");
      const understand = document.getElementById("sponsor-licence-understand");
      const accept = document.getElementById("sponsor-licence-accept");
      if (!holds?.checked) {
        if (status) status.textContent = "Confirm your organisation holds a UK Sponsor Licence.";
        return;
      }
      if (!understand?.checked) {
        if (status) status.textContent = "Confirm you understand ShiftSwift HR records data — it does not report to the Home Office for you.";
        return;
      }
      if (!accept?.checked) {
        if (status) status.textContent = "Accept sponsor duty terms in the HR Module EULA.";
        return;
      }
      if (status) status.textContent = "Saving…";
      try {
        const res = await apiFetch("/compliance/sponsor-licence/acknowledgement", {
          method: "POST",
          body: JSON.stringify({ holds_sponsor_licence: true, accept_terms: true }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Could not save confirmation");
        if (status) status.textContent = "Confirmed. Loading compliance tools…";
        await initComplianceTools(true);
      } catch (error) {
        if (status) status.textContent = error.message;
      }
    });
  }

  function riskPill(level) {
    const cls = level === "alert" ? "status-critical" : level === "warning" ? "status-warning" : "status-ok";
    const label = level === "alert" ? "Day 9+" : level === "warning" ? "Day 7–8" : "Clear";
    return `<span class="status-pill ${cls}">${escapeHtml(label)}</span>`;
  }

  async function loadAbsenceStreaks() {
    const tbody = document.getElementById("absence-streak-body");
    if (!tbody) return;
    try {
      const res = await apiFetch("/compliance/sponsor-licence/absence-streaks");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      renderTableBody(tbody, {
        emptyMessage: "No sponsored workers. Mark employees as sponsored to track absences.",
        columns: [
          {
            key: "employee_name",
            render: (r) => `<strong>${escapeHtml(r.employee_name)}</strong><div class="muted">#${escapeHtml(r.employee_id)}</div>`,
          },
          {
            key: "unexcused_streak",
            render: (r) => `<strong>${escapeHtml(r.unexcused_streak)}</strong> working days`,
          },
          { key: "paid_leave_days", render: (r) => escapeHtml(r.paid_leave_days) },
          { key: "unpaid_authorized_days", render: (r) => escapeHtml(r.unpaid_authorized_days) },
          { key: "risk_level", render: (r) => riskPill(r.risk_level) },
        ],
        rows: data.items || [],
      });
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }],
        rows: [],
        emptyMessage: "Could not load absence streaks.",
      });
    }
  }

  async function loadAbsenceDays() {
    const tbody = document.getElementById("absence-days-body");
    if (!tbody) return;
    try {
      const res = await apiFetch("/compliance/sponsor-licence/absence-days?limit=50");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      renderTableBody(tbody, {
        emptyMessage: "No absence days recorded yet.",
        columns: [
          { key: "absence_date", render: (r) => escapeHtml(r.absence_date) },
          {
            key: "employee_name",
            render: (r) => `<strong>${escapeHtml(r.employee_name)}</strong>`,
          },
          { key: "excuse_label", render: (r) => escapeHtml(r.excuse_label) },
          {
            key: "paid",
            render: (r) => (r.paid ? "Paid" : "Unpaid"),
          },
          {
            key: "is_excused",
            render: (r) => (r.is_excused ? "<span class='muted'>No</span>" : `<strong>Yes</strong>`),
          },
          {
            key: "actions",
            render: (r) =>
              `<button type="button" class="btn ghost" data-del-absence="${escapeHtml(r.employee_id)}" data-del-date="${escapeHtml(r.absence_date)}">Remove</button>`,
          },
        ],
        rows: data.items || [],
      });

      tbody.querySelectorAll("[data-del-absence]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          if (!window.confirm("Remove this absence day record?")) return;
          await apiFetch(
            `/compliance/sponsor-licence/absence-days/${btn.dataset.delAbsence}/${btn.dataset.delDate}`,
            { method: "DELETE" }
          );
          await loadAbsenceDays();
          await loadAbsenceStreaks();
          window.dispatchEvent(new CustomEvent("admin:compliance-refresh"));
        });
      });
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }, { key: "f" }],
        rows: [],
        emptyMessage: "Could not load absence days.",
      });
    }
  }

  async function loadWorkingCalendar() {
    const tbody = document.getElementById("working-calendar-body");
    if (!tbody) return;
    const year = new Date().getFullYear();
    try {
      const res = await apiFetch(
        `/compliance/sponsor-licence/working-calendar?from_date=${year}-01-01&to_date=${year}-12-31&non_working_only=true`
      );
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      renderTableBody(tbody, {
        emptyMessage: "No custom calendar entries. All weekdays count as working days.",
        columns: [
          { key: "calendar_date", render: (r) => escapeHtml(r.calendar_date) },
          { key: "label", render: (r) => escapeHtml(r.label) },
          {
            key: "actions",
            render: (r) =>
              `<button type="button" class="btn ghost" data-reset-cal="${escapeHtml(r.calendar_date)}">Mark working day</button>`,
          },
        ],
        rows: data.items || [],
      });

      tbody.querySelectorAll("[data-reset-cal]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          await apiFetch("/compliance/sponsor-licence/working-calendar", {
            method: "PUT",
            body: JSON.stringify({
              entries: [{ calendar_date: btn.dataset.resetCal, is_working_day: true }],
            }),
          });
          loadWorkingCalendar();
        });
      });
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }],
        rows: [],
        emptyMessage: "Could not load working calendar.",
      });
    }
  }

  async function mountAbsenceDayForm() {
    const host = document.getElementById("absence-day-form");
    if (!host || host.dataset.mounted === "true") return;
    await loadFormOptions();
    await loadEmployees();
    mountEditForm(host, FORM_SCHEMAS.absenceDay, {
      onSubmit: async (payload) => {
        const res = await apiFetch("/compliance/sponsor-licence/absence-days", {
          method: "POST",
          body: JSON.stringify({
            employee_id: Number(payload.employee_id),
            absence_date: payload.absence_date,
            excuse_type: payload.excuse_type,
            source: "admin",
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Save failed");
        await loadAbsenceDays();
        await loadAbsenceStreaks();
        window.dispatchEvent(new CustomEvent("admin:compliance-refresh"));
      },
    });
    host.dataset.mounted = "true";
  }

  async function mountWorkingCalendarForm() {
    const host = document.getElementById("working-calendar-form");
    if (!host || host.dataset.mounted === "true") return;
    mountEditForm(host, FORM_SCHEMAS.workingCalendar, {
      onSubmit: async (payload) => {
        const res = await apiFetch("/compliance/sponsor-licence/working-calendar", {
          method: "PUT",
          body: JSON.stringify({
            entries: [
              {
                calendar_date: payload.calendar_date,
                is_working_day: !payload.is_non_working,
              },
            ],
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Save failed");
        await loadWorkingCalendar();
      },
    });
    host.dataset.mounted = "true";
  }

  async function loadReportingTriggers() {
    const tbody = document.getElementById("reporting-triggers-body");
    if (!tbody) return;
    try {
      const res = await apiFetch("/compliance/sponsor-licence/reporting-triggers?status=open");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      renderTableBody(tbody, {
        emptyMessage: "No open Home Office reporting triggers.",
        columns: [
          { key: "trigger_type", render: (r) => `<strong>${escapeHtml(r.trigger_type)}</strong>` },
          { key: "employee_id", render: (r) => escapeHtml(r.employee_id) },
          { key: "description", render: (r) => escapeHtml(r.description) },
          { key: "deadline_date", render: (r) => escapeHtml(r.deadline_date || "Not set") },
          {
            key: "actions",
            render: (r) =>
              `<div class="table-actions">
                <button type="button" class="btn ghost" data-ack="${r.id}">Acknowledge</button>
                <button type="button" class="btn ghost" data-report="${r.id}">Mark reported</button>
              </div>`,
          },
        ],
        rows: data.items || [],
      });

      tbody.querySelectorAll("[data-ack]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          await apiFetch(`/compliance/sponsor-licence/reporting-triggers/${btn.dataset.ack}`, {
            method: "PATCH",
            body: JSON.stringify({ status: "acknowledged" }),
          });
          loadReportingTriggers();
        });
      });
      tbody.querySelectorAll("[data-report]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const ref = window.prompt("Home Office SMS report reference:");
          if (!ref) return;
          await apiFetch(`/compliance/sponsor-licence/reporting-triggers/${btn.dataset.report}`, {
            method: "PATCH",
            body: JSON.stringify({ status: "reported", report_reference: ref }),
          });
          loadReportingTriggers();
        });
      });
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }],
        rows: [],
        emptyMessage: "Could not load reporting triggers.",
      });
    }
  }

  async function mountShareCodeForm() {
    const host = document.getElementById("share-code-form");
    if (!host || host.dataset.mounted === "true") return;
    await loadFormOptions();
    await loadEmployees();
    mountEditForm(host, FORM_SCHEMAS.shareCodeVerify, {
      onSubmit: async (payload) => {
        const res = await apiFetch("/compliance/sponsor-licence/rtw-verify-share-code", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Verification failed");
        const panel = document.getElementById("share-code-result");
        if (panel) {
          panel.hidden = false;
          panel.innerHTML = `<p class="promo-result-message promo-result-message--ok">${escapeHtml(data.message || "Verified")} · RTW: ${escapeHtml(data.rtw_status)} · Expiry: ${escapeHtml(data.expiry_date || "Not set")} · Mode: ${escapeHtml(data.mode)}</p>`;
        }
      },
    });
    host.dataset.mounted = "true";
  }

  function mountRtwUploadForm() {
    const host = document.getElementById("rtw-upload-form");
    if (!host || host.dataset.mounted === "true") return;
    host.innerHTML = `
      <form class="edit-form edit-form--cols-2" id="rtw-upload">
        <label class="edit-field"><span class="edit-label">Employee ID</span><input name="employee_id" type="number" required /></label>
        <label class="edit-field"><span class="edit-label">Check date</span><input name="check_date" type="date" required /></label>
        <label class="edit-field"><span class="edit-label">Method</span><input name="check_method" value="Manual PDF upload" required /></label>
        <label class="edit-field"><span class="edit-label">Outcome</span>
          <select name="outcome" required>
            <option value="pass">Pass</option>
            <option value="time_limited">Time limited</option>
            <option value="fail">Fail</option>
          </select>
        </label>
        <label class="edit-field"><span class="edit-label">Expiry date</span><input name="expiry_date" type="date" /></label>
        <label class="edit-field" data-span="2"><span class="edit-label">RTW evidence PDF</span><input name="evidence_pdf" type="file" accept="application/pdf" required /></label>
        <div class="edit-form-actions" data-span="2">
          <button class="btn" type="submit">Store immutable RTW PDF</button>
          <p class="edit-form-status muted" data-status></p>
        </div>
      </form>`;
    host.querySelector("form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const status = form.querySelector("[data-status]");
      if (status) status.textContent = "Uploading…";
      const fd = new FormData(form);
      fd.set("checker_user_id", localStorage.getItem("username") || "hr");
      try {
        const res = await fetch(`${API_BASE}/compliance/sponsor-licence/rtw-checks`, {
          method: "POST",
          headers: authHeaders(false),
          body: fd,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Upload failed");
        if (status) status.textContent = `Stored check #${data.check_id} · SHA ${data.content_sha256?.slice(0, 12)}…`;
        form.reset();
        window.dispatchEvent(new CustomEvent("admin:compliance-refresh"));
      } catch (error) {
        if (status) status.textContent = error.message;
      }
    });
    host.dataset.mounted = "true";
  }

  async function initComplianceTools(skipAckCheck = false) {
    if (!skipAckCheck) {
      const ready = await ensureSponsorLicenceAcknowledged();
      if (!ready) return;
    }
    mountRtwUploadForm();
    await mountShareCodeForm();
    await mountAbsenceDayForm();
    await mountWorkingCalendarForm();
    await loadAbsenceStreaks();
    await loadAbsenceDays();
    await loadWorkingCalendar();
    await loadReportingTriggers();

    document.getElementById("audit-export-json")?.addEventListener("click", async () => {
      const employeeId = document.getElementById("audit-export-employee")?.value;
      const path = employeeId
        ? `/compliance/sponsor-licence/audit-export?employee_id=${encodeURIComponent(employeeId)}`
        : "/compliance/sponsor-licence/audit-export";
      const res = await apiFetch(path);
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `audit-pack-business-${window.Admin.TENANT_ID}.json`;
      link.click();
      URL.revokeObjectURL(url);
    });

    document.getElementById("audit-export-pdf")?.addEventListener("click", async () => {
      const employeeId = document.getElementById("audit-export-employee")?.value;
      let path = "/compliance/sponsor-licence/audit-export?format=pdf";
      if (employeeId) path += `&employee_id=${encodeURIComponent(employeeId)}`;
      await downloadAuthenticated(path, `audit-pack-business-${window.Admin.TENANT_ID}.pdf`);
    });
  }

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "compliance" && !complianceReady) {
      complianceReady = true;
      initComplianceTools();
    }
  });

  window.addEventListener("admin:compliance-refresh", () => {
    if (typeof loadComplianceDashboard === "function") loadComplianceDashboard();
    loadAbsenceStreaks();
    loadAbsenceDays();
  });

  if (parseHashBaseSection(window.location.hash) === "compliance") {
    complianceReady = true;
    initComplianceTools();
  }
})();
