const year = document.querySelector("[data-year]");
if (year) year.textContent = new Date().getFullYear();

const menuButton = document.querySelector("[data-menu]");
const mobileMenu = document.querySelector("[data-mobile-menu]");
if (menuButton && mobileMenu) {
  menuButton.addEventListener("click", () => {
    const open = mobileMenu.hidden;
    mobileMenu.hidden = !open;
    menuButton.setAttribute("aria-expanded", String(open));
  });
}

const previewHost =
  "bxk-marketing-preview-production.up.railway.app";

const previewAppBase =
  "https://bxk-trader-pro-preview-production.up.railway.app";

if (window.location.hostname === previewHost) {
  document
    .querySelectorAll(
      'a[href^="https://app.bxktraderpro.com"]'
    )
    .forEach((link) => {
      const url = new URL(link.href);
      link.href =
        previewAppBase +
        url.pathname +
        url.search +
        url.hash;
    });
}
