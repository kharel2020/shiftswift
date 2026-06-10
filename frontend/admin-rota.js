/** Admin — weekly rota: grid, attendance, copy week, shift requests. */
(async function initAdminRota() {
  const { apiFetch, renderTableBody, escapeHtml, parseHashBaseSection, statusPill } = window.Admin;

  let sectionReady = false;
  let currentWeekStart = mondayIso(new Date());
  let weekMeta = null;
  let shifts = [];
  let attendanceByShiftId = new Map();
  let employees = [];
  let dirty = false;
  let activeView = "grid";
  let dragShiftIndex = null;

  const ATTENDANCE_LABELS = {
    scheduled: "Scheduled",
    awaiting: "Awaiting",
    attended: "Attended",
    late: "Late",
    no_show: "No show",
    missing_clock_out: "No clock-out",
  };

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
  }

  function markClean() {
    dirty = false;
  }

  function updateHeader() {
    document.getElementById("rota-week-label").textContent = formatWeekLabel(currentWeekStart);
    const status = document.getElementById("rota-week-status");
    if (status) status.innerHTML = statusPill(weekMeta?.status === "published" ? "published" : "draft");
    const publishBtn = document.getElementById("rota-publish-btn");
    if (publishBtn) publishBtn.disabled = !weekMeta || weekMeta.status === "published" || !shifts.length;
  }

  function attendanceForShift(shift) {
    const key = shift.id != null ? String(shift.id) : `${shift.employee_id}-${shift.shift_date}-${shift.start_time}`;
    return attendanceByShiftId.get(key);
  }

  function renderAttendanceTable(items) {
    const panel = document.getElementById("rota-attendance-panel");
    const tbody = document.getElementById("rota-attendance-body");
    if (!panel || !tbody) return;
    if (!items?.length) {
      panel.hidden = true;
      return;
    }
    panel.hidden = false;
    renderTableBody(tbody, {
      emptyMessage: "No shifts to compare.",
      columns: [
        {
          key: "shift_date",
          render: (r) =>
            new Date(`${r.shift_date}T12:00:00`).toLocaleDateString("en-GB", {
              weekday: "short",
              day: "numeric",
            }),
        },
        { key: "employee_name", render: (r) => escapeHtml(r.employee_name || "") },
        {
          key: "shift",
          render: (r) => `${escapeHtml(r.start_time)}–${escapeHtml(r.end_time)}`,
        },
        {
          key: "attendance_status",
          render: (r) => statusPill(ATTENDANCE_LABELS[r.attendance_status] || r.attendance_status),
        },
        { key: "attendance_detail", render: (r) => escapeHtml(r.attendance_detail || "") },
      ],
      rows: items,
    });
  }

  function renderShiftTable() {
    const tbody = document.getElementById("rota-shifts-body");
    if (!tbody) return;
    renderTableBody(tbody, {
      emptyMessage: "No shifts this week — add one below or use the grid.",
      columns: [
        {
          key: "shift_date",
          render: (r) =>
            new Date(`${r.shift_date}T12:00:00`).toLocaleDateString("en-GB", {
              weekday: "short",
              day: "numeric",
              month: "short",
            }),
        },
        { key: "employee_name", render: (r) => escapeHtml(r.employee_name || employeeName(r.employee_id)) },
        { key: "start_time", render: (r) => escapeHtml(r.start_time) },
        { key: "end_time", render: (r) => escapeHtml(r.end_time) },
        { key: "role_label", render: (r) => escapeHtml(r.role_label || "—") },
        {
          key: "punch",
          render: (r) => {
            const a = attendanceForShift(r);
            return a ? statusPill(ATTENDANCE_LABELS[a.attendance_status] || a.attendance_status) : "—";
          },
        },
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
        shifts.splice(Number(btn.getAttribute("data-rota-remove")), 1);
        markDirty();
        renderAll();
      });
    });
  }

  function renderGrid() {
    const grid = document.getElementById("rota-grid");
    if (!grid) return;
    const days = Array.from({ length: 7 }, (_, i) => addDays(currentWeekStart, i));
    const dayLabels = days.map((iso) =>
      new Date(`${iso}T12:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric" })
    );
    const staff = activeEmployees();
    if (!staff.length) {
      grid.innerHTML = '<p class="muted">Add active employees before building a rota.</p>';
      return;
    }

    let html = '<div class="rota-grid-table"><div class="rota-grid-row rota-grid-row--head"><div class="rota-grid-cell rota-grid-cell--name">Staff</div>';
    dayLabels.forEach((label) => {
      html += `<div class="rota-grid-cell rota-grid-cell--head">${escapeHtml(label)}</div>`;
    });
    html += "</div>";

    staff.forEach((emp) => {
      html += `<div class="rota-grid-row" data-employee-id="${emp.id}"><div class="rota-grid-cell rota-grid-cell--name">${escapeHtml(employeeName(emp.id))}</div>`;
      days.forEach((iso) => {
        const cellShifts = shifts
          .map((s, index) => ({ s, index }))
          .filter(({ s }) => Number(s.employee_id) === Number(emp.id) && s.shift_date === iso);
        html += `<div class="rota-grid-cell rota-grid-drop" data-employee-id="${emp.id}" data-shift-date="${iso}">`;
        cellShifts.forEach(({ s, index }) => {
          const a = attendanceForShift(s);
          const flag = a?.attendance_status === "no_show" || a?.attendance_status === "late" ? ` rota-shift-chip--${a.attendance_status}` : "";
          html += `<button type="button" class="rota-shift-chip${flag}" draggable="true" data-shift-index="${index}" title="${escapeHtml(s.start_time)}–${escapeHtml(s.end_time)}">${escapeHtml(s.start_time)}–${escapeHtml(s.end_time)}</button>`;
        });
        html += `<button type="button" class="rota-grid-add" data-add-employee="${emp.id}" data-add-date="${iso}" aria-label="Add shift">+</button>`;
        html += "</div>";
      });
      html += "</div>";
    });
    html += "</div>";
    grid.innerHTML = html;

    grid.querySelectorAll(".rota-shift-chip").forEach((chip) => {
      chip.addEventListener("dragstart", (event) => {
        dragShiftIndex = Number(chip.getAttribute("data-shift-index"));
        event.dataTransfer?.setData("text/plain", String(dragShiftIndex));
      });
    });

    grid.querySelectorAll(".rota-grid-drop").forEach((cell) => {
      cell.addEventListener("dragover", (event) => {
        event.preventDefault();
        cell.classList.add("is-drag-over");
      });
      cell.addEventListener("dragleave", () => cell.classList.remove("is-drag-over"));
      cell.addEventListener("drop", (event) => {
        event.preventDefault();
        cell.classList.remove("is-drag-over");
        const index = dragShiftIndex ?? Number(event.dataTransfer?.getData("text/plain"));
        if (Number.isNaN(index) || !shifts[index]) return;
        shifts[index].employee_id = Number(cell.getAttribute("data-employee-id"));
        shifts[index].employee_name = employeeName(shifts[index].employee_id);
        shifts[index].shift_date = cell.getAttribute("data-shift-date");
        markDirty();
        renderAll();
      });
    });

    grid.querySelectorAll(".rota-grid-add").forEach((btn) => {
      btn.addEventListener("click", () => {
        const employeeId = Number(btn.getAttribute("data-add-employee"));
        const shiftDate = btn.getAttribute("data-add-date");
        shifts.push({
          employee_id: employeeId,
          employee_name: employeeName(employeeId),
          shift_date: shiftDate,
          start_time: "09:00",
          end_time: "17:00",
          role_label: "",
          notes: "",
        });
        markDirty();
        renderAll();
        setMessage("Default 09:00–17:00 shift added — save when ready.");
      });
    });
  }

  function renderAll() {
    renderGrid();
    renderShiftTable();
    updateHeader();
  }

  function setView(view) {
    activeView = view;
    document.getElementById("rota-grid-panel").hidden = view !== "grid";
    document.getElementById("rota-list-panel").hidden = view !== "list";
    document.getElementById("rota-view-grid")?.classList.toggle("is-active", view === "grid");
    document.getElementById("rota-view-list")?.classList.toggle("is-active", view === "list");
  }

  async function loadShiftRequests() {
    const tbody = document.getElementById("rota-requests-body");
    if (!tbody) return;
    try {
      const res = await apiFetch("/admin/rota/shift-requests?status=pending");
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error("load failed");
      const rows = data.items || [];
      renderTableBody(tbody, {
        emptyMessage: "No pending cover or swap requests.",
        columns: [
          {
            key: "shift_date",
            render: (r) =>
              `${escapeHtml(r.shift_date || "")} ${escapeHtml(r.start_time || "")}–${escapeHtml(r.end_time || "")}`,
          },
          { key: "requester_name", render: (r) => escapeHtml(r.requester_name) },
          { key: "request_type", render: (r) => escapeHtml(r.request_type) },
          { key: "note", render: (r) => escapeHtml(r.note || "—") },
          {
            key: "actions",
            render: (r) =>
              `<button type="button" class="btn btn-sm" data-approve-request="${r.id}">Approve</button> <button type="button" class="btn ghost btn-sm" data-reject-request="${r.id}">Reject</button>`,
          },
        ],
        rows,
      });
      tbody.querySelectorAll("[data-approve-request]").forEach((btn) => {
        btn.addEventListener("click", () => reviewRequest(Number(btn.getAttribute("data-approve-request")), true));
      });
      tbody.querySelectorAll("[data-reject-request]").forEach((btn) => {
        btn.addEventListener("click", () => reviewRequest(Number(btn.getAttribute("data-reject-request")), false));
      });
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }],
        rows: [],
        emptyMessage: "Could not load shift requests.",
      });
    }
  }

  async function reviewRequest(requestId, approve) {
    try {
      const res = await apiFetch(`/admin/rota/shift-requests/${requestId}/review`, {
        method: "POST",
        body: JSON.stringify({ approve }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMessage(data.detail?.message || data.detail || "Review failed.", "error");
        return;
      }
      setMessage(approve ? "Request approved." : "Request rejected.");
      await Promise.all([loadWeek(), loadShiftRequests()]);
    } catch (error) {
      setMessage(error.message || "Review failed.", "error");
    }
  }

  function populateEmployeeSelect() {
    const select = document.getElementById("rota-add-employee");
    if (!select) return;
    select.innerHTML =
      activeEmployees()
        .map((e) => `<option value="${e.id}">${escapeHtml(employeeName(e.id))}</option>`)
        .join("") || '<option value="">No active employees</option>';
  }

  function populateDaySelect() {
    const select = document.getElementById("rota-add-day");
    if (!select) return;
    select.innerHTML = Array.from({ length: 7 }, (_, i) => {
      const iso = addDays(currentWeekStart, i);
      const label = new Date(`${iso}T12:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric" });
      return `<option value="${iso}">${label}</option>`;
    }).join("");
  }

  async function loadWeek() {
    setMessage("Loading rota…");
    try {
      const res = await apiFetch(`/admin/rota/weeks/${currentWeekStart}?include_attendance=true`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMessage(data.detail?.message || data.detail || "Could not load rota.", "error");
        return;
      }
      weekMeta = data.week || { status: "draft", version: 1 };
      shifts = (data.shifts || []).map((s) => ({ ...s }));
      attendanceByShiftId = new Map();
      (data.attendance?.items || []).forEach((item) => {
        if (item.shift_id != null) attendanceByShiftId.set(String(item.shift_id), item);
      });
      markClean();
      renderAttendanceTable(data.attendance?.items || []);
      renderAll();
      populateDaySelect();
      setMessage(
        weekMeta.status === "published"
          ? "Published — punch vs rota flags update live."
          : "Build the rota, save, then publish so staff see shifts in the Time Clock app."
      );
    } catch (error) {
      setMessage(error.message || "Could not load rota.", "error");
    }
  }

  async function loadEmployeesList() {
    try {
      const res = await apiFetch("/admin/employees");
      if (!res.ok) throw new Error("load failed");
      employees = (await res.json()).items || [];
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
    shifts.sort((a, b) => `${a.shift_date}${a.start_time}`.localeCompare(`${b.shift_date}${b.start_time}`));
    markDirty();
    renderAll();
    setMessage("Shift added — click Save rota.");
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
        setMessage((data.detail?.message || "Version conflict.") + " Reloading…", "error");
        await loadWeek();
        return;
      }
      if (!res.ok) {
        setMessage(data.detail?.message || data.detail || "Save failed.", "error");
        return;
      }
      weekMeta = data.week;
      shifts = data.shifts || [];
      markClean();
      renderAll();
      setMessage(data.message || "Rota saved.");
    } catch (error) {
      setMessage(error.message || "Save failed.", "error");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function copyPreviousWeek() {
    if (!window.confirm("Copy all shifts from last week into this week? Current week must be empty.")) return;
    setMessage("Copying…");
    try {
      const res = await apiFetch(`/admin/rota/weeks/${currentWeekStart}/copy-previous`, {
        method: "POST",
        body: JSON.stringify({ expected_version: weekMeta?.version ?? null }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMessage(data.detail?.message || data.detail || "Copy failed.", "error");
        return;
      }
      weekMeta = data.week;
      shifts = data.shifts || [];
      markClean();
      await loadWeek();
      setMessage(data.message || "Copied from previous week.");
    } catch (error) {
      setMessage(error.message || "Copy failed.", "error");
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
      if (!res.ok) {
        setMessage(data.detail?.message || data.detail || "Publish failed.", "error");
        return;
      }
      weekMeta = data.week;
      shifts = data.shifts || [];
      await loadWeek();
      setMessage(data.message || "Rota published — staff can see shifts in Time Clock.");
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
      if (dirty && !window.confirm("Discard unsaved changes?")) return;
      currentWeekStart = mondayIso(new Date());
      loadWeek();
    });
    document.getElementById("rota-add-btn")?.addEventListener("click", addShiftFromForm);
    document.getElementById("rota-save-btn")?.addEventListener("click", saveRota);
    document.getElementById("rota-copy-prev-btn")?.addEventListener("click", copyPreviousWeek);
    document.getElementById("rota-publish-btn")?.addEventListener("click", publishRota);
    document.getElementById("rota-reload-btn")?.addEventListener("click", () => {
      if (dirty && !window.confirm("Discard unsaved changes?")) return;
      loadWeek();
    });
    document.getElementById("rota-view-grid")?.addEventListener("click", () => setView("grid"));
    document.getElementById("rota-view-list")?.addEventListener("click", () => setView("list"));

    setView("grid");
    await loadEmployeesList();
    await Promise.all([loadWeek(), loadShiftRequests()]);
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
