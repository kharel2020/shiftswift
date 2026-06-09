/** Settings document store — filters, metadata, edit and delete. */
(function () {
  const { apiFetch, escapeHtml, mountEditForm, renderTableBody } = window.Admin;

  const FILTER_IDS = {
    category: "document-filter-category",
    stage: "document-filter-stage",
  };

  function categoryLabel(value) {
    const categories = window.Admin.formOptions?.document_categories || [];
    return categories.find((item) => item.value === value)?.label || value;
  }

  function stageLabel(value) {
    const stages = window.Admin.formOptions?.document_lifecycle_stages || [];
    return stages.find((item) => item.value === value)?.label || value;
  }

  function documentFormSchema() {
    return {
      id: "document",
      columns: 2,
      submitLabel: "Add document",
      successMessage: "Document saved.",
      fields: [
        { name: "title", label: "Title", type: "text", required: true },
        {
          name: "category",
          label: "Category",
          type: "select",
          optionsKey: "document_categories",
          defaultValue: "general",
        },
        {
          name: "lifecycle_stage",
          label: "Lifecycle stage",
          type: "select",
          optionsKey: "document_lifecycle_stages",
          defaultValue: "general",
        },
        { name: "document_url", label: "Document URL", type: "url", placeholder: "https://..." },
        { name: "expires_at", label: "Expiry date", type: "date" },
        { name: "original_filename", label: "Original filename", type: "text", placeholder: "contract.pdf" },
        { name: "notes", label: "Notes", type: "textarea", span: 2, rows: 2 },
      ],
    };
  }

  function editFormSchema(row) {
    return {
      id: `document-edit-${row.id}`,
      columns: 2,
      submitLabel: "Update document",
      successMessage: "Document updated.",
      fields: documentFormSchema().fields,
    };
  }

  function buildQuery() {
    const params = new URLSearchParams();
    const category = document.getElementById(FILTER_IDS.category)?.value;
    const stage = document.getElementById(FILTER_IDS.stage)?.value;
    if (category) params.set("category", category);
    if (stage) params.set("lifecycle_stage", stage);
    const query = params.toString();
    return query ? `?${query}` : "";
  }

  async function loadSettingsDocuments() {
    const tbody = document.getElementById("documents-table-body");
    const formHost = document.getElementById("document-form");
    const filtersHost = document.getElementById("document-filters");
    if (!tbody && !formHost) return;

    if (filtersHost && !filtersHost.dataset.ready) {
      const categories = window.Admin.formOptions?.document_categories || [];
      const stages = window.Admin.formOptions?.document_lifecycle_stages || [];
      filtersHost.innerHTML = `
        <div class="form-grid form-grid--2">
          <label class="field">
            <span>Category</span>
            <select id="${FILTER_IDS.category}">
              <option value="">All categories</option>
              ${categories.map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`).join("")}
            </select>
          </label>
          <label class="field">
            <span>Lifecycle stage</span>
            <select id="${FILTER_IDS.stage}">
              <option value="">All stages</option>
              ${stages.map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`).join("")}
            </select>
          </label>
        </div>`;
      filtersHost.dataset.ready = "1";
      filtersHost.querySelectorAll("select").forEach((el) => {
        el.addEventListener("change", () => refreshDocuments());
      });
    }

    async function refreshDocuments() {
      try {
        const res = await apiFetch(`/admin/documents${buildQuery()}`);
        if (!res.ok) throw new Error("Load failed");
        const data = await res.json();

        renderTableBody(tbody, {
          emptyMessage: "No documents stored yet.",
          columns: [
            { key: "title", render: (row) => `<strong>${escapeHtml(row.title)}</strong>` },
            { key: "category", render: (row) => escapeHtml(categoryLabel(row.category)) },
            { key: "lifecycle_stage", render: (row) => escapeHtml(stageLabel(row.lifecycle_stage || "general")) },
            {
              key: "document_url",
              render: (row) =>
                row.document_url
                  ? `<a href="${escapeHtml(row.document_url)}" target="_blank" rel="noopener">Open</a>`
                  : "<span class='muted'>—</span>",
            },
            {
              key: "expires_at",
              render: (row) => escapeHtml((row.expires_at || "").slice(0, 10) || "—"),
            },
            { key: "created_at", render: (row) => escapeHtml((row.created_at || "").slice(0, 10)) },
            {
              key: "actions",
              render: (row) =>
                `<div class="table-actions">
                  <button type="button" class="btn ghost" data-edit-doc="${row.id}">Edit</button>
                  <button type="button" class="btn ghost" data-delete-doc="${row.id}">Remove</button>
                </div>`,
            },
          ],
          rows: data.items || [],
        });

        tbody.querySelectorAll("[data-delete-doc]").forEach((btn) => {
          btn.addEventListener("click", async () => {
            if (!window.confirm("Remove this document record?")) return;
            const res = await apiFetch(`/admin/documents/${btn.dataset.deleteDoc}`, { method: "DELETE" });
            if (!res.ok) {
              const err = await res.json();
              alert(err.detail || "Delete failed");
              return;
            }
            await refreshDocuments();
          });
        });

        tbody.querySelectorAll("[data-edit-doc]").forEach((btn) => {
          btn.addEventListener("click", () => {
            const row = (data.items || []).find((item) => String(item.id) === btn.dataset.editDoc);
            if (!row) return;
            const host = document.getElementById("document-edit-panel");
            if (!host) return;
            host.hidden = false;
            host.innerHTML = `<h4>Edit document</h4><div id="document-edit-form"></div>`;
            mountEditForm(host.querySelector("#document-edit-form"), editFormSchema(row), {
              values: {
                title: row.title,
                category: row.category,
                lifecycle_stage: row.lifecycle_stage || "general",
                document_url: row.document_url || "",
                expires_at: (row.expires_at || "").slice(0, 10),
                original_filename: row.original_filename || "",
                notes: row.notes || "",
              },
              onSubmit: async (payload) => {
                const res = await apiFetch(`/admin/documents/${row.id}`, {
                  method: "PATCH",
                  body: JSON.stringify({
                    ...payload,
                    document_url: payload.document_url || null,
                    notes: payload.notes || null,
                    expires_at: payload.expires_at || null,
                    original_filename: payload.original_filename || null,
                  }),
                });
                const body = await res.json();
                if (!res.ok) throw new Error(body.detail || "Update failed");
                host.hidden = true;
                await refreshDocuments();
              },
            });
          });
        });
      } catch {
        renderTableBody(tbody, {
          columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }, { key: "e" }, { key: "f" }, { key: "g" }],
          rows: [],
          emptyMessage: "Could not load documents.",
        });
      }
    }

    if (formHost && !formHost.dataset.ready) {
      mountEditForm(formHost, documentFormSchema(), {
        onSubmit: async (payload) => {
          const res = await apiFetch("/admin/documents", {
            method: "POST",
            body: JSON.stringify({
              ...payload,
              document_url: payload.document_url || null,
              notes: payload.notes || null,
              expires_at: payload.expires_at || null,
              original_filename: payload.original_filename || null,
            }),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Save failed");
          formHost.querySelector("form")?.reset();
          await refreshDocuments();
        },
      });
      formHost.dataset.ready = "1";
    }

    await refreshDocuments();
  }

  window.AdminDocuments = { loadSettingsDocuments };
})();
