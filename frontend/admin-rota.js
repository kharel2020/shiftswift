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

  const DEFAULT_ROLE_SUGGESTIONS = ["Floor", "Bar", "Kitchen", "Front of house", "Management", "Day off"];
  const AVATAR_PALETTES = [
    { bg: "#E1F5EE", color: "#0F6E56" },
    { bg: "#E6F1FB", color: "#185FA5" },
    { bg: "#FAEEDA", color: "#854F0B" },
    { bg: "#FBEAF0", color: "#993556" },
  ];
  let panelOpen = false;

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

  function employeeRoleLabel(emp) {
    if (!emp) return "Staff";
    return emp.job_title || emp.department || "Staff";
  }

  function employeeShortName(emp) {
    if (!emp) return "Staff";
    const first = (emp.first_name || "").trim();
    const last = (emp.last_name || "").trim();
    if (first && last) return `${first[0]}. ${last.split(/\s+/)[0]}`;
    return employeeName(emp.id);
  }

  function avatarPalette(employeeId) {
    return AVATAR_PALETTES[Math.abs(Number(employeeId)) % AVATAR_PALETTES.length];
  }

  function employeeInitials(emp) {
    const first = (emp?.first_name || "").trim()[0] || "";
    const last = (emp?.last_name || "").trim()[0] || "";
    return (first + last).toUpperCase() || "?";
  }

  function shiftRoleKey(shift, emp) {
    return (shift.role_label || emp?.job_title || emp?.department || "").toLowerCase();
  }

  function isDayOffShift(shift) {
    const role = (shift.role_label || "").toLowerCase();
    return /day off|off day|annual leave|holiday|unpaid leave/.test(role);
  }

  function shiftBlockClass(shift, emp) {
    if (isDayOffShift(shift)) return "rota-shift-block--off";
    const role = shiftRoleKey(shift, emp);
    if (/kitchen|cook|chef/.test(role)) return "rota-shift-block--kitchen";
    if (/bar|floor|front|wait|server/.test(role)) return "rota-shift-block--floor";
    return "rota-shift-block--default";
  }

  function coverageLevel(count) {
    if (count === 0) return "empty";
    if (count <= 2) return "warn";
    return "ok";
  }

  function parseMinutes(time) {
    const [h, m] = String(time).slice(0, 5).split(":").map(Number);
    return h * 60 + m;
  }

  function shiftsTimeOverlap(a, b) {
    if (Number(a.employee_id) !== Number(b.employee_id) || a.shift_date !== b.shift_date) return false;
    let a0 = parseMinutes(a.start_time);
    let a1 = parseMinutes(a.end_time);
    let b0 = parseMinutes(b.start_time);
    let b1 = parseMinutes(b.end_time);
    if (a1 <= a0) a1 += 24 * 60;
    if (b1 <= b0) b1 += 24 * 60;
    return a0 < b1 && b0 < a1;
  }

  function getFormShiftCandidate() {
    const employeeId = document.getElementById("rota-add-employee")?.value;
    const shiftDate = document.getElementById("rota-add-day")?.value;
    const startTime = document.getElementById("rota-add-start")?.value;
    const endTime = document.getElementById("rota-add-end")?.value;
    const roleLabel = document.getElementById("rota-add-role")?.value?.trim() || "";
    const notes = document.getElementById("rota-add-notes")?.value?.trim() || "";
    if (!employeeId || !shiftDate || !startTime || !endTime) return null;
    return {
      employee_id: Number(employeeId),
      shift_date: shiftDate,
      start_time: startTime.slice(0, 5),
      end_time: endTime.slice(0, 5),
      role_label: roleLabel,
      notes,
    };
  }

  function findFormOverlap() {
    const candidate = getFormShiftCandidate();
    if (!candidate) return null;
    if (candidate.start_time === candidate.end_time) return "Start and end time cannot be the same";
    for (let i = 0; i < shifts.length; i += 1) {
      if (i === editingShiftIndex) continue;
      if (shiftsTimeOverlap(candidate, shifts[i])) {
        return `Overlaps with ${employeeName(shifts[i].employee_id)} ${shifts[i].start_time}–${shifts[i].end_time}`;
      }
    }
    return null;
  }

  function updateOverlapStatus() {
    const el = document.getElementById("rota-overlap-status");
    const addBtn = document.getElementById("rota-add-btn");
    if (!el) return;
    const overlap = findFormOverlap();
    if (!getFormShiftCandidate()) {
      el.textContent = "";
      el.className = "rota-overlap-status";
      if (addBtn) addBtn.disabled = false;
      return;
    }
    if (overlap) {
      el.textContent = overlap;
      el.className = "rota-overlap-status rota-overlap-status--error";
      if (addBtn) addBtn.disabled = true;
    } else {
      el.textContent = "No overlap detected for this slot";
      el.className = "rota-overlap-status rota-overlap-status--ok";
      if (addBtn) addBtn.disabled = false;
    }
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
    el.textContent = formatDuration(shiftDurationMinutes(start, end));
    updateOverlapStatus();
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
      el.textContent = `0 shifts · ${staff.length} staff · Mon–Sun`;
      return;
    }
    el.textContent = `${shiftCount} shift${shiftCount === 1 ? "" : "s"} · ${scheduledStaff} staff · Mon–Sun`;
  }

  function syncPanelVisibility() {
    const panel = document.getElementById("rota-shift-panel");
    if (!panel) return;
    if (activeView === "grid" && hasActiveEmployees() && panelOpen) {
      panel.removeAttribute("hidden");
    } else {
      panel.setAttribute("hidden", "");
    }
  }

  function renderEmptyState() {
    const empty = document.getElementById("rota-empty-state");
    const grid = document.getElementById("rota-grid");
    const hasStaff = hasActiveEmployees();
    if (empty) empty.hidden = hasStaff;
    if (grid) grid.hidden = !hasStaff;
    if (!hasStaff) {
      panelOpen = false;
      syncPanelVisibility();
    } else if (activeView === "grid" && !panelOpen) {
      panelOpen = true;
      syncPanelVisibility();
    }
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
        openShiftPanel({ shiftIndex: Number(btn.getAttribute("data-rota-edit")) });
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
    const todayIso = new Date().toISOString().slice(0, 10);
    const staff = activeEmployees();

    let html = '<div class="rota-grid-header"><div class="rota-gh-cell">Staff</div>';
    days.forEach((iso) => {
      const label = new Date(`${iso}T12:00:00`).toLocaleDateString("en-GB", {
        weekday: "short",
        day: "numeric",
      });
      const count = shiftsOnDate(iso);
      const level = coverageLevel(count);
      const todayClass = iso === todayIso ? " rota-gh-cell--today" : "";
      html += `<div class="rota-gh-cell${todayClass}">
        <span class="rota-day-sub">${escapeHtml(label)}</span>
        <span class="rota-day-cov"><span class="rota-cov-dot rota-cov-dot--${level}" aria-hidden="true"></span>${count} shift${count === 1 ? "" : "s"}</span>
      </div>`;
    });
    html += "</div>";

    staff.forEach((emp) => {
      const palette = avatarPalette(emp.id);
      html += `<div class="rota-staff-row" data-employee-id="${emp.id}">
        <div class="rota-staff-name-cell">
          <span class="rota-staff-avatar" style="background:${palette.bg};color:${palette.color}">${escapeHtml(employeeInitials(emp))}</span>
          <span><span class="rota-staff-name">${escapeHtml(employeeShortName(emp))}</span><span class="rota-staff-role">${escapeHtml(employeeRoleLabel(emp))}</span></span>
        </div>`;
      days.forEach((iso) => {
        const cellShifts = shifts
          .map((s, index) => ({ s, index }))
          .filter(({ s }) => Number(s.employee_id) === Number(emp.id) && s.shift_date === iso);
        html += `<div class="rota-shift-cell rota-grid-drop" data-employee-id="${emp.id}" data-shift-date="${iso}">`;
        cellShifts.forEach(({ s, index }) => {
          const a = attendanceForShift(s);
          const attendClass =
            a?.attendance_status === "no_show" || a?.attendance_status === "late"
              ? ` rota-shift-block--${a.attendance_status}`
              : "";
          const blockClass = shiftBlockClass(s, emp);
          const roleText = escapeHtml(s.role_label || employeeRoleLabel(emp));
          const blockBody = isDayOffShift(s)
            ? "Day off"
            : `${escapeHtml(s.start_time)}–${escapeHtml(s.end_time)}<span class="rota-shift-block-role">${roleText}</span>`;
          html += `<button type="button" class="rota-shift-block ${blockClass}${attendClass}" draggable="true" data-shift-index="${index}" title="Edit shift">${blockBody}</button>`;
        });
        html += `<span class="rota-add-cell-hint">+ add</span></div>`;
      });
      html += "</div>";
    });

    grid.innerHTML = html;

    grid.querySelectorAll(".rota-shift-block").forEach((chip) => {
      chip.addEventListener("dragstart", (event) => {
        dragShiftIndex = Number(chip.getAttribute("data-shift-index"));
        event.dataTransfer?.setData("text/plain", String(dragShiftIndex));
      });
      chip.addEventListener("click", (event) => {
        event.stopPropagation();
        openShiftPanel({ shiftIndex: Number(chip.getAttribute("data-shift-index")) });
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
      cell.addEventListener("click", () => {
        openShiftPanel({
          employeeId: Number(cell.getAttribute("data-employee-id")),
          shiftDate: cell.getAttribute("data-shift-date"),
        });
      });
    });
  }

  function renderAll() {
    renderWeekSummary();
    renderGrid();
    renderShiftTable();
    updateHeader();
    syncPanelVisibility();
  }

  function setView(view) {
    activeView = view;
    document.getElementById("rota-grid-view").hidden = view !== "grid";
    document.getElementById("rota-list-panel").hidden = view !== "list";
    document.getElementById("rota-view-grid")?.classList.toggle("is-active", view === "grid");
    document.getElementById("rota-view-list")?.classList.toggle("is-active", view === "list");
    if (view === "grid" && hasActiveEmployees()) {
      panelOpen = true;
    } else if (view !== "grid") {
      panelOpen = false;
    }
    syncPanelVisibility();
  }

  function closeShiftPanel() {
    editingShiftIndex = null;
    panelOpen = false;
    syncPanelVisibility();
    document.getElementById("rota-add-btn").textContent = "Add to rota";
    document.getElementById("rota-shift-popover-title").textContent = "Add shift";
  }

  function openShiftPanel({ employeeId = null, shiftDate = null, shiftIndex = null } = {}) {
    if (!hasActiveEmployees()) {
      setMessage("Add active employees before building a rota.", "error");
      return;
    }
    panelOpen = true;
    syncPanelVisibility();

    const employeeSelect = document.getElementById("rota-add-employee");
    const daySelect = document.getElementById("rota-add-day");
    const roleInput = document.getElementById("rota-add-role");
    const notesInput = document.getElementById("rota-add-notes");
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
      if (notesInput) notesInput.value = shift.notes || "";
      if (title) title.textContent = "Edit shift";
      if (addBtn) addBtn.textContent = "Save shift";
    } else {
      if (employeeSelect && employeeId) employeeSelect.value = String(employeeId);
      if (daySelect && shiftDate) daySelect.value = shiftDate;
      populateTimeSelects("09:00", "17:00");
      if (roleInput) roleInput.value = "";
      if (notesInput) notesInput.value = "";
      if (employeeSelect?.value) prefillRoleFromEmployee(Number(employeeSelect.value));
      if (title) title.textContent = "Add shift";
      if (addBtn) addBtn.textContent = "Add to rota";
    }

    updatePanelContext();
    updateShiftDurationLabel();
  }

  function updatePanelContext() {
    const panel = document.getElementById("rota-shift-panel");
    if (panel?.hasAttribute("hidden")) return;
    const employeeSelect = document.getElementById("rota-add-employee");
    const daySelect = document.getElementById("rota-add-day");
    const context = document.getElementById("rota-shift-popover-context");
    const empId = Number(employeeSelect?.value);
    const dateIso = daySelect?.value;
    if (!context || !empId || !dateIso) return;
    context.textContent = `${employeeName(empId)} · ${new Date(`${dateIso}T12:00:00`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" })}`;
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
      .map(
        (e) =>
          `<option value="${e.id}">${escapeHtml(employeeShortName(e))} — ${escapeHtml(employeeRoleLabel(e))}</option>`
      )
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
        setMessage("Click a cell to add your first shift, then Save draft.");
      } else {
        setMessage("Unsaved changes? Save draft, then publish when ready.");
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
    const overlap = findFormOverlap();
    if (overlap) {
      setMessage(overlap, "error");
      updateOverlapStatus();
      return;
    }
    const candidate = getFormShiftCandidate();
    if (!candidate) {
      setMessage("Employee, day, start, and end are required.", "error");
      return;
    }
    const payload = {
      ...candidate,
      employee_name: employeeName(candidate.employee_id),
    };
    if (editingShiftIndex != null && shifts[editingShiftIndex]) {
      shifts[editingShiftIndex] = { ...shifts[editingShiftIndex], ...payload };
      setMessage("Shift updated — click Save draft.");
    } else {
      shifts.push(payload);
      setMessage("Shift added — click Save draft.");
    }
    shifts.sort((a, b) => `${a.shift_date}${a.start_time}`.localeCompare(`${b.shift_date}${b.start_time}`));
    markDirty();
    panelOpen = true;
    renderAll();
    updateOverlapStatus();
  }

  function clearRota() {
    if (!shifts.length) {
      setMessage("No shifts to clear.");
      return;
    }
    if (!window.confirm("Remove all shifts from this week? You still need to Save rota to persist.")) return;
    shifts = [];
    markDirty();
    closeShiftPanel();
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
    closeShiftPanel();
    currentWeekStart = addDays(currentWeekStart, delta * 7);
    loadWeek();
  }

  async function initSection() {
    populateTimeSelects("09:00", "17:00");

    document.getElementById("rota-prev-week")?.addEventListener("click", () => changeWeek(-1));
    document.getElementById("rota-next-week")?.addEventListener("click", () => changeWeek(1));
    document.getElementById("rota-this-week")?.addEventListener("click", () => {
      if (dirty && !window.confirm("Discard unsaved changes?")) return;
      closeShiftPanel();
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
      closeShiftPanel();
      loadWeek();
    });
    document.getElementById("rota-view-grid")?.addEventListener("click", () => setView("grid"));
    document.getElementById("rota-view-list")?.addEventListener("click", () => setView("list"));
    document.getElementById("rota-shift-cancel-btn")?.addEventListener("click", closeShiftPanel);
    document.getElementById("rota-shift-popover-close")?.addEventListener("click", closeShiftPanel);
    document.getElementById("rota-add-employee")?.addEventListener("change", (event) => {
      prefillRoleFromEmployee(Number(event.target.value));
      updatePanelContext();
      updateOverlapStatus();
    });
    document.getElementById("rota-add-day")?.addEventListener("change", () => {
      updatePanelContext();
      updateOverlapStatus();
    });
    document.getElementById("rota-add-start")?.addEventListener("change", updateShiftDurationLabel);
    document.getElementById("rota-add-end")?.addEventListener("change", updateShiftDurationLabel);
    document.getElementById("rota-add-role")?.addEventListener("input", updateOverlapStatus);
    document.getElementById("rota-add-notes")?.addEventListener("input", updateOverlapStatus);

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
