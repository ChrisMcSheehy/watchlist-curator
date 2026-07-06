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

  // ---- article: reading progress bar (fraction of the article scrolled past) ----
  var article = document.querySelector(".prose");
  if (article) {
    var bar = document.createElement("div");
    bar.className = "read-progress";
    document.body.appendChild(bar);
    var readout = document.getElementById("toc-read");
    var readoutPct = document.getElementById("toc-read-pct");
    if (readout) readout.hidden = false;  // only shown once JS is driving it
    var ticking = false;
    function updateProgress() {
      ticking = false;
      var start = article.offsetTop;
      var end = start + article.offsetHeight - window.innerHeight;
      var p = end > start ? (window.scrollY - start) / (end - start) : 1;
      p = Math.max(0, Math.min(1, p));
      bar.style.width = p * 100 + "%";
      if (readoutPct) readoutPct.textContent = Math.round(p * 100);
    }
    function onScroll() {
      if (!ticking) { ticking = true; requestAnimationFrame(updateProgress); }
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    updateProgress();
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
