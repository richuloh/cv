(() => {
  const tabs = document.querySelectorAll("[data-pub-tab]");
  const panels = document.querySelectorAll("[data-pub-group]");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.pubTab;
      tabs.forEach((button) => {
        const active = button.dataset.pubTab === target;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      });
      panels.forEach((panel) => {
        panel.hidden = panel.dataset.pubGroup !== target;
      });
    });
  });

  document.querySelectorAll("[data-disclosure]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const body = trigger.nextElementSibling;
      const expanded = trigger.getAttribute("aria-expanded") === "true";
      trigger.setAttribute("aria-expanded", String(!expanded));
      if (body) body.hidden = expanded;
    });
  });

  document.querySelectorAll("[data-current-year]").forEach((node) => {
    node.textContent = String(new Date().getFullYear());
  });
})();
