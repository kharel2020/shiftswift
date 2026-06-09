/** HR process templates + AI document assistant. */
(async function initAdminTemplates() {
  const { apiFetch, renderTableBody, escapeHtml, downloadAuthenticated, parseHashBaseSection } = window.Admin;

  let ready = false;
  let selectedId = null;
  let aiStatus = null;
  let listCache = [];

  function categoryLabel(cat) {
    return String(cat || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function syncStatusPill(item) {
    if (item.update_available) {
      return `<span class="status-pill status-warning">Update v${escapeHtml(item.platform_version)}</span>`;
    }
    if (item.is_customised) {
      return `<span class="status-pill status-ok">Custom</span>`;
    }
    return `<span class="status-pill status-ok">Latest</span>`;
  }

  function renderUpdatesBanner(data) {
    const banner = document.getElementById("hr-template-updates-banner");
    if (!banner) return;
    const pending = Number(data.updates_pending || 0);
    if (!pending) {
      banner.hidden = true;
      banner.innerHTML = "";
      return;
    }
    banner.hidden = false;
    banner.className = "promo-result promo-result-message";
    banner.innerHTML = `
      <p><strong>${pending} template${pending === 1 ? "" : "s"}</strong> have a newer platform version (UK law / guidance update).
      Open the template and choose <strong>Apply platform update</strong>, or download <strong>platform latest</strong> without changing your saved copy.</p>`;
  }

  async function loadAiStatus() {
    const panel = document.getElementById("ai-status-panel");
    if (!panel) return;
    try {
      const res = await apiFetch("/ai/status");
      aiStatus = await res.json();
      if (!res.ok) throw new Error("Status unavailable");
      const toggle = document.getElementById("ai-tenant-toggle");
      if (toggle) toggle.checked = !!aiStatus.tenant_enabled;
      panel.innerHTML = `
        <p class="promo-result-message ${aiStatus.available ? "promo-result-message--ok" : ""}">
          Provider: <strong>${escapeHtml(aiStatus.provider || "not configured")}</strong>
          · Recommended: Gemini 2.0 Flash
          · ${aiStatus.available ? "Ready" : aiStatus.provider_configured ? "Enable for this business below" : "Add GEMINI_API_KEY to backend .env"}
        </p>`;
      document.getElementById("ai-assist-panel")?.toggleAttribute("hidden", !aiStatus.available);
    } catch {
      panel.innerHTML = `<p class="muted">Could not load AI status.</p>`;
    }
  }

  async function saveAiToggle(enabled) {
    await apiFetch("/ai/settings", {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    });
    await loadAiStatus();
  }

  async function loadTemplateList() {
    const tbody = document.getElementById("hr-templates-body");
    if (!tbody) return;
    try {
      const res = await apiFetch("/hr-templates");
      if (!res.ok) throw new Error("Load failed");
      const data = await res.json();
      listCache = data.items || [];
      renderUpdatesBanner(data);
      renderTableBody(tbody, {
        emptyMessage: "No HR templates seeded. Run scripts/seed_hr_templates.py.",
        columns: [
          {
            key: "title",
            render: (r) =>
              `<strong>${escapeHtml(r.display_title)}</strong><div class="muted">${escapeHtml(r.description)}</div>`,
          },
          { key: "category", render: (r) => escapeHtml(categoryLabel(r.category)) },
          {
            key: "version",
            render: (r) =>
              `<div>Platform v${escapeHtml(r.platform_version)}</div>
               <div style="margin-top:0.25rem;">${syncStatusPill(r)}</div>
               ${r.change_summary && !r.is_customised ? `<div class="muted" style="margin-top:0.25rem;font-size:0.85rem;">${escapeHtml(r.change_summary)}</div>` : ""}`,
          },
          {
            key: "actions",
            render: (r) =>
              `<div class="table-actions">
                <button type="button" class="btn ghost" data-open="${escapeHtml(r.id)}">Edit</button>
                <button type="button" class="btn ghost" data-dl-platform="${escapeHtml(r.id)}" title="Latest ShiftSwift HR version">Latest</button>
                ${r.is_customised ? `<button type="button" class="btn ghost" data-dl-effective="${escapeHtml(r.id)}" title="Your organisation copy">My copy</button>` : ""}
              </div>`,
          },
        ],
        rows: listCache,
      });

      tbody.querySelectorAll("[data-open]").forEach((btn) => {
        btn.addEventListener("click", () => openEditor(btn.dataset.open));
      });
      tbody.querySelectorAll("[data-dl-platform]").forEach((btn) => {
        btn.addEventListener("click", () =>
          downloadAuthenticated(`/hr-templates/${btn.dataset.dlPlatform}/download?variant=platform`, `${btn.dataset.dlPlatform}.md`)
        );
      });
      tbody.querySelectorAll("[data-dl-effective]").forEach((btn) => {
        btn.addEventListener("click", () =>
          downloadAuthenticated(`/hr-templates/${btn.dataset.dlEffective}/download?variant=effective`, `${btn.dataset.dlEffective}.md`)
        );
      });
    } catch {
      renderTableBody(tbody, {
        columns: [{ key: "a" }, { key: "b" }, { key: "c" }, { key: "d" }],
        rows: [],
        emptyMessage: "Could not load templates.",
      });
    }
  }

  function renderEditorMeta(tpl) {
    const meta = document.getElementById("template-editor-meta");
    const legal = document.getElementById("template-legal-meta");
    const notice = document.getElementById("template-update-notice");
    const applyBtn = document.getElementById("template-apply-update-btn");
    const dlMy = document.getElementById("template-download-btn");
    const dlPlatform = document.getElementById("template-download-platform-btn");

    if (meta) {
      if (tpl.is_customised) {
        meta.textContent = `Your copy · based on platform v${tpl.based_on_platform_version || "?"} · platform latest is v${tpl.platform_version}`;
      } else {
        meta.textContent = `Using platform latest v${tpl.platform_version}${tpl.published_at ? ` · published ${tpl.published_at.slice(0, 10)}` : ""}`;
      }
    }

    if (legal) {
      const parts = [];
      if (tpl.legal_basis) parts.push(`<strong>Legal / guidance:</strong> ${escapeHtml(tpl.legal_basis)}`);
      if (tpl.change_summary) parts.push(`<strong>Latest change:</strong> ${escapeHtml(tpl.change_summary)}`);
      legal.innerHTML = parts.join("<br />");
    }

    if (notice && applyBtn) {
      if (tpl.update_available) {
        notice.hidden = false;
        notice.className = "promo-result promo-result-message";
        notice.innerHTML = `<p>Platform update <strong>v${escapeHtml(tpl.platform_version)}</strong> is available.
          ${escapeHtml(tpl.change_summary || "Review the platform latest before applying.")}</p>`;
        applyBtn.hidden = false;
      } else {
        notice.hidden = true;
        notice.innerHTML = "";
        applyBtn.hidden = true;
      }
    }

    if (dlMy) dlMy.hidden = !tpl.is_customised;
    if (dlPlatform) dlPlatform.hidden = false;

    const revPanel = document.getElementById("template-revisions-panel");
    const revList = document.getElementById("template-revisions-list");
    const revisions = tpl.revisions || [];
    if (revPanel && revList) {
      if (revisions.length) {
        revPanel.hidden = false;
        revList.innerHTML = revisions
          .map(
            (rev) =>
              `<li><strong>v${escapeHtml(rev.version)}</strong>${rev.published_at ? ` · ${escapeHtml(rev.published_at.slice(0, 10))}` : ""}
              ${rev.change_summary ? `: ${escapeHtml(rev.change_summary)}` : ""}</li>`
          )
          .join("");
      } else {
        revPanel.hidden = true;
        revList.innerHTML = "";
      }
    }
  }

  async function openEditor(templateId) {
    selectedId = templateId;
    const panel = document.getElementById("template-editor-panel");
    if (!panel) return;
    panel.hidden = false;
    const res = await apiFetch(`/hr-templates/${templateId}`);
    const tpl = await res.json();
    if (!res.ok) {
      alert(tpl.detail || "Could not load template");
      return;
    }
    document.getElementById("template-editor-title").textContent = tpl.title;
    document.getElementById("template-title-input").value = tpl.title;
    document.getElementById("template-body-input").value = tpl.content_markdown;
    document.getElementById("ai-template-id").value = templateId;
    renderEditorMeta(tpl);
  }

  async function saveTemplate() {
    if (!selectedId) return;
    const title = document.getElementById("template-title-input").value;
    const content = document.getElementById("template-body-input").value;
    const status = document.getElementById("template-save-status");
    if (status) status.textContent = "Saving…";
    const res = await apiFetch(`/hr-templates/${selectedId}`, {
      method: "PUT",
      body: JSON.stringify({ title, content_markdown: content }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (status) status.textContent = data.detail || "Save failed";
      return;
    }
    if (status) status.textContent = "Saved.";
    await loadTemplateList();
    await openEditor(selectedId);
  }

  async function applyPlatformUpdate() {
    if (!selectedId) return;
    if (
      !window.confirm(
        "Replace your custom text with the latest platform template? You can still reset or edit afterwards."
      )
    ) {
      return;
    }
    const res = await apiFetch(`/hr-templates/${selectedId}/apply-platform-update`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Update failed");
      return;
    }
    await loadTemplateList();
    await openEditor(selectedId);
  }

  async function resetTemplate() {
    if (!selectedId || !window.confirm("Reset to platform default? Your custom text will be removed.")) return;
    const res = await apiFetch(`/hr-templates/${selectedId}/reset`, { method: "POST" });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || "Reset failed");
      return;
    }
    await loadTemplateList();
    await openEditor(selectedId);
  }

  async function runAiDraft() {
    const prompt = document.getElementById("ai-prompt-input").value.trim();
    const context = document.getElementById("ai-context-input").value.trim();
    const existing = document.getElementById("template-body-input").value;
    const status = document.getElementById("ai-draft-status");
    if (!prompt) {
      if (status) status.textContent = "Enter a brief for the AI.";
      return;
    }
    if (status) status.textContent = "Generating…";
    const res = await apiFetch("/ai/draft-document", {
      method: "POST",
      body: JSON.stringify({
        prompt,
        template_id: selectedId || document.getElementById("ai-template-id").value || null,
        business_context: context || null,
        existing_draft: existing || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      if (status) status.textContent = data.detail || "AI request failed";
      return;
    }
    document.getElementById("template-body-input").value = data.content_markdown;
    if (status) status.textContent = `${data.disclaimer} (${data.provider}/${data.model})`;
  }

  function bindControls() {
    document.getElementById("ai-tenant-toggle")?.addEventListener("change", (e) => {
      saveAiToggle(e.target.checked).catch((err) => alert(err.message));
    });
    document.getElementById("template-save-btn")?.addEventListener("click", () => saveTemplate());
    document.getElementById("template-reset-btn")?.addEventListener("click", () => resetTemplate());
    document.getElementById("template-apply-update-btn")?.addEventListener("click", () => applyPlatformUpdate());
    document.getElementById("template-download-btn")?.addEventListener("click", () => {
      if (selectedId) {
        downloadAuthenticated(`/hr-templates/${selectedId}/download?variant=effective`, `${selectedId}.md`);
      }
    });
    document.getElementById("template-download-platform-btn")?.addEventListener("click", () => {
      if (selectedId) {
        downloadAuthenticated(`/hr-templates/${selectedId}/download?variant=platform`, `${selectedId}.md`);
      }
    });
    document.getElementById("ai-draft-btn")?.addEventListener("click", () => runAiDraft());
    document.getElementById("template-editor-close")?.addEventListener("click", () => {
      document.getElementById("template-editor-panel").hidden = true;
      selectedId = null;
    });
  }

  async function init() {
    bindControls();
    await loadAiStatus();
    await loadTemplateList();
  }

  window.addEventListener("admin:section", (event) => {
    if (event.detail?.section === "templates" && !ready) {
      ready = true;
      init();
    }
  });

  if (parseHashBaseSection(window.location.hash) === "templates") {
    ready = true;
    init();
  }
})();
