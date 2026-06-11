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
  let editingShiftIndex = null;

  const ATTENDANCE_LABELS = {
    scheduled: "Scheduled",
    awaiting: "Awaiting",
    attended: "Attended",
    late: "Late",
    no_show: "No show",
    missing_clock_out: "No clock-out",
  };

  const DEFAULT_ROLE_SUGGESTIONS = ["Floor", "Bar", "Kitchen", "Front of house", "Management"];

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

  function employeeById(id) {
    return employees.find((e) => Number(e.id) === Number(id));
  }

  function activeEmployees() {
    return employees.filter((e) => ["active", "onboarding", "suspended"].includes(e.status));
  }

  function hasActiveEmployees() {
    return activeEmployees().length > 0;
  }

  function timeSelectOptions(selected = "09:00") {
    const parts = [];
    for (let hour = 0; hour < 24; hour += 1) {
      for (const minute of [0, 30]) {
        const value = `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
        parts.push(
          `<option value="${value}"${value === selected.slice(0, 5) ? " selected" : ""}>${value}</option>`
        );
      }
    }
    return parts.join("");
  }

  function populateTimeSelects(start = "09:00", end = "17:00") {
    const startEl = document.getElementById("rota-add-start");
    const endEl = document.getElementById("rota-add-end");
    if (startEl) startEl.innerHTML = timeSelectOptions(start);
    if (endEl) endEl.innerHTML = timeSelectOptions(end);
    updateShiftDurationLabel();
  }

  function shiftDurationMinutes(start, end) {
    const [sh, sm] = start.split(":").map(Number);
    const [eh, em] = end.split(":").map(Number);
    let mins = eh * 60 + em - (sh * 60 + sm);
    if (mins <= 0) mins += 24 * 60;
    return mins;
  }

  function formatDuration(mins) {
    const hours = Math.floor(mins / 60);
    const minutes = mins % 60;
    if (minutes === 0) return `${hours} hour${hours === 1 ? "" : "s"}`;
    return `${hours}h ${minutes}m`;
  }

  function updateShiftDurationLabel() {
    const el = document.getElementById("rota-shift-duration");
    const start = document.getElementById("rota-add-start")?.value;
    const end = document.getElementById("rota-add-end")?.value;
    if (!el || !start || !end) return;
    el.textContent = `Shift duration: ${formatDuration(shiftDurationMinutes(start, end))}`;
  }

  function roleSuggestions() {
    const values = new Set(DEFAULT_ROLE_SUGGESTIONS);
    employees.forEach((emp) => {
      if (emp.job_title) values.add(emp.job_title);
      if (emp.department) values.add(emp.department);
    });
    return [...values].sort((a, b) => a.localeCompare(b));
  }

  function populateRoleSuggestions() {
    const list = document.getElementById("rota-role-suggestions");
    if (!list) return;
    list.innerHTML = roleSuggestions().map((value) => `<option value="${escapeHtml(value)}"></option>`).join("");
  }

  function prefillRoleFromEmployee(employeeId) {
    const roleInput = document.getElementById("rota-add-role");
    if (!roleInput || roleInput.value.trim()) return;
    const emp = employeeById(employeeId);
    if (!emp) return;
    roleInput.value = emp.job_title || emp.department || "";
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

  function renderStatusBadge() {
    const status = document.getElementById("rota-week-status");
    if (!status) return;
    if (weekMeta?.status === "published") {
      status.innerHTML = '<span class="rota-status-badge rota-status-badge--published">Published</span>';
      return;
    }
    status.innerHTML = '<span class="rota-status-badge rota-status-badge--draft">Draft</span>';
  }

  function updateHeader() {
    document.getElementById("rota-week-label").textContent = formatWeekLabel(currentWeekStart);
    renderStatusBadge();
    const publishBtn = document.getElementById("rota-publish-btn");
    const canPublish = Boolean(weekMeta?.version && weekMeta.status !== "published" && shifts.length && !dirty);
    if (publishBtn) {
      publishBtn.disabled = !canPublish;
      publishBtn.title = canPublish
        ? "Publish so staff see shifts in Time Clock"
        : dirty
          ? "Save the rota before publishing"
          : !shifts.length
            ? "Add shifts before publishing"
            : weekMeta?.status === "published"
              ? "Already published"
              : "Save the rota before publishing";
    }
  }

  function renderWeekSummary() {
    const el = document.getElementById("rota-week-summary");
    if (!el) return;
    const staff = activeEmployees();
    const shiftCount = shifts.length;
    const scheduledStaff = new Set(shifts.map((s) => s.employee_id)).size;
    if (!staff.length) {
      el.textContent = "";
      return;
    }
    if (!shiftCount) {
      el.textContent = `No shifts yet · ${staff.length} active staff available`;
      return;
    }
    el.textContent = `${shiftCount} shift${shiftCount === 1 ? "" : "s"} · Mon–Sun · ${scheduledStaff} staff scheduled`;
  }

  function renderEmptyState() {
    const empty = document.getElementById("rota-empty-state");
    const grid = document.getElementById("rota-grid");
    const popover = document.getElementById("rota-shift-popover");
    const hasStaff = hasActiveEmployees();
    if (empty) empty.hidden = hasStaff;
    if (grid) grid.hidden = !hasStaff;
    if (popover && !hasStaff) closeShiftPopover();
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
      emptyMessage: hasActiveEmployees()
        ? "No shifts this week — click + in the grid to add one."
        : "No active employees — open the Employees section to add team members.",
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
            `<button type="button" class="btn ghost btn-sm" data-rota-edit="${index}">Edit</button> <button type="button" class="btn ghost btn-sm" data-rota-remove="${index}">Remove</button>`,
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
    tbody.querySelectorAll("[data-rota-edit]").forEach((btn) => {
      btn.addEventListener("click", () => {
        openShiftPopover({ shiftIndex: Number(btn.getAttribute("data-rota-edit")) });
      });
    });
  }

  function shiftsOnDate(iso) {
    return shifts.filter((s) => s.shift_date === iso).length;
  }

  function renderGrid() {
    const grid = document.getElementById("rota-grid");
    if (!grid) return;
    renderEmptyState();
    if (!hasActiveEmployees()) return;

    const days = Array.from({ length: 7 }, (_, i) => addDays(currentWeekStart, i));
    const dayLabels = days.map((iso) =>
      new Date(`${iso}T12:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric" })
    );
    const staff = activeEmployees();

    let html =
      '<div class="rota-grid-table"><div class="rota-grid-row rota-grid-row--head"><div class="rota-grid-cell rota-grid-cell--name">Staff</div>';
    dayLabels.forEach((label, index) => {
      const iso = days[index];
      const count = shiftsOnDate(iso);
      const coverageClass = count > 0 ? "rota-day-coverage--ok" : "rota-day-coverage--empty";
      html += `<div class="rota-grid-cell rota-grid-cell--head">
        <span>${escapeHtml(label)}</span>
        <span class="rota-day-coverage ${coverageClass}" title="${count} shift${count === 1 ? "" : "s"} scheduled">${count}</span>
      </div>`;
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
          const flag =
            a?.attendance_status === "no_show" || a?.attendance_status === "late"
              ? ` rota-shift-chip--${a.attendance_status}`
              : "";
          html += `<button type="button" class="rota-shift-chip${flag}" draggable="true" data-shift-index="${index}" title="Edit shift — ${escapeHtml(s.start_time)}–${escapeHtml(s.end_time)}">${escapeHtml(s.start_time)}–${escapeHtml(s.end_time)}</button>`;
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
      chip.addEventListener("click", (event) => {
        event.stopPropagation();
        openShiftPopover({ shiftIndex: Number(chip.getAttribute("data-shift-index")) });
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
      cell.addEventListener("click", (event) => {
        if (event.target.closest(".rota-shift-chip, .rota-grid-add")) return;
        openShiftPopover({
          employeeId: Number(cell.getAttribute("data-employee-id")),
          shiftDate: cell.getAttribute("data-shift-date"),
        });
      });
    });

    grid.querySelectorAll(".rota-grid-add").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        openShiftPopover({
          employeeId: Number(btn.getAttribute("data-add-employee")),
          shiftDate: btn.getAttribute("data-add-date"),
        });
      });
    });
  }

  function renderAll() {
    renderWeekSummary();
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

  function closeShiftPopover() {
    editingShiftIndex = null;
    document.getElementById("rota-shift-popover")?.setAttribute("hidden", "");
    document.getElementById("rota-add-btn").textContent = "Add to rota";
    document.getElementById("rota-shift-popover-title").textContent = "Add shift";
  }

  function openShiftPopover({ employeeId = null, shiftDate = null, shiftIndex = null } = {}) {
    if (!hasActiveEmployees()) {
      setMessage("Add active employees before building a rota.", "error");
      return;
    }
    const popover = document.getElementById("rota-shift-popover");
    const employeeSelect = document.getElementById("rota-add-employee");
    const daySelect = document.getElementById("rota-add-day");
    const roleInput = document.getElementById("rota-add-role");
    const context = document.getElementById("rota-shift-popover-context");
    const addBtn = document.getElementById("rota-add-btn");
    const title = document.getElementById("rota-shift-popover-title");

    populateEmployeeSelect();
    populateDaySelect();

    editingShiftIndex = shiftIndex;

    if (shiftIndex != null && shifts[shiftIndex]) {
      const shift = shifts[shiftIndex];
      if (employeeSelect) employeeSelect.value = String(shift.employee_id);
      if (daySelect) daySelect.value = shift.shift_date;
      populateTimeSelects(shift.start_time, shift.end_time);
      if (roleInput) roleInput.value = shift.role_label || "";
      if (title) title.textContent = "Edit shift";
      if (addBtn) addBtn.textContent = "Save shift";
      if (context) {
        context.textContent = `${employeeName(shift.employee_id)} · ${new Date(`${shift.shift_date}T12:00:00`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" })}`;
      }
    } else {
      if (employeeSelect && employeeId) employeeSelect.value = String(employeeId);
      if (daySelect && shiftDate) daySelect.value = shiftDate;
      populateTimeSelects("09:00", "17:00");
      if (roleInput) roleInput.value = "";
      if (employeeSelect?.value) prefillRoleFromEmployee(Number(employeeSelect.value));
      if (title) title.textContent = "Add shift";
      if (addBtn) addBtn.textContent = "Add to rota";
      const empId = Number(employeeSelect?.value);
      const dateIso = daySelect?.value;
      if (context && empId && dateIso) {
        context.textContent = `${employeeName(empId)} · ${new Date(`${dateIso}T12:00:00`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" })}`;
      } else if (context) {
        context.textContent = "Choose employee and day, then set times.";
      }
    }

    popover?.removeAttribute("hidden");
    popover?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    updateShiftDurationLabel();
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
    const hint = document.getElementById("rota-employee-empty-hint");
    const staff = activeEmployees();
    if (!select) return;
    if (!staff.length) {
      select.innerHTML = '<option value="">No active employees</option>';
      select.disabled = true;
      hint?.removeAttribute("hidden");
      document.getElementById("rota-add-btn")?.setAttribute("disabled", "");
      return;
    }
    select.disabled = false;
    hint?.setAttribute("hidden", "");
    document.getElementById("rota-add-btn")?.removeAttribute("disabled");
    select.innerHTML = staff
      .map((e) => `<option value="${e.id}">${escapeHtml(employeeName(e.id))}</option>`)
      .join("");
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
      if (weekMeta.status === "published") {
        setMessage("Published — punch vs rota flags update live.");
      } else if (!hasActiveEmployees()) {
        setMessage("Add active employees before building a rota.");
      } else if (!shifts.length) {
        setMessage("Click + in the grid to add your first shift, then Save rota.");
      } else {
        setMessage("Unsaved changes? Save rota, then publish when ready.");
      }
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
    populateRoleSuggestions();
    renderEmptyState();
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
    const payload = {
      employee_id: Number(employeeId),
      employee_name: employeeName(employeeId),
      shift_date: shiftDate,
      start_time: startTime.slice(0, 5),
      end_time: endTime.slice(0, 5),
      role_label: roleLabel,
      notes: "",
    };
    if (editingShiftIndex != null && shifts[editingShiftIndex]) {
      shifts[editingShiftIndex] = { ...shifts[editingShiftIndex], ...payload };
      setMessage("Shift updated — click Save rota.");
    } else {
      shifts.push(payload);
      setMessage("Shift added — click Save rota.");
    }
    shifts.sort((a, b) => `${a.shift_date}${a.start_time}`.localeCompare(`${b.shift_date}${b.start_time}`));
    markDirty();
    closeShiftPopover();
    renderAll();
  }

  function clearRota() {
    if (!shifts.length) {
      setMessage("No shifts to clear.");
      return;
    }
    if (!window.confirm("Remove all shifts from this week? You still need to Save rota to persist.")) return;
    shifts = [];
    markDirty();
    closeShiftPopover();
    renderAll();
    setMessage("Rota cleared — click Save rota to persist.");
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
      setMessage(data.message || "Rota saved — publish when ready.");
    } catch (error) {
      setMessage(error.message || "Save failed.", "error");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function copyPreviousWeek() {
    if (!window.confirm("Copy all shifts from last week into this week? Unsaved changes will be lost.")) return;
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
    closeShiftPopover();
    currentWeekStart = addDays(currentWeekStart, delta * 7);
    loadWeek();
  }

  function updatePopoverContext() {
    if (document.getElementById("rota-shift-popover")?.hasAttribute("hidden")) return;
    const employeeSelect = document.getElementById("rota-add-employee");
    const daySelect = document.getElementById("rota-add-day");
    const context = document.getElementById("rota-shift-popover-context");
    const empId = Number(employeeSelect?.value);
    const dateIso = daySelect?.value;
    if (!context || !empId || !dateIso) return;
    context.textContent = `${employeeName(empId)} · ${new Date(`${dateIso}T12:00:00`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" })}`;
  }

  async function initSection() {
    populateTimeSelects("09:00", "17:00");

    document.getElementById("rota-prev-week")?.addEventListener("click", () => changeWeek(-1));
    document.getElementById("rota-next-week")?.addEventListener("click", () => changeWeek(1));
    document.getElementById("rota-this-week")?.addEventListener("click", () => {
      if (dirty && !window.confirm("Discard unsaved changes?")) return;
      closeShiftPopover();
      currentWeekStart = mondayIso(new Date());
      loadWeek();
    });
    document.getElementById("rota-add-btn")?.addEventListener("click", addShiftFromForm);
    document.getElementById("rota-save-btn")?.addEventListener("click", saveRota);
    document.getElementById("rota-copy-prev-btn")?.addEventListener("click", copyPreviousWeek);
    document.getElementById("rota-clear-btn")?.addEventListener("click", clearRota);
    document.getElementById("rota-publish-btn")?.addEventListener("click", publishRota);
    document.getElementById("rota-reload-btn")?.addEventListener("click", () => {
      if (dirty && !window.confirm("Discard unsaved changes?")) return;
      closeShiftPopover();
      loadWeek();
    });
    document.getElementById("rota-view-grid")?.addEventListener("click", () => setView("grid"));
    document.getElementById("rota-view-list")?.addEventListener("click", () => setView("list"));
    document.getElementById("rota-shift-cancel-btn")?.addEventListener("click", closeShiftPopover);
    document.getElementById("rota-shift-popover-close")?.addEventListener("click", closeShiftPopover);
    document.getElementById("rota-add-employee")?.addEventListener("change", (event) => {
      prefillRoleFromEmployee(Number(event.target.value));
      updatePopoverContext();
    });
    document.getElementById("rota-add-day")?.addEventListener("change", updatePopoverContext);
    document.getElementById("rota-add-start")?.addEventListener("change", updateShiftDurationLabel);
    document.getElementById("rota-add-end")?.addEventListener("change", updateShiftDurationLabel);

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
