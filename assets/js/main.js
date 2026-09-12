(function () {
  var STORAGE_KEY = "ece-docs-lang";
  var THEME_KEY = "ece-docs-theme";

  function currentLang() {
    return localStorage.getItem(STORAGE_KEY) || "fa";
  }

  function currentTheme() {
    return localStorage.getItem(THEME_KEY) || "light";
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
  }

  function initThemeToggle() {
    applyTheme(currentTheme());
    document.querySelectorAll(".theme-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        applyTheme(currentTheme() === "dark" ? "light" : "dark");
      });
    });
  }

  function applyLang(lang) {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "fa" ? "rtl" : "ltr";

    document.querySelectorAll("[data-fa][data-en]").forEach(function (el) {
      el.textContent = lang === "fa" ? el.dataset.fa : el.dataset.en;
    });

    document.querySelectorAll(".lang-toggle").forEach(function (btn) {
      btn.textContent = lang === "fa" ? "EN" : "فا";
    });

    localStorage.setItem(STORAGE_KEY, lang);
    document.dispatchEvent(new CustomEvent("langchange", { detail: { lang: lang } }));
  }

  function initLangToggle() {
    applyLang(currentLang());
    document.querySelectorAll(".lang-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        applyLang(currentLang() === "fa" ? "en" : "fa");
      });
    });
  }

  function initReveal() {
    var items = document.querySelectorAll(".reveal:not([data-reveal-ready])");
    items.forEach(function (el, index) {
      el.dataset.revealReady = "1";
      el.style.transitionDelay = (index % 6) * 70 + "ms";
    });

    if (!("IntersectionObserver" in window) || items.length === 0) {
      items.forEach(function (el) { el.classList.add("is-visible"); });
      return;
    }
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15 }
    );
    items.forEach(function (el) { observer.observe(el); });
  }

  function initScrollProgress() {
    var bar = document.getElementById("scroll-progress");
    if (!bar) return;
    var ticking = false;
    function update() {
      var scrollTop = window.scrollY;
      var height = document.documentElement.scrollHeight - window.innerHeight;
      var ratio = height > 0 ? scrollTop / height : 0;
      bar.style.width = Math.min(1, Math.max(0, ratio)) * 100 + "%";
      ticking = false;
    }
    window.addEventListener("scroll", function () {
      if (!ticking) {
        requestAnimationFrame(update);
        ticking = true;
      }
    });
    update();
  }

  function docsBasePath() {
    return location.pathname.indexOf("/courses/") !== -1 ? "../" : "courses/";
  }

  function currentCourseId() {
    var m = location.pathname.match(/\/courses\/([^/]+)\//);
    return m ? m[1] : null;
  }

  function initSidebarCourseList() {
    var lists = document.querySelectorAll(".sidebar-course-list");
    if (!lists.length) return;
    var base = docsBasePath();
    var activeId = currentCourseId();
    fetch(base + "index.json")
      .then(function (res) { return res.json(); })
      .then(function (courses) {
        lists.forEach(function (list) {
          list.innerHTML = "";
          courses.forEach(function (course) {
            var li = document.createElement("li");
            var a = document.createElement("a");
            a.href = base + course.id + "/index.html";
            a.dataset.fa = course.title_fa;
            a.dataset.en = course.title_en;
            if (course.id === activeId) a.classList.add("active");
            li.appendChild(a);
            list.appendChild(li);
          });
        });
        applyLang(currentLang());
      });
  }

  function initPageNavScrollSpy() {
    var links = document.querySelectorAll(".sidebar-page-nav a");
    if (!links.length) return;
    var sections = [];
    links.forEach(function (link) {
      var id = link.getAttribute("href").replace("#", "");
      var section = document.getElementById(id);
      if (section) sections.push({ link: link, section: section });
    });
    if (!sections.length || !("IntersectionObserver" in window)) return;

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          var match = sections.find(function (s) { return s.section === entry.target; });
          if (!match) return;
          if (entry.isIntersecting) {
            sections.forEach(function (s) { s.link.classList.remove("active"); });
            match.link.classList.add("active");
          }
        });
      },
      { rootMargin: "-20% 0px -70% 0px" }
    );
    sections.forEach(function (s) { observer.observe(s.section); });
  }

  function initCourseGrid() {
    var grid = document.getElementById("course-grid");
    if (!grid) return;
    fetch("courses/index.json")
      .then(function (res) { return res.json(); })
      .then(function (courses) {
        grid.innerHTML = "";
        courses.forEach(function (course) {
          var a = document.createElement("a");
          a.className = "course-card reveal";
          a.href = "courses/" + course.id + "/index.html";

          var badge = document.createElement("span");
          badge.className = "badge";
          badge.textContent = course.id.toUpperCase();

          var h3 = document.createElement("h3");
          h3.dataset.fa = course.title_fa;
          h3.dataset.en = course.title_en;

          var p = document.createElement("p");
          p.dataset.fa = course.desc_fa;
          p.dataset.en = course.desc_en;

          a.appendChild(badge);
          a.appendChild(h3);
          a.appendChild(p);
          grid.appendChild(a);
        });
        applyLang(currentLang());
        initReveal();
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initThemeToggle();
    initLangToggle();
    initReveal();
    initCourseGrid();
    initScrollProgress();
    initSidebarCourseList();
    initPageNavScrollSpy();
  });
})();
