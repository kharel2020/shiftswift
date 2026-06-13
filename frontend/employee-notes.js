/** Employee portal — messages HR has shared with the logged-in employee. */
(function () {
  const API_BASE =
    localStorage.getItem("apiBaseUrl") ||
    (window.ShiftSwiftBrand?.resolveApiBase ? window.ShiftSwiftBrand.resolveApiBase() : "http://localhost:3000");
  const tenantId = localStorage.getItem("tenantId");

  if (!localStorage.getItem("token") || !tenantId) return;

  const listEl = document.getElementById("employee-notes-list");
  const summaryEl = document.getElementById("employee-notes-summary");

  function token() {
    return localStorage.getItem("token");
  }

  function authHeaders() {
    return {
      Authorization: `Bearer ${token()}`,
      "X-Tenant-Id": tenantId,
      "Content-Type": "application/json",
    };
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatWhen(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
    } catch {
      return iso;
    }
  }

  function renderNotes(items) {
    if (!listEl) return;
    if (!items.length) {
      listEl.innerHTML =
        '<p class="muted">No messages from HR yet. When your employer shares a note with you, it will appear here.</p>';
      return;
    }
    listEl.innerHTML = items
      .map(
        (note) => `
        <article class="employee-note-card employee-note-card--employee_visible">
          <header class="employee-note-card__head">
            <span class="employee-note-badge">From HR</span>
            <span class="muted">${escapeHtml(formatWhen(note.created_at))}</span>
          </header>
          <p class="employee-note-card__body">${escapeHtml(note.body || "")}</p>
        </article>`,
      )
      .join("");
  }

  function setSummaryText(sourceId, text) {
    const source = document.getElementById(sourceId);
    if (source) source.textContent = text;
    document.querySelectorAll(`[data-mirror="${sourceId}"]`).forEach((el) => {
      el.textContent = text;
    });
  }

  async function loadNotes() {
    try {
      const res = await fetch(`${API_BASE}/employee/me/notes`, { headers: authHeaders() });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not load notes");
      const items = data.items || [];
      renderNotes(items);
      if (summaryEl) {
        setSummaryText(
          "employee-notes-summary",
          items.length
            ? `${items.length} message${items.length === 1 ? "" : "s"} from HR.`
            : "No messages yet.",
        );
      }
    } catch (error) {
      if (listEl) {
        listEl.innerHTML = `<p class="muted">${escapeHtml(error.message || "Could not load notes.")}</p>`;
      }
      if (summaryEl) setSummaryText("employee-notes-summary", "Could not load notes.");
    }
  }

  loadNotes();
})();
