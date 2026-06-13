(function () {
  "use strict";

  function parseHashSection(rawHash, defaultSection) {
    const section = (rawHash.replace("#", "") || defaultSection).split("/")[0];
    return section || defaultSection;
  }

  let sidebarCtl = null;

  function initSidebar(options = {}) {
    if (sidebarCtl) return sidebarCtl;

    const toggle = document.getElementById(options.toggleId || "sidebar-toggle");
    const closeBtn = document.getElementById(options.closeId || "sidebar-close");
    const sidebar = document.querySelector(options.sidebarSelector || ".sidebar");
    const overlay = document.getElementById(options.overlayId || "sidebar-overlay");

    function setExpanded(open) {
      toggle?.setAttribute("aria-expanded", open ? "true" : "false");
      overlay?.setAttribute("aria-hidden", open ? "false" : "true");
    }

    function closeSidebar() {
      sidebar?.classList.remove("sidebar--open");
      overlay?.classList.remove("sidebar-overlay--visible");
      document.body.classList.remove("no-scroll");
      setExpanded(false);
    }

    function openSidebar() {
      sidebar?.classList.add("sidebar--open");
      overlay?.classList.add("sidebar-overlay--visible");
      document.body.classList.add("no-scroll");
      setExpanded(true);
    }

    toggle?.addEventListener("click", () => {
      if (sidebar?.classList.contains("sidebar--open")) closeSidebar();
      else openSidebar();
    });
    closeBtn?.addEventListener("click", closeSidebar);
    overlay?.addEventListener("click", closeSidebar);
    window.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeSidebar();
    });

    sidebarCtl = {
      openSidebar,
      closeSidebar,
      isOpen: () => Boolean(sidebar?.classList.contains("sidebar--open")),
    };
    return sidebarCtl;
  }

  function scrollToAnchor(anchorId) {
    if (!anchorId) return;
    const el = document.getElementById(anchorId);
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function initBottomTabs(options = {}) {
    const bar = document.getElementById(options.barId || "mobile-tab-bar");
    if (!bar) return;

    const resolveSection =
      options.resolveSection ||
      ((rawHash) => {
        const section = parseHashSection(rawHash, "overview");
        if (section.startsWith("compliance")) return "compliance";
        if (section === "overview-actions") return "overview";
        return section;
      });

    function syncActive() {
      const section = resolveSection(window.location.hash);
      bar.querySelectorAll("[data-section]").forEach((tab) => {
        tab.classList.toggle("mobile-tab--active", tab.dataset.section === section);
      });
    }

    bar.querySelectorAll("[data-section]").forEach((tab) => {
      tab.addEventListener("click", (event) => {
        event.preventDefault();
        window.location.hash = tab.dataset.section;
      });
    });

    document.getElementById("mobile-tab-more")?.addEventListener("click", () => {
      sidebarCtl?.openSidebar?.();
    });

    document.getElementById("topbar-alerts-btn")?.addEventListener("click", () => {
      if (resolveSection(window.location.hash) !== "overview") {
        window.location.hash = "overview";
        window.setTimeout(() => scrollToAnchor("overview-actions"), 120);
      } else {
        scrollToAnchor("overview-actions");
      }
    });

    window.addEventListener("admin:section", syncActive);
    window.addEventListener("hashchange", syncActive);
    syncActive();
  }

  function linkSectionId(link, defaultSection) {
    if (link.dataset.section) return link.dataset.section;
    const href = link.getAttribute("href") || "";
    if (href.startsWith("#")) {
      return href.slice(1).split("/")[0] || defaultSection;
    }
    return null;
  }

  function initHashSections(options) {
    const defaultSection = options.defaultSection || "overview";
    const sectionSelector = options.sectionSelector || ".admin-section";
    const linkSelector = options.linkSelector || ".nav-link";
    const sectionEvent = options.sectionEvent || null;
    const resolveSection = options.resolveSection || null;
    const sidebar = options.sidebar || null;

    const sections = [...document.querySelectorAll(sectionSelector)];
    const links = [...document.querySelectorAll(linkSelector)];

    function showSection(sectionId) {
      const exists = sections.some((section) => section.id === sectionId);
      const target = exists ? sectionId : defaultSection;

      sections.forEach((section) => {
        const active = section.id === target;
        section.hidden = !active;
        section.classList.toggle("admin-section--active", active);
      });

      links.forEach((link) => {
        const id = linkSectionId(link, defaultSection);
        if (id) link.classList.toggle("active", id === target);
      });

      if (sidebar?.isOpen?.()) sidebar.closeSidebar();

      if (sectionEvent) {
        window.dispatchEvent(new CustomEvent(sectionEvent, { detail: { section: target } }));
      }

      return target;
    }

    function routeFromHash() {
      const rawHash = window.location.hash;
      let sectionId = parseHashSection(rawHash, defaultSection);
      if (typeof resolveSection === "function") {
        sectionId = resolveSection(rawHash) || defaultSection;
      }
      const target = showSection(sectionId);
      const path = rawHash.replace("#", "");
      if (!sections.some((section) => section.id === sectionId) && path !== target) {
        window.location.hash = target;
      }
    }

    links.forEach((link) => {
      const id = linkSectionId(link, defaultSection);
      if (!id) return;
      link.addEventListener("click", (event) => {
        event.preventDefault();
        window.location.hash = id;
      });
    });

    window.addEventListener("hashchange", routeFromHash);
    routeFromHash();
  }

  window.MobileShell = {
    initSidebar,
    initBottomTabs,
    initHashSections,
    parseHashSection,
    scrollToAnchor,
  };
})();
