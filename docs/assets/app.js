/* theme toggle + index search/filter + article scrollspy */
(function () {
  "use strict";

  // ---- theme toggle (manual, persisted; no auto-switching) ----
  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var root = document.documentElement;
      var next = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
  }

  // ---- index: search + tag pills over search.json ----
  var searchBox = document.getElementById("search");
  var issuesEl = document.getElementById("issues");
  if (searchBox && issuesEl) {
    var index = [];
    fetch("search.json")
      .then(function (r) { return r.json(); })
      .then(function (data) { index = data; });

    var activeTags = new Set();
    var pills = Array.prototype.slice.call(document.querySelectorAll(".pill"));
    pills.forEach(function (pill) {
      pill.addEventListener("click", function () {
        var tag = pill.dataset.tag;
        if (activeTags.has(tag)) { activeTags.delete(tag); pill.classList.remove("active"); }
        else { activeTags.add(tag); pill.classList.add("active"); }
        applyFilter();
      });
    });

    searchBox.addEventListener("input", applyFilter);

    function matches(entry, q) {
      if (activeTags.size) {
        var hasAll = Array.from(activeTags).every(function (t) {
          return entry.tags.indexOf(t) !== -1;
        });
        if (!hasAll) return false;
      }
      if (!q) return true;
      var hay = (entry.title + " " + entry.summary + " " +
        entry.tags.join(" ") + " " + entry.headings.join(" ")).toLowerCase();
      return q.split(/\s+/).every(function (w) { return hay.indexOf(w) !== -1; });
    }

    function applyFilter() {
      var q = searchBox.value.trim().toLowerCase();
      var visible = 0;
      var bySlug = {};
      index.forEach(function (e) { bySlug[e.slug] = e; });
      Array.prototype.forEach.call(issuesEl.children, function (card) {
        var entry = bySlug[card.dataset.slug];
        var show = entry ? matches(entry, q) : true;
        card.hidden = !show;
        if (show) visible++;
      });
      document.getElementById("no-results").hidden = visible !== 0;
    }
  }

  // ---- article: scrollspy for the table of contents ----
  var toc = document.getElementById("toc");
  if (toc && "IntersectionObserver" in window) {
    var links = {};
    toc.querySelectorAll("a[href^='#']").forEach(function (a) {
      links[a.getAttribute("href").slice(1)] = a;
    });
    var current = null;
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          if (current) current.classList.remove("active");
          current = links[entry.target.id];
          if (current) current.classList.add("active");
        }
      });
    }, { rootMargin: "0px 0px -70% 0px" });
    document.querySelectorAll(".prose h2[id]").forEach(function (h) {
      if (links[h.id]) observer.observe(h);
    });
  }
})();
