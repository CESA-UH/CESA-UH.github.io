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