document.addEventListener("DOMContentLoaded", () => {
  const isHomePage =
    window.location.pathname === "/" ||
    window.location.pathname === "/courses/DSA/" ||
    window.location.pathname.endsWith("/courses/DSA/index.html");

  if (!isHomePage) return;

  setTimeout(() => {
    const table = document.querySelector("main table");

    if (!table) return;

    const rows = table.querySelectorAll("tbody tr");

    if (!rows.length) return;

    const lastRow = rows[rows.length - 1];

    lastRow.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });
  }, 1500);
});