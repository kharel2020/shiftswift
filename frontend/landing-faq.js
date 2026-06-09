/** FAQ accordion — manual toggle so answers always show when expanded. */
(function () {
  const items = document.querySelectorAll("#faq .faq-item");
  if (!items.length) return;

  function setOpen(details, open) {
    const summary = details.querySelector("summary");
    const answer = details.querySelector(".faq-item__answer");
    if (!summary || !answer) return;

    if (open) {
      details.setAttribute("open", "");
    } else {
      details.removeAttribute("open");
    }

    details.classList.toggle("is-open", open);
    answer.hidden = !open;
    answer.style.display = open ? "block" : "none";
    summary.setAttribute("aria-expanded", open ? "true" : "false");
  }

  items.forEach((details) => {
    const summary = details.querySelector("summary");
    if (!summary) return;

    summary.setAttribute("role", "button");
    summary.setAttribute("aria-expanded", "false");

    summary.addEventListener("click", (event) => {
      event.preventDefault();
      const willOpen = !details.classList.contains("is-open");
      items.forEach((other) => {
        if (other !== details) setOpen(other, false);
      });
      setOpen(details, willOpen);
    });

    setOpen(details, false);
  });
})();
