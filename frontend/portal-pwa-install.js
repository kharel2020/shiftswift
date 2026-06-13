/** Top-of-page install banner for ShiftSwift HR admin and employee portal PWAs. */
(function initPortalPwaInstall() {
  const script = document.currentScript;
  const portal = script?.dataset.portal || "portal";
  const appName = script?.dataset.appName || "ShiftSwift HR";
  const manifestHref = script?.dataset.manifest || "";
  const swHref = script?.dataset.sw || "./app-sw.js?v=1";
  const dismissKey = `pwaInstallDismissed:${portal}`;

  const banner = document.getElementById("portal-pwa-install-banner");
  const titleEl = document.getElementById("portal-pwa-install-title");
  const copyEl = document.getElementById("portal-pwa-install-copy");
  const installBtn = document.getElementById("portal-pwa-install-btn");
  const dismissBtn = document.getElementById("portal-pwa-install-dismiss");

  let deferredInstallPrompt = null;

  function isStandalone() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.matchMedia("(display-mode: fullscreen)").matches ||
      window.navigator.standalone === true
    );
  }

  function isIos() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent);
  }

  function isAndroid() {
    return /Android/i.test(navigator.userAgent);
  }

  function installDismissed() {
    return localStorage.getItem(dismissKey) === "1";
  }

  function hideBanner() {
    if (banner) banner.hidden = true;
  }

  function showBanner({ copy, showInstallButton }) {
    if (!banner || isStandalone() || installDismissed()) return;
    if (titleEl) titleEl.textContent = `Download ${appName} app`;
    if (copyEl) copyEl.textContent = copy;
    if (installBtn) installBtn.hidden = !showInstallButton;
    banner.hidden = false;
  }

  function maybeShowInstallBanner() {
    if (!banner || isStandalone() || installDismissed()) return;

    if (deferredInstallPrompt) {
      showBanner({
        copy: `Install ${appName} on this device for quick access from your home screen.`,
        showInstallButton: true,
      });
      return;
    }

    if (isIos()) {
      showBanner({
        copy: `On iPhone or iPad: tap Share, then Add to Home Screen to install ${appName}.`,
        showInstallButton: false,
      });
      return;
    }

    if (isAndroid()) {
      showBanner({
        copy: `Install ${appName} from your browser menu, or tap Install app when your browser offers it.`,
        showInstallButton: false,
      });
    }
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    window.addEventListener("load", () => {
      navigator.serviceWorker.register(swHref, { scope: "./" }).catch(() => null);
    });
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    maybeShowInstallBanner();
  });

  installBtn?.addEventListener("click", async () => {
    if (!deferredInstallPrompt) return;
    deferredInstallPrompt.prompt();
    try {
      await deferredInstallPrompt.userChoice;
    } catch {
      /* ignore */
    }
    deferredInstallPrompt = null;
    hideBanner();
  });

  dismissBtn?.addEventListener("click", () => {
    localStorage.setItem(dismissKey, "1");
    hideBanner();
  });

  if (manifestHref && !document.querySelector('link[rel="manifest"]')) {
    const link = document.createElement("link");
    link.rel = "manifest";
    link.href = manifestHref;
    document.head.appendChild(link);
  }

  registerServiceWorker();
  maybeShowInstallBanner();
})();
