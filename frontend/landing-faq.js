/** FAQ accordion — ensures answers expand reliably across browsers. */
(function () {
  const items = document.querySelectorAll("#faq .faq-item");
  if (!items.length) return;

  items.forEach((details) => {
    const answer = details.querySelector(".faq-item__answer");
    if (!answer) return;

    const sync = () => {
      const open = details.open;
      answer.hidden = !open;
      answer.style.display = open ? "block" : "none";
      details.classList.toggle("is-open", open);
    };

    details.addEventListener("toggle", sync);
    sync();
  });
})();
