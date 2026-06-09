/**
 * Shared subscription pricing — platform HR + optional payroll add-ons
 */
(function () {
  function resolveApiBase() {
    if (window.ShiftSwiftBrand?.resolveApiBase) return window.ShiftSwiftBrand.resolveApiBase();
    if (window.ShiftSwiftBrand?.getApiBase) return window.ShiftSwiftBrand.getApiBase();
    return localStorage.getItem("apiBaseUrl") || "http://localhost:3000";
  }

  const API_BASE = resolveApiBase();

  const FALLBACK_PLATFORM_PLANS = [
    {
      id: "site_starter_monthly",
      name: "Starter",
      description: "Up to 15 staff at one site.",
      billing_interval: "month",
      max_employees: 15,
      price_gbp_ex_vat: 29,
      price_gbp_inc_vat: 34.8,
      features: [
        "Employee records",
        "Right-to-work checks",
        "Document storage",
        "Rota builder",
        "Self-service portal",
        "Email support",
      ],
    },
    {
      id: "site_medium_monthly",
      name: "Growth",
      description: "Up to 40 staff at one site.",
      billing_interval: "month",
      max_employees: 40,
      price_gbp_ex_vat: 59,
      price_gbp_inc_vat: 70.8,
      features: [
        "Everything in Starter",
        "Day-9 absence alerts",
        "Sponsor licence compliance",
        "Home Office audit export",
        "Grievance workflows",
        "SMS alerts · Priority support",
      ],
    },
    {
      id: "site_growth_monthly",
      name: "Scale",
      description: "Up to 100 staff at one site.",
      billing_interval: "month",
      max_employees: 100,
      price_gbp_ex_vat: 99,
      price_gbp_inc_vat: 118.8,
      features: [
        "Everything in Growth",
        "Multi-site dashboard",
        "Custom onboarding workflows",
        "API access",
        "Dedicated account manager",
      ],
    },
    {
      id: "site_starter_annual",
      name: "Starter (annual)",
      description: "Up to 15 staff. Save £58 vs monthly.",
      billing_interval: "year",
      max_employees: 15,
      price_gbp_ex_vat: 290,
      price_gbp_inc_vat: 348,
      features: [
        "Employee records",
        "Right-to-work checks",
        "Document storage",
        "Rota builder",
        "Self-service portal",
        "Email support",
      ],
    },
    {
      id: "site_medium_annual",
      name: "Growth (annual)",
      description: "Up to 40 staff. Save £118 vs monthly.",
      billing_interval: "year",
      max_employees: 40,
      price_gbp_ex_vat: 590,
      price_gbp_inc_vat: 708,
      features: [
        "Everything in Starter",
        "Day-9 absence alerts",
        "Sponsor licence compliance",
        "Home Office audit export",
        "Grievance workflows",
        "SMS alerts · Priority support",
      ],
    },
    {
      id: "site_growth_annual",
      name: "Scale (annual)",
      description: "Up to 100 staff. Save £198 vs monthly.",
      billing_interval: "year",
      max_employees: 100,
      price_gbp_ex_vat: 990,
      price_gbp_inc_vat: 1188,
      features: [
        "Everything in Growth",
        "Multi-site dashboard",
        "Custom onboarding workflows",
        "API access",
        "Dedicated account manager",
      ],
    },
  ];

  const FALLBACK_PAYROLL_PLANS = [
    {
      id: "payroll_starter_monthly",
      name: "1–10 employees",
      description: "Pay cycles, payslips, HMRC RTI, P60/P45 generation.",
      billing_interval: "month",
      max_employees: 10,
      price_gbp_ex_vat: 19,
      price_gbp_inc_vat: 22.8,
      features: ["HMRC RTI submissions", "Payslips & P60s", "P45 generation"],
    },
    {
      id: "payroll_standard_monthly",
      name: "11–25 employees",
      description: "All Starter features plus auto-enrolment pension reporting.",
      billing_interval: "month",
      max_employees: 25,
      price_gbp_ex_vat: 35,
      price_gbp_inc_vat: 42,
      features: ["Everything in 1–10 band", "Auto-enrolment pension reporting"],
    },
    {
      id: "payroll_growth_monthly",
      name: "26–50 employees",
      description: "All Standard features plus multi-site payroll runs.",
      billing_interval: "month",
      max_employees: 50,
      price_gbp_ex_vat: 55,
      price_gbp_inc_vat: 66,
      features: ["Everything in 11–25 band", "Multi-site payroll runs"],
    },
    {
      id: "payroll_scale_monthly",
      name: "51–100 employees",
      description: "All Growth features plus dedicated payroll support line.",
      billing_interval: "month",
      max_employees: 100,
      price_gbp_ex_vat: 85,
      price_gbp_inc_vat: 102,
      features: ["Everything in 26–50 band", "Dedicated payroll support line"],
    },
  ];

  let cachedCatalog = null;

  function formatMoney(value) {
    return Number(value).toFixed(2).replace(/\.00$/, "");
  }

  function intervalLabel(interval) {
    return interval === "year" ? "/ year" : "/ month";
  }

  function isFeatured(plan) {
    return plan.id === "site_medium_monthly" || plan.id === "site_medium_annual";
  }

  function plansForBillingInterval(plans, billing) {
    const monthly = plans.filter((p) => p.billing_interval === "month");
    if (billing === "month") return monthly;

    const annualByCap = Object.fromEntries(
      plans.filter((p) => p.billing_interval === "year").map((p) => [p.max_employees, p])
    );

    return monthly.map((plan) => {
      const existing = annualByCap[plan.max_employees];
      if (existing) return existing;
      const annualPrice = Math.round(plan.price_gbp_ex_vat * 10 * 100) / 100;
      return {
        ...plan,
        id: plan.id.replace("_monthly", "_annual"),
        name: `${plan.name} (annual)`,
        billing_interval: "year",
        price_gbp_ex_vat: annualPrice,
        price_gbp_inc_vat: Math.round(annualPrice * 1.2 * 100) / 100,
        description: `${plan.description} Billed annually (2 months free vs monthly).`,
      };
    });
  }

  function suggestedPayrollPlan(platformPlanId, payrollPlans) {
    const platform = (cachedCatalog?.platform_plans || FALLBACK_PLATFORM_PLANS).find(
      (p) => p.id === platformPlanId
    );
    if (!platform) return null;
    const match = payrollPlans.find((p) => p.max_employees >= platform.max_employees);
    return match?.id || payrollPlans[payrollPlans.length - 1]?.id || null;
  }

  async function fetchCatalog() {
    if (cachedCatalog) return cachedCatalog;
    try {
      const res = await fetch(`${API_BASE}/billing/plans`);
      if (!res.ok) throw new Error("API unavailable");
      const data = await res.json();
      const platform = (data.platform_plans || data.plans || []).filter(
        (item) => item.id && item.name && item.price_gbp_ex_vat != null
      );
      const payroll = (data.payroll_plans || []).filter(
        (item) => item.id && item.name && item.price_gbp_ex_vat != null
      );
      cachedCatalog = {
        platform_plans: platform.length ? platform : FALLBACK_PLATFORM_PLANS,
        payroll_plans: payroll.length ? payroll : FALLBACK_PAYROLL_PLANS,
      };
    } catch {
      cachedCatalog = {
        platform_plans: FALLBACK_PLATFORM_PLANS,
        payroll_plans: FALLBACK_PAYROLL_PLANS,
      };
    }
    return cachedCatalog;
  }

  async function fetchPlans() {
    const catalog = await fetchCatalog();
    return catalog.platform_plans;
  }

  function planCardHtml(plan, options) {
    const mode = options.mode || "marketing";
    const cardType = options.cardType || "platform";
    const selected =
      cardType === "payroll"
        ? options.selectedPayrollPlanId === plan.id
        : options.selectedPlanId === plan.id;
    const featured = cardType === "platform" && isFeatured(plan);
    const interval = intervalLabel(plan.billing_interval);
    const exVat = formatMoney(plan.price_gbp_ex_vat);
    const incVat = formatMoney(plan.price_gbp_inc_vat || plan.price_gbp_ex_vat * 1.2);

    let actions = "";
    if (mode === "marketing") {
      const query =
        cardType === "payroll"
          ? `plan=${encodeURIComponent(options.platformPlanId || "site_starter_monthly")}&payroll=${encodeURIComponent(plan.id)}`
          : `plan=${encodeURIComponent(plan.id)}`;
      actions = `
        <div class="pricing-card-actions">
          <a class="btn" href="./signup.html?${query}">Start 14-day trial</a>
          <a class="pricing-link-cta" href="./signup.html?${query}&amp;subscribe=1">Subscribe now</a>
        </div>`;
    } else if (cardType === "payroll") {
      actions = `
        <div class="pricing-card-actions">
          <button type="button" class="btn ${selected ? "" : "ghost"}" data-select-payroll="${plan.id}">
            ${selected ? "Selected" : "Add payroll"}
          </button>
        </div>`;
    } else {
      actions = `
        <div class="pricing-card-actions">
          <button type="button" class="btn ${selected ? "" : "ghost"}" data-select-plan="${plan.id}">
            ${selected ? "Selected" : "Select plan"}
          </button>
        </div>`;
    }

    return `
      <article class="pricing-card ${featured ? "is-featured" : ""} ${selected ? "is-selected" : ""} pricing-card--${cardType}"
               data-plan-id="${plan.id}" data-card-type="${cardType}">
        <div class="pricing-card-head">
          ${featured ? '<span class="pricing-badge">Most popular</span>' : ""}
          ${cardType === "payroll" ? '<span class="pricing-badge pricing-badge--payroll">Payroll add-on</span>' : ""}
          ${plan.billing_interval === "year" ? '<span class="pricing-badge pricing-badge--muted">Save 2 months</span>' : ""}
          <div class="pricing-plan-name">${plan.name}</div>
          <p class="pricing-plan-desc">${plan.description}</p>
        </div>
        <div class="pricing-amount">
          <span class="currency">£</span>
          <span class="value">${exVat}</span>
          <span class="interval">+ VAT ${interval}</span>
        </div>
        <p class="pricing-vat"><strong>£${incVat}</strong> inc. 20% VAT ${interval.replace("/", "per")}</p>
        <p class="pricing-staff-cap">Up to ${plan.max_employees} employees · one site</p>
        <ul class="pricing-features">
          ${(plan.features || []).map((f) => `<li>${f}</li>`).join("")}
        </ul>
        ${actions}
      </article>`;
  }

  function payrollSkipCardHtml(selected, mode) {
    if (mode !== "selectable") return "";
    return `
      <article class="pricing-card pricing-card--payroll pricing-card--skip ${selected ? "is-selected" : ""}"
               data-plan-id="" data-card-type="payroll-skip">
        <div class="pricing-card-head">
          <div class="pricing-plan-name">HR only</div>
          <p class="pricing-plan-desc">Platform subscription without payroll processing.</p>
        </div>
        <div class="pricing-amount">
          <span class="value" style="font-size:1.5rem;">£0</span>
          <span class="interval">payroll add-on</span>
        </div>
        <p class="pricing-staff-cap">Add payroll later from admin billing</p>
        <div class="pricing-card-actions">
          <button type="button" class="btn ${selected ? "" : "ghost"}" data-select-payroll="">
            ${selected ? "Selected" : "No payroll"}
          </button>
        </div>
      </article>`;
  }

  function renderPlans(container, plans, options) {
    if (!container) return;
    container.innerHTML = plans.map((plan) => planCardHtml(plan, options)).join("");

    if (options.mode === "selectable" && options.cardType !== "payroll") {
      container.querySelectorAll("[data-select-plan]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const planId = btn.getAttribute("data-select-plan");
          if (options.onSelect) options.onSelect(planId);
          renderPlans(container, plans, { ...options, selectedPlanId: planId });
        });
      });
    }
  }

  function renderPayrollPlans(container, plans, options) {
    if (!container) return;
    const skipSelected = !options.selectedPayrollPlanId;
    container.innerHTML =
      payrollSkipCardHtml(skipSelected, options.mode) +
      plans.map((plan) => planCardHtml(plan, options)).join("");

    if (options.mode === "selectable") {
      container.querySelectorAll("[data-select-payroll]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const planId = btn.getAttribute("data-select-payroll") || "";
          if (options.onPayrollSelect) options.onPayrollSelect(planId || null);
          renderPayrollPlans(container, plans, { ...options, selectedPayrollPlanId: planId || null });
          updateSummary(options.selectedPlanId, options.platformPlans, planId || null, plans);
        });
      });
    }
  }

  function updateSummary(planId, platformPlans, payrollPlanId, payrollPlans) {
    const summary = document.getElementById("signup-plan-summary");
    if (!summary) return;
    const plan = platformPlans.find((p) => p.id === planId);
    if (!plan) {
      summary.hidden = true;
      return;
    }
    summary.hidden = false;
    summary.querySelector(".signup-summary-plan").textContent = plan.name;
    const payroll = payrollPlanId ? payrollPlans.find((p) => p.id === payrollPlanId) : null;
    let priceText = `£${formatMoney(plan.price_gbp_ex_vat)} + VAT (${intervalLabel(plan.billing_interval).trim()}) · up to ${plan.max_employees} staff`;
    if (payroll) {
      priceText += ` · + payroll £${formatMoney(payroll.price_gbp_ex_vat)} + VAT/mo`;
    }
    summary.querySelector(".signup-summary-price").textContent = priceText;

    const hiddenPlan = document.getElementById("selected-plan-id");
    if (hiddenPlan) hiddenPlan.value = plan.id;
    const hiddenPayroll = document.getElementById("selected-payroll-plan-id");
    if (hiddenPayroll) hiddenPayroll.value = payrollPlanId || "";
  }

  async function initMarketing(platformContainerId, payrollContainerId) {
    const platformContainer = document.getElementById(platformContainerId);
    const payrollContainer = payrollContainerId ? document.getElementById(payrollContainerId) : null;
    const toggle = document.getElementById("pricing-billing-toggle");
    // Marketing page uses strategy pricing — signup/billing API may lag until catalog is re-seeded.
    const catalog = {
      platform_plans: FALLBACK_PLATFORM_PLANS,
      payroll_plans: FALLBACK_PAYROLL_PLANS,
    };
    let billing = "month";

    function renderPlatformPlans() {
      if (!platformContainer) return;
      const plans = plansForBillingInterval(catalog.platform_plans, billing);
      renderPlans(platformContainer, plans, { mode: "marketing", cardType: "platform", billing });
    }

    if (platformContainer) {
      platformContainer.innerHTML = '<div class="pricing-loading">Loading plans…</div>';
      renderPlatformPlans();
    }
    if (payrollContainer) {
      payrollContainer.innerHTML = '<div class="pricing-loading">Loading payroll…</div>';
      renderPayrollPlans(payrollContainer, catalog.payroll_plans, {
        mode: "marketing",
        cardType: "payroll",
        platformPlanId: "site_starter_monthly",
      });
    }

    if (toggle) {
      toggle.querySelectorAll("[data-billing]").forEach((btn) => {
        btn.addEventListener("click", () => {
          billing = btn.getAttribute("data-billing") || "month";
          toggle.querySelectorAll("[data-billing]").forEach((el) => {
            const active = el === btn;
            el.classList.toggle("is-active", active);
            el.setAttribute("aria-pressed", active ? "true" : "false");
          });
          renderPlatformPlans();
        });
      });
    }
  }

  let currentSelectedPlan = "site_starter_monthly";
  let currentSelectedPayroll = null;

  async function initSignup(platformContainerId, payrollContainerId) {
    const platformContainer = document.getElementById(platformContainerId);
    const payrollContainer = document.getElementById(payrollContainerId);
    const params = new URLSearchParams(window.location.search);
    let selectedPlanId = params.get("plan") || "site_starter_monthly";
    let selectedPayrollPlanId = params.get("payroll") || null;
    const catalog = await fetchCatalog();

    if (!catalog.platform_plans.find((p) => p.id === selectedPlanId)) {
      selectedPlanId = catalog.platform_plans[0]?.id || "site_starter_monthly";
    }
    if (selectedPayrollPlanId && !catalog.payroll_plans.find((p) => p.id === selectedPayrollPlanId)) {
      selectedPayrollPlanId = null;
    }

    if (platformContainer) {
      platformContainer.innerHTML = '<div class="pricing-loading">Loading plans…</div>';
      const platformMonthly = catalog.platform_plans.filter((p) => p.billing_interval === "month");
      renderPlans(platformContainer, platformMonthly, {
        mode: "selectable",
        cardType: "platform",
        selectedPlanId,
        platformPlans: catalog.platform_plans,
        payrollPlans: catalog.payroll_plans,
        onSelect: (id) => {
          currentSelectedPlan = id;
          const url = new URL(window.location.href);
          url.searchParams.set("plan", id);
          window.history.replaceState({}, "", url);
          if (selectedPayrollPlanId) {
            const payroll = catalog.payroll_plans.find((p) => p.id === selectedPayrollPlanId);
            const platform = catalog.platform_plans.find((p) => p.id === id);
            if (payroll && platform && payroll.max_employees < platform.max_employees) {
              selectedPayrollPlanId = suggestedPayrollPlan(id, catalog.payroll_plans);
              currentSelectedPayroll = selectedPayrollPlanId;
              url.searchParams.set("payroll", selectedPayrollPlanId || "");
              window.history.replaceState({}, "", url);
              renderPayrollPlans(payrollContainer, catalog.payroll_plans, {
                mode: "selectable",
                cardType: "payroll",
                selectedPlanId: id,
                selectedPayrollPlanId,
                platformPlans: catalog.platform_plans,
                payrollPlans: catalog.payroll_plans,
                onPayrollSelect: (pid) => {
                  currentSelectedPayroll = pid;
                  const u = new URL(window.location.href);
                  if (pid) u.searchParams.set("payroll", pid);
                  else u.searchParams.delete("payroll");
                  window.history.replaceState({}, "", u);
                  updateSummary(id, catalog.platform_plans, pid, catalog.payroll_plans);
                },
              });
            }
          }
          updateSummary(id, catalog.platform_plans, selectedPayrollPlanId, catalog.payroll_plans);
        },
      });
    }

    if (payrollContainer) {
      payrollContainer.innerHTML = '<div class="pricing-loading">Loading payroll…</div>';
      renderPayrollPlans(payrollContainer, catalog.payroll_plans, {
        mode: "selectable",
        cardType: "payroll",
        selectedPlanId,
        selectedPayrollPlanId,
        platformPlans: catalog.platform_plans,
        payrollPlans: catalog.payroll_plans,
        onPayrollSelect: (id) => {
          currentSelectedPayroll = id;
          const url = new URL(window.location.href);
          if (id) url.searchParams.set("payroll", id);
          else url.searchParams.delete("payroll");
          window.history.replaceState({}, "", url);
          selectedPayrollPlanId = id;
          updateSummary(selectedPlanId, catalog.platform_plans, id, catalog.payroll_plans);
        },
      });
    }

    currentSelectedPlan = selectedPlanId;
    currentSelectedPayroll = selectedPayrollPlanId;
    updateSummary(selectedPlanId, catalog.platform_plans, selectedPayrollPlanId, catalog.payroll_plans);
    return {
      platformPlans: catalog.platform_plans,
      payrollPlans: catalog.payroll_plans,
      selectedPlanId,
      selectedPayrollPlanId,
    };
  }

  function refreshSummary(planId, payrollPlanId) {
    fetchCatalog().then((catalog) => {
      updateSummary(
        planId || currentSelectedPlan,
        catalog.platform_plans,
        payrollPlanId !== undefined ? payrollPlanId : currentSelectedPayroll,
        catalog.payroll_plans
      );
    });
  }

  window.ShiftSwiftPricing = {
    fetchPlans,
    fetchCatalog,
    initMarketing,
    initSignup,
    refreshSummary,
    formatMoney,
  };
})();
