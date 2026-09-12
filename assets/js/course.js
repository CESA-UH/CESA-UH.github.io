(function () {
  function currentLang() {
    return document.documentElement.lang === "en" ? "en" : "fa";
  }

  function text(item, lang) {
    return lang === "fa" ? item.title_fa : item.title_en;
  }

  function renderResourceList(container, items, lang) {
    container.innerHTML = "";
    if (!items || items.length === 0) {
      var p = document.createElement("p");
      p.className = "placeholder";
      p.textContent = lang === "fa" ? "به‌زودی" : "Coming soon";
      container.appendChild(p);
      return;
    }
    var ul = document.createElement("ul");
    ul.className = "resource-list";
    items.forEach(function (item) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = item.href;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = text(item, lang);
      li.appendChild(a);
      ul.appendChild(li);
    });
    container.appendChild(ul);
  }

  function renderSchedule(data, lang) {
    var wrap = document.getElementById("schedule-section-body");
    if (!wrap) return;
    wrap.innerHTML = "";

    if (!data.schedule || data.schedule.length === 0) {
      var p = document.createElement("p");
      p.className = "placeholder";
      p.textContent = lang === "fa" ? "به‌زودی" : "Coming soon";
      wrap.appendChild(p);
      return;
    }

    var todayIso = new Date().toISOString().slice(0, 10);

    function linkCell(item) {
      var td = document.createElement("td");
      if (item && item.href) {
        var a = document.createElement("a");
        a.href = item.href;
        a.target = "_blank";
        a.rel = "noopener";
        a.textContent = text(item, lang);
        td.appendChild(a);
      } else {
        td.textContent = "—";
      }
      return td;
    }

    var table = document.createElement("table");
    table.className = "schedule-table";

    var thead = document.createElement("thead");
    var headRow = document.createElement("tr");
    [
      lang === "fa" ? "هفته" : "Week",
      lang === "fa" ? "جلسه" : "Session",
      lang === "fa" ? "تاریخ" : "Date",
      lang === "fa" ? "موضوع" : "Topic",
      lang === "fa" ? "منابع" : "Resources",
      lang === "fa" ? "تمرین" : "Homework",
      lang === "fa" ? "ددلاین" : "Deadline"
    ].forEach(function (label) {
      var th = document.createElement("th");
      th.textContent = label;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    var tbody = document.createElement("tbody");
    data.schedule.forEach(function (row, index) {
      var tr = document.createElement("tr");
      if (row.date === todayIso) tr.classList.add("is-today");

      var weekTd = document.createElement("td");
      weekTd.className = "schedule-week";
      weekTd.textContent = row.week != null ? row.week : "—";
      tr.appendChild(weekTd);

      var sessionTd = document.createElement("td");
      sessionTd.className = "schedule-session";
      sessionTd.textContent = row.session != null ? row.session : index + 1;
      tr.appendChild(sessionTd);

      var dateTd = document.createElement("td");
      dateTd.className = "schedule-date";
      dateTd.textContent = row.date && window.ECEJalali
        ? window.ECEJalali.formatScheduleDate(row.date, lang)
        : (row.date || "—");
      tr.appendChild(dateTd);

      var titleTd = document.createElement("td");
      titleTd.textContent = text(row, lang);
      tr.appendChild(titleTd);

      var materialsTd = document.createElement("td");
      if (row.materials && row.materials.length) {
        row.materials.forEach(function (m, materialIndex) {
          var a = document.createElement("a");
          a.href = m.href;
          a.target = "_blank";
          a.rel = "noopener";
          a.textContent = text(m, lang);
          materialsTd.appendChild(a);
          if (materialIndex < row.materials.length - 1) {
            materialsTd.appendChild(document.createTextNode("، "));
          }
        });
      } else {
        materialsTd.textContent = "—";
      }
      tr.appendChild(materialsTd);

      tr.appendChild(linkCell(row.homework));

      var deadlineTd = document.createElement("td");
      deadlineTd.className = "schedule-deadline";
      deadlineTd.textContent = row.deadline && window.ECEJalali
        ? window.ECEJalali.formatScheduleDate(row.deadline, lang)
        : (row.deadline || "—");
      tr.appendChild(deadlineTd);

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    var scrollWrap = document.createElement("div");
    scrollWrap.className = "table-scroll";
    scrollWrap.appendChild(table);
    wrap.appendChild(scrollWrap);
  }

  function renderVideos(data, lang) {
    var wrap = document.getElementById("video-section-body");
    wrap.innerHTML = "";

    if (!data.videos || data.videos.length === 0) {
      var p = document.createElement("p");
      p.className = "placeholder";
      p.textContent = lang === "fa" ? "به‌زودی" : "Coming soon";
      wrap.appendChild(p);
      return;
    }

    var playerWrap = document.createElement("div");
    playerWrap.className = "player-wrap";

    var left = document.createElement("div");
    var player = document.createElement("video");
    player.id = "player";
    player.controls = true;
    player.src = data.videos[0].src;

    var download = document.createElement("a");
    download.className = "download-link";
    download.href = data.videos[0].src;
    download.setAttribute("download", "");
    download.textContent = lang === "fa" ? "دانلود ویدیو" : "Download video";

    left.appendChild(player);
    left.appendChild(download);

    var right = document.createElement("ul");
    right.className = "session-list";

    data.videos.forEach(function (video, index) {
      var li = document.createElement("li");
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = text(video, lang);
      if (index === 0) btn.classList.add("active");
      btn.addEventListener("click", function () {
        player.src = video.src;
        player.play();
        download.href = video.src;
        right.querySelectorAll("button").forEach(function (b) {
          b.classList.remove("active");
        });
        btn.classList.add("active");
      });
      li.appendChild(btn);
      right.appendChild(li);
    });

    playerWrap.appendChild(left);
    playerWrap.appendChild(right);
    wrap.appendChild(playerWrap);
  }

  function renderAll(data) {
    var lang = currentLang();
    renderSchedule(data, lang);
    renderVideos(data, lang);
    renderResourceList(document.getElementById("notes-section-body"), data.notes, lang);
    renderResourceList(document.getElementById("exercises-section-body"), data.exercises, lang);
    renderResourceList(document.getElementById("code-section-body"), data.code, lang);
  }

  document.addEventListener("DOMContentLoaded", function () {
    fetch("./data.json")
      .then(function (res) { return res.json(); })
      .then(function (data) {
        window.__courseData = data;
        renderAll(data);
      })
      .catch(function () {
        renderAll({ schedule: [], videos: [], notes: [], exercises: [], code: [] });
      });
  });

  document.addEventListener("langchange", function () {
    if (window.__courseData) renderAll(window.__courseData);
  });
})();
