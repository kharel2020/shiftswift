/** ShiftSwift HR — client-side brand defaults (overridden in production via /setup/brand). */
window.ShiftSwiftBrand = {
  appName: "ShiftSwift HR",
  tradingName: "ShiftSwift HR",
  companyLegalName: "Datasoftware Analytics Ltd",
  companyNumber: "14568900",
  registeredAddress: "235 Charlbury Road, Nottingham, NG8 1NF",
  legalNotice:
    "ShiftSwift HR is a trading name of Datasoftware Analytics Ltd (Company No. 14568900), registered in England and Wales.",
  domain: "shiftswifthr.co.uk",
  tagline: "UK HR & sponsor licence compliance software",
  urls: {
    marketing: "https://www.shiftswifthr.co.uk",
    app: "https://app.shiftswifthr.co.uk",
    api: "https://api.shiftswifthr.co.uk",
    localApp: "http://localhost:5173",
    localApi: "http://localhost:3000",
  },
  emails: {
    hello: "support@shiftswifthr.co.uk",
    support: "support@shiftswifthr.co.uk",
    legal: "legal@shiftswifthr.co.uk",
    noreply: "noreply@shiftswifthr.co.uk",
    compliance: "compliance@shiftswifthr.co.uk",
    admin: "admin@shiftswifthr.co.uk",
    hr: "hr@shiftswifthr.co.uk",
    employee: "employee@shiftswifthr.co.uk",
  },
};

window.ShiftSwiftBrand.resolveApiBase = function resolveApiBase() {
  const host = window.location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1";
  if (isLocal) {
    return window.ShiftSwiftBrand.urls.localApi;
  }

  const stored = localStorage.getItem("apiBaseUrl");
  if (stored && !/localhost|127\.0\.0\.1/.test(stored)) {
    return stored;
  }
  if (stored) {
    localStorage.removeItem("apiBaseUrl");
  }

  if (host.startsWith("app.") || host.includes("shiftswifthr")) {
    return window.ShiftSwiftBrand.urls.api;
  }
  return window.ShiftSwiftBrand.urls.localApi;
};

window.ShiftSwiftBrand.appUrl = function appUrl(path) {
  const base = window.ShiftSwiftBrand.urls.app.replace(/\/$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
};

window.ShiftSwiftBrand.getApiBase = function getApiBase() {
  return window.ShiftSwiftBrand.resolveApiBase();
};
