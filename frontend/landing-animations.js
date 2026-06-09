(function () {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function revealAll(nodes) {
    nodes.forEach((node) => node.classList.add("is-visible"));
  }

  const revealRoots = document.querySelectorAll(".reveal, .reveal-stagger");
  if (reduced) {
    revealAll(revealRoots);
    return;
  }

  document.documentElement.classList.add("motion-ready");

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    { root: null, rootMargin: "0px 0px -8% 0px", threshold: 0.12 }
  );

  revealRoots.forEach((node) => observer.observe(node));

  const counter = document.querySelector("[data-count-up]");
  if (counter) {
    const target = Number(counter.dataset.countUp || counter.textContent);
    if (Number.isFinite(target)) {
      const counterObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            counterObserver.disconnect();
            const duration = 900;
            const start = performance.now();
            const tick = (now) => {
              const progress = Math.min((now - start) / duration, 1);
              const eased = 1 - Math.pow(1 - progress, 3);
              counter.textContent = String(Math.round(target * eased));
              if (progress < 1) requestAnimationFrame(tick);
            };
            requestAnimationFrame(tick);
          });
        },
        { threshold: 0.5 }
      );
      counterObserver.observe(counter);
    }
  }
})();
