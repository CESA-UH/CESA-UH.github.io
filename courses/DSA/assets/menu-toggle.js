document.addEventListener("DOMContentLoaded", () => {

    if (document.querySelector(".custom-menu-toggle")) return;
  
    const header = document.querySelector(".md-header__inner");
    if (!header) return;
  
    const defaultMenuButton = document.querySelector('label[for="__drawer"]');
    if (defaultMenuButton) {
      defaultMenuButton.classList.add("hide-desktop-menu-button");
    }
  
    const button = document.createElement("button");
  
    button.className = "custom-menu-toggle";
    button.type = "button";
    button.setAttribute("aria-label", "باز و بسته کردن منو");
    button.setAttribute("aria-expanded", "true");
    button.innerHTML = "☰";
  
    header.appendChild(button);
  
    button.addEventListener("click", () => {
      const collapsed = document.body.classList.toggle("menu-collapsed");
      button.setAttribute("aria-expanded", String(!collapsed));
    });
  });

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
    }, 1000);
  });
