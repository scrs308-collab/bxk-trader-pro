(() => {
  const STORAGE_KEY = "bxk-theme";
  const LIGHT = "light";
  const DARK = "dark";

  function savedTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === DARK || saved === LIGHT
      ? saved
      : LIGHT;
  }

  function updateButton(button, theme) {
    const dark = theme === DARK;

    button.textContent = dark
      ? "Light Mode"
      : "Dark Mode";

    button.setAttribute(
      "aria-label",
      dark
        ? "Switch to light mode"
        : "Switch to dark mode",
    );

    button.setAttribute(
      "aria-pressed",
      String(dark),
    );

    button.title = dark
      ? "Switch to light mode"
      : "Switch to dark mode";
  }

  function applyTheme(theme, button) {
    document.documentElement.dataset.theme = theme;
    document.body.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;

    if (button) {
      updateButton(button, theme);
    }
  }

  function initializeTheme() {
    const theme = savedTheme();
    applyTheme(theme);

    const topbar = document.querySelector(".topbar");
    const apiStatus = document.getElementById("apiStatus");

    if (!topbar || !apiStatus) {
      return;
    }

    const controls = document.createElement("div");
    controls.className = "topbar-controls";

    const button = document.createElement("button");
    button.id = "themeToggle";
    button.className = "theme-toggle";
    button.type = "button";

    apiStatus.parentNode.insertBefore(
      controls,
      apiStatus,
    );

    controls.appendChild(button);
    controls.appendChild(apiStatus);

    updateButton(button, theme);

    button.addEventListener("click", () => {
      const current =
        document.documentElement.dataset.theme;

      const next =
        current === DARK
          ? LIGHT
          : DARK;

      localStorage.setItem(STORAGE_KEY, next);
      applyTheme(next, button);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      initializeTheme,
      { once: true },
    );
  } else {
    initializeTheme();
  }
})();
