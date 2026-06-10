/** Admin — weekly rota builder with validated save and publish. */
(async function initAdminRota() {
  const { apiFetch, renderTableBody, escapeHtml, parseHashBaseSection, loadEmployees, statusPill } = window.Admin;

  let sectionReady = false;
  let currentWeekStart = mondayIso(new Date());
  let weekMeta = null;
  let shifts = [];
  let employees = [];
  let dirty = false;

  function mondayIso(date) {
    const d = new Date(date);
    const day = d.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    d.setDate(d.getDate() + diff);
    return d.toISOString().slice(0, 10);
  }

  function addDays(isoDate, days) {
    const d = new Date(`${isoDate}T12:00:00`);
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
  }

  function formatWeekLabel(weekStart) {
    const start = new Date(`${weekStart}T12:00:00`);
    const end = new Date(`${addDays(weekStart, 6)}T12:00:00`);
    const fmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });
    return `${fmt.format(start)} – ${fmt.format(end)} ${start.getFullYear()}`;
  }

  function employeeName(id) {
    const emp = employees.find((e) => Number(e.id) === Number(id));
    if (!emp) return `Employee #${id}`;
    return `${emp.first_name || ""} ${emp.last_name || ""}`.trim() || emp.email || `#${id}`;
  }

  function activeEmployees() {
    return employees.filter((e) => ["active", "onboarding", "suspended"].includes(e.status));
  }

  function setMessage(text, type = "info") {
    const el = document.getElementById("rota-admin-message");
    if (!el) return;
    el.textContent = text || "";
    el.dataset.type = type;
  }

  function markDirty() {
    dirty = true;
    document.getElementById("rota-save-btn")?.classList.add("primary");
  }

  function markClean() {
    dirty = false;
  }

  function updateHeader() {
    const label = document.getElementById("rota-week-label");
    const status = document.getElementById("rota-week-status");
    if (label) label.textContent = formatWeekLabel(currentWeekStart);
    if (status) {
      status.innerHTML = statusPill(weekMeta?.status === "published" ? "published" : "draft");
    }
    const publishBtn = document.getElementById("rota-publish-btn");
    if (publishBtn) publishBtn.disabled = !weekMeta || weekMeta.status === "published" || !shifts.length;
  }

  function renderShiftTable() {
    const tbody = document.getElementById("rota-shifts-body");
    if (!tbody) return;
    renderTableBody(tbody, {
      emptyMessage: "No shifts this week — add one below.",
      columns: [
        {
          key: "shift_date",
          render: (r) => {
            try {
              return new Date(`${r.shift_date}T12:00:00`).toLocaleDateString("en-GB", {
                weekday: "short",
                day: "numeric",
                month: "short",
              });
            } catch {
              return escapeHtml(r.shift_date);
            }
          },
        },
        { key: "employee_name", render: (r) => escapeHtml(r.employee_name || employeeName(r.employee_id)) },
        { key: "start_time", render: (r) => escapeHtml(r.start_time) },
        { key: "end_time", render: (r) => escapeHtml(r.end_time) },
        { key: "role_label", render: (r) => escapeHtml(r.role_label || "—") },
        {
          key: "actions",
          render: (r, index) =>
            `<button type="button" class="btn ghost btn-sm" data-rota-remove="${index}">Remove</button>`,
        },
      ],
      rows: shifts,
    });

    tbody.querySelectorAll("[data-rota-remove]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const index = Number(btn.getAttribute("data-rota-remove"));
        shifts.splice(index, 1);
        markDirty();
        renderShiftTable();
        updateHeader();
      });
    });
  }

  function populateEmployeeSelect() {
    const select = document.getElementById("rota-add-employee");
    if (!select) return;
    const options = activeEmployees()
      .map((e) => `<option value="${e.id}">${escapeHtml(employeeName(e.id))}</option>`)
      .join("");
    select.innerHTML = options || '<option value="">No active employees</option>';
  }

  function populateDaySelect() {
    const select = document.getElementById("rota-add-day");
    if (!select) return;
    select.innerHTML = Array.from({ length: 7 }, (_, i) => {
      const iso = addDays(currentWeekStart, i);
      const label = new Date(`${iso}T12:00:00`).toLocaleDateString("en-GB", {
        weekday: "short",
        day: "numeric",
      });
      return `<option value="${iso}">${label}</option>`;
    }).join("");
  }

  async function loadWeek() {
    setMessage("Loading rota…");
    try {
      const res = await apiFetch(`/admin/rota/weeks/${currentWeekStart}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMessage(data.detail?.message || data.detail || "Could not load rota.", "error");
        return;
      }
      weekMeta = data.week || { status: "draft", version: 1 };
      shifts = (data.shifts || []).map((s) => ({ ...s }));
      markClean();
      updateHeader();
      renderShiftTable();
      populateDaySelect();
      setMessage(
        weekMeta.status === "published"
          ? "Published rota — saving edits will revert to draft."
          : "Add shifts and save. Overlaps for the same employee are blocked."
      );
    } catch (error) {
      setMessage(error.message || "Could not load rota.", "error");
    }
  }

  async function loadEmployeesList() {
    try {
      employees = await loadEmployees();
    } catch {
      employees = [];
    }
    populateEmployeeSelect();
  }

  function addShiftFromForm() {
    const employeeId = document.getElementById("rota-add-employee")?.value;
    const shiftDate = document.getElementById("rota-add-day")?.value;
    const startTime = document.getElementById("rota-add-start")?.value;
    const endTime = document.getElementById("rota-add-end")?.value;
    const roleLabel = document.getElementById("rota-add-role")?.value?.trim() || "";

    if (!employeeId || !shiftDate || !startTime || !endTime) {
      setMessage("Employee, day, start, and end are required.", "error");
      return;
    }

    shifts.push({
      employee_id: Number(employeeId),
      employee_name: employeeName(employeeId),
      shift_date: shiftDate,
      start_time: startTime.slice(0, 5),
      end_time: endTime.slice(0, 5),
      role_label: roleLabel,
      notes: "",
    });
    shifts.sort((a, b) =>
      `${a.shift_date}${a.start_time}`.localeCompare(`${b.shift_date}${b.start_time}`)
    );
    markDirty();
    renderShiftTable();
    updateHeader();
    setMessage("Shift added — click Save rota to persist.");
  }

  async function saveRota() {
    const btn = document.getElementById("rota-save-btn");
    if (btn) btn.disabled = true;
    setMessage("Saving…");
    try {
      const res = await apiFetch(`/admin/rota/weeks/${currentWeekStart}`, {
        method: "PUT",
        body: JSON.stringify({
          shifts: shifts.map((s) => ({
            employee_id: s.employee_id,
            shift_date: s.shift_date,
            start_time: s.start_time,
            end_time: s.end_time,
            role_label: s.role_label || "",
            notes: s.notes || "",
          })),
          expected_version: weekMeta?.version ?? null,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 409) {
        setMessage(
          (data.detail?.message || "Someone else updated this rota.") + " Reloading…",
          "error"
        );
        await loadWeek();
        return;
      }
      if (!res.ok) {
        const detail = data.detail;
        const msg =
          typeof detail === "object"
            ? detail.message || JSON.stringify(detail)
            : detail || "Save failed.";
        setMessage(msg, "error");
        return;
      }
      weekMeta = data.week;
      shifts = data.shifts || [];
      markClean();
      updateHeader();
      renderShiftTable();
      setMessage(data.message || "Rota saved.");
    } catch (error) {
      setMessage(error.message || "Save failed.", "error");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function publishRota() {
    if (!weekMeta?.version) {
      setMessage("Save the rota before publishing.", "error");
      return;
    }
    const btn = document.getElementById("rota-publish-btn");
    if (btn) btn.disabled = true;
    setMessage("Publishing…");
    try {
      const res = await apiFetch(`/admin/rota/weeks/${currentWeekStart}/publish`, {
        method: "POST",
        body: JSON.stringify({ expected_version: weekMeta.version }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 409) {
        setMessage((data.detail?.message || "Version conflict.") + " Reloading…", "error");
        await loadWeek();
        return;
      }
      if (!res.ok) {
        setMessage(data.detail?.message || data.detail || "Publish failed.", "error");
        return;
      }
      weekMeta = data.week;
      shifts = data.shifts || [];
      updateHeader();
      setMessage(data.message || "Rota published.");
    } catch (error) {
      setMessage(error.message || "Publish failed.", "error");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function changeWeek(delta) {
    if (dirty && !window.confirm("You have unsaved shifts. Change week anyway?")) return;
    currentWeekStart = addDays(currentWeekStart, delta * 7);
    loadWeek();
  }

  async function initSection() {
    document.getElementById("rota-prev-week")?.addEventListener("click", () => changeWeek(-1));
    document.getElementById("rota-next-week")?.addEventListener("click", () => changeWeek(1));
    document.getElementById("rota-this-week")?.addEventListener("click", () => {
      if (dirty && !window.confirm("You have unsaved shifts. Jump to this week anyway?")) return;
      currentWeekStart = mondayIso(new Date());
      loadWeek();
    });
    document.getElementById("rota-add-btn")?.addEventListener("click", addShiftFromForm);
    document.getElementById("rota-save-btn")?.addEventListener("click", saveRota);
    document.getElementById("rota-publish-btn")?.addEventListener("click", publishRota);
    document.getElementById("rota-reload-btn")?.addEventListener("click", () => {
      if (dirty && !window.confirm("Discard unsaved changes and reload?")) return;
      loadWeek();
    });

    await loadEmployeesList();
    await loadWeek();
  }

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "rota" && !sectionReady) {
      sectionReady = true;
      initSection();
    }
  });

  if (parseHashBaseSection(window.location.hash) === "rota") {
    sectionReady = true;
    initSection();
  }
})();
