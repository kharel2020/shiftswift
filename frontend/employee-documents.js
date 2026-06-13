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
  const payslipsHost = document.getElementById("employee-payslips-list");

  let allItems = [];

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

  function bindDownloadButtons(container, items) {
    container.querySelectorAll("[data-download-doc]").forEach((btn) => {
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

  function documentActions(row) {
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
    return actions.join(" ");
  }

  function renderDocuments(items) {
    const generalDocs = items.filter((row) => row.category !== "payslip");
    if (!tbody) return;
    if (!generalDocs.length) {
      tbody.innerHTML =
        '<tr><td colspan="4" class="muted">No general documents shared yet. Signed employment contracts appear here after you sign, or when HR uploads a file to your profile.</td></tr>';
      return;
    }
    tbody.innerHTML = generalDocs
      .map(
        (row) => `<tr>
          <td><strong>${escapeHtml(row.title)}</strong></td>
          <td>${escapeHtml(row.category_label || row.category)}</td>
          <td>${escapeHtml(formatDate(row.created_at))}</td>
          <td><div class="table-actions">${documentActions(row)}</div></td>
        </tr>`
      )
      .join("");
    bindDownloadButtons(tbody, generalDocs);
  }

  function renderPayslips(items) {
    if (!payslipsHost) return;
    const payslips = items.filter((row) => row.category === "payslip");
    if (!payslips.length) {
      payslipsHost.innerHTML =
        '<p class="muted">No payslips shared yet. When HR uploads your payslip, it will appear here grouped by pay period.</p>';
      return;
    }

    const grouped = new Map();
    payslips.forEach((row) => {
      const key = row.pay_period || "Other";
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(row);
    });

    const sortedKeys = [...grouped.keys()].sort((a, b) => {
      if (a === "Other") return 1;
      if (b === "Other") return -1;
      return b.localeCompare(a);
    });

    payslipsHost.innerHTML = sortedKeys
      .map((period) => {
        const rows = grouped.get(period) || [];
        return `<section class="employee-payslip-group">
          <h3 class="employee-payslip-group__title">${escapeHtml(period)}</h3>
          <div class="hr-table-wrap">
            <table class="data-table">
              <thead><tr><th>Title</th><th>Added</th><th></th></tr></thead>
              <tbody>
                ${rows
                  .map(
                    (row) => `<tr>
                      <td><strong>${escapeHtml(row.title)}</strong></td>
                      <td>${escapeHtml(formatDate(row.created_at))}</td>
                      <td><div class="table-actions">${documentActions(row)}</div></td>
                    </tr>`
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
        </section>`;
      })
      .join("");

    bindDownloadButtons(payslipsHost, payslips);
  }

  async function loadDocuments() {
    try {
      const res = await apiFetch("/employee/me/documents");
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not load documents");
      allItems = data.items || [];
      renderDocuments(allItems);
      renderPayslips(allItems);
      if (summaryEl) {
        const payslipCount = allItems.filter((row) => row.category === "payslip").length;
        const otherCount = allItems.length - payslipCount;
        if (allItems.length === 0) {
          summaryEl.textContent = "Nothing shared yet.";
        } else {
          const parts = [];
          if (otherCount) parts.push(`${otherCount} document${otherCount === 1 ? "" : "s"}`);
          if (payslipCount) parts.push(`${payslipCount} payslip${payslipCount === 1 ? "" : "s"}`);
          summaryEl.textContent = `${parts.join(" · ")} available.`;
        }
      }
    } catch (error) {
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="4" class="muted">${escapeHtml(error.message || "Could not load documents.")}</td></tr>`;
      }
      if (payslipsHost) {
        payslipsHost.innerHTML = `<p class="muted">${escapeHtml(error.message || "Could not load payslips.")}</p>`;
      }
      if (summaryEl) summaryEl.textContent = "Could not load documents.";
    }
  }

  loadDocuments();
})();
