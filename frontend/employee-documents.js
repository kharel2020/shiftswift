/** Employee portal — view and download HR documents shared on their profile. */
(function () {
  const API_BASE =
    localStorage.getItem("apiBaseUrl") ||
    (window.ShiftSwiftBrand?.resolveApiBase ? window.ShiftSwiftBrand.resolveApiBase() : "http://localhost:3000");
  const tenantId = localStorage.getItem("tenantId");

  if (!localStorage.getItem("token") || !tenantId) return;

  const tbody = document.getElementById("employee-documents-body");
  const messageEl = document.getElementById("employee-documents-message");
  const summaryEl = document.getElementById("employee-docs-summary");

  function token() {
    return localStorage.getItem("token");
  }

  function authHeaders(json = true) {
    const headers = {
      Authorization: `Bearer ${token()}`,
      "X-Tenant-Id": tenantId,
    };
    if (json) headers["Content-Type"] = "application/json";
    return headers;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatDate(value) {
    if (!value) return "—";
    try {
      return new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
    } catch {
      return value;
    }
  }

  async function apiFetch(path, options = {}) {
    return fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...authHeaders(options.body != null), ...(options.headers || {}) },
    });
  }

  async function downloadDocument(documentId, filename) {
    const res = await apiFetch(`/employee/me/documents/${documentId}/file`, { headers: authHeaders(false) });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Download failed");
    }
    let name = filename || "document";
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    if (match) name = match[1];
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.click();
    URL.revokeObjectURL(url);
  }

  function renderDocuments(items) {
    if (!tbody) return;
    if (!items.length) {
      tbody.innerHTML =
        '<tr><td colspan="4" class="muted">No documents shared yet. Signed employment contracts appear here after you sign, or when HR uploads a file to your profile.</td></tr>';
      return;
    }
    tbody.innerHTML = items
      .map((row) => {
        const actions = [];
        if (row.has_file) {
          actions.push(
            `<button type="button" class="btn ghost" data-download-doc="${escapeHtml(row.id)}">Download</button>`
          );
        }
        if (row.document_url) {
          actions.push(
            `<a class="btn ghost" href="${escapeHtml(row.document_url)}" target="_blank" rel="noopener">Open link</a>`
          );
        }
        return `<tr>
          <td><strong>${escapeHtml(row.title)}</strong></td>
          <td>${escapeHtml(row.category_label || row.category)}</td>
          <td>${escapeHtml(formatDate(row.created_at))}</td>
          <td><div class="table-actions">${actions.join(" ")}</div></td>
        </tr>`;
      })
      .join("");

    tbody.querySelectorAll("[data-download-doc]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (messageEl) messageEl.textContent = "Downloading…";
        try {
          const row = items.find((item) => String(item.id) === btn.dataset.downloadDoc);
          await downloadDocument(Number(btn.dataset.downloadDoc), row?.original_filename);
          if (messageEl) messageEl.textContent = "";
        } catch (error) {
          if (messageEl) messageEl.textContent = error.message || "Download failed";
        }
      });
    });
  }

  async function loadDocuments() {
    try {
      const res = await apiFetch("/employee/me/documents");
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not load documents");
      const items = data.items || [];
      renderDocuments(items);
      if (summaryEl) {
        summaryEl.textContent =
          items.length === 0
            ? "Nothing shared yet."
            : `${items.length} document${items.length === 1 ? "" : "s"} available.`;
      }
    } catch (error) {
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="4" class="muted">${escapeHtml(error.message || "Could not load documents.")}</td></tr>`;
      }
      if (summaryEl) summaryEl.textContent = "Could not load documents.";
    }
  }

  loadDocuments();
})();
