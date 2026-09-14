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