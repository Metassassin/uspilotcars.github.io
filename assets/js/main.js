(function () {
  "use strict";

  // ---- Mobile sidebar drawer ----
  var toggle = document.querySelector("[data-menu-toggle]");
  var sidebar = document.querySelector(".sidebar");
  var scrim = document.querySelector(".scrim");

  function openMenu() {
    sidebar.classList.add("is-open");
    scrim.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
  }
  function closeMenu() {
    sidebar.classList.remove("is-open");
    scrim.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
  }
  if (toggle && sidebar && scrim) {
    toggle.addEventListener("click", function () {
      var isOpen = sidebar.classList.contains("is-open");
      isOpen ? closeMenu() : openMenu();
    });
    scrim.addEventListener("click", closeMenu);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeMenu();
    });
  }

  // ---- Lightweight client-side filter for region grids / listing tables ----
  // Any element with [data-filter-input] filters siblings matching
  // [data-filter-target] by their data-filter-text attribute.
  document.querySelectorAll("[data-filter-input]").forEach(function (input) {
    var targetSelector = input.getAttribute("data-filter-input");
    var items = document.querySelectorAll(targetSelector);
    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase();
      items.forEach(function (item) {
        var text = (item.getAttribute("data-filter-text") || item.textContent).toLowerCase();
        item.style.display = q === "" || text.indexOf(q) !== -1 ? "" : "none";
      });
    });
  });
  // ---- Sortable + searchable tables --------------------------------------
  // <table data-sortable id="x">  with  <th data-sort-key="city"><button>
  // Each row carries  data-sort-city="..."  values to sort by.
  // <input data-table-search="x">   filters rows by their text.
  // <select data-table-state="x">   filters rows by data-state.
  // Reusable for any list on the site (hotels now, truck stops later).
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  document.querySelectorAll("table[data-sortable]").forEach(function (table) {
    var tbody = table.tBodies[0];
    var heads = table.querySelectorAll("th[data-sort-key]");
    heads.forEach(function (th) {
      var btn = th.querySelector("button");
      if (!btn) return;
      btn.addEventListener("click", function () {
        var key = "sort" + cap(th.getAttribute("data-sort-key"));
        var asc = th.getAttribute("aria-sort") !== "ascending";
        heads.forEach(function (o) { o.removeAttribute("aria-sort"); });
        th.setAttribute("aria-sort", asc ? "ascending" : "descending");
        var rows = Array.prototype.slice.call(tbody.rows);
        rows.sort(function (a, b) {
          var x = a.dataset[key] || "", y = b.dataset[key] || "";
          var c = x.localeCompare(y, undefined, { numeric: true, sensitivity: "base" });
          if (c === 0) c = (a.dataset.sortName || "").localeCompare(b.dataset.sortName || "");
          return asc ? c : -c;
        });
        rows.forEach(function (r) { tbody.appendChild(r); });
      });
    });
  });

  function applyFilters(id) {
    var table = document.getElementById(id);
    if (!table) return;
    var search = document.querySelector('[data-table-search="' + id + '"]');
    var state = document.querySelector('[data-table-state="' + id + '"]');
    var count = document.querySelector('[data-table-count="' + id + '"]');
    var empty = document.querySelector('[data-table-empty="' + id + '"]');
    var q = search ? search.value.trim().toLowerCase() : "";
    var st = state ? state.value : "";
    var shown = 0, total = table.tBodies[0].rows.length;
    Array.prototype.forEach.call(table.tBodies[0].rows, function (r) {
      var ok = (!q || r.textContent.toLowerCase().indexOf(q) !== -1) &&
               (!st || r.getAttribute("data-state") === st);
      r.hidden = !ok;
      if (ok) shown++;
    });
    if (count) count.textContent = shown === total ? total + " hotels" : "Showing " + shown + " of " + total;
    if (empty) empty.hidden = shown !== 0;
  }

  document.querySelectorAll("[data-table-search],[data-table-state]").forEach(function (el) {
    var id = el.getAttribute("data-table-search") || el.getAttribute("data-table-state");
    el.addEventListener(el.tagName === "SELECT" ? "change" : "input", function () { applyFilters(id); });
  });
  // ---- Old-site ads: fit text to its box -------------------------------
  // The original boxes were sized for fonts like Tahoma and Rockwell. If a
  // visitor's device substitutes a slightly larger font, shrink that panel's
  // text a step at a time until it fits, instead of cutting it off or letting
  // it run over the next advertiser's ad.
  function fitLegacy() {
    document.querySelectorAll(".lbox:not(.lbox-flow) .lp-text").forEach(function (el) {
      if (getComputedStyle(el).position !== "absolute") { el.style.removeProperty("--fit"); return; }
      var s = 1;
      el.style.setProperty("--fit", s);
      while ((el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1) && s > 0.6) {
        s -= 0.03;
        el.style.setProperty("--fit", s.toFixed(2));
      }
    });
  }
  var fitTimer;
  function scheduleFit() { clearTimeout(fitTimer); fitTimer = setTimeout(fitLegacy, 120); }
  if (document.querySelector(".lbox")) {
    fitLegacy();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitLegacy);
    window.addEventListener("load", fitLegacy);
    window.addEventListener("resize", scheduleFit);
  }
  // ---- Nationwide Sponsors: slow auto-scroll on phones ------------------
  // A steady drift so every sponsor gets equal time on screen. Loops
  // seamlessly (a hidden copy of the row follows the real one). Stops while
  // someone touches it and resumes 4s after they let go; has a Pause button;
  // never moves for people who ask their phone to reduce motion; rests when
  // off screen, folded away, or in a background tab.
  (function () {
    var row = document.querySelector(".sec-national .banner-row");
    if (!row) return;
    var phone = window.matchMedia("(max-width: 640px)");
    var calm = window.matchMedia("(prefers-reduced-motion: reduce)");
    var SPEED = 28;                         // pixels per second -- about one banner every 11s
    var originals = Array.prototype.slice.call(row.children);
    if (originals.length < 2) return;
    var running = false, held = false, userPaused = false, onScreen = true;
    var pos = 0, last = null, resumeTimer = null, btn = null;

    function addCopies() {
      if (row.querySelector(".is-clone")) return;
      originals.forEach(function (n) {
        var c = n.cloneNode(true);
        c.classList.add("is-clone");
        c.setAttribute("aria-hidden", "true");          // screen readers hear each sponsor once
        c.querySelectorAll("a, button").forEach(function (a) { a.setAttribute("tabindex", "-1"); });
        c.querySelectorAll("img").forEach(function (i) { i.alt = ""; });
        row.appendChild(c);
      });
    }
    function removeCopies() { row.querySelectorAll(".is-clone").forEach(function (n) { n.remove(); }); }
    function loopLength() {
      var first = row.querySelector(".is-clone");
      return first ? first.offsetLeft - originals[0].offsetLeft : 0;
    }
    function frame(t) {
      if (!running) return;
      if (last === null) last = t;
      var dt = Math.min(t - last, 100) / 1000;
      last = t;
      var visible = onScreen && !document.hidden && row.offsetParent !== null;
      if (!held && !userPaused && visible) {
        pos += SPEED * dt;
        var L = loopLength();
        if (L > 0 && pos >= L) pos -= L;                 // seamless: the copy looks identical
        row.scrollLeft = pos;
      }
      requestAnimationFrame(frame);
    }
    function makeButton() {
      btn = document.createElement("button");
      btn.type = "button";
      btn.className = "autoscroll-toggle";
      btn.setAttribute("aria-label", "Pause the moving sponsor banners");
      btn.textContent = "\u275A\u275A Pause";
      btn.addEventListener("click", function () {
        userPaused = !userPaused;
        btn.textContent = userPaused ? "\u25B6 Play" : "\u275A\u275A Pause";
        btn.setAttribute("aria-label", userPaused ? "Play the moving sponsor banners" : "Pause the moving sponsor banners");
        if (!userPaused) { pos = row.scrollLeft; last = null; }
      });
      row.parentNode.insertBefore(btn, row);
    }
    function start() {
      if (running) return;
      addCopies();
      row.classList.add("is-autoscroll");
      if (!btn) makeButton();
      btn.hidden = false;
      running = true; last = null; pos = row.scrollLeft;
      requestAnimationFrame(frame);
    }
    function stop() {
      running = false;
      row.classList.remove("is-autoscroll");
      removeCopies();
      if (btn) btn.hidden = true;
    }
    function decide() { (phone.matches && !calm.matches) ? start() : stop(); }

    function hold() { held = true; clearTimeout(resumeTimer); }
    function release() {
      clearTimeout(resumeTimer);
      resumeTimer = setTimeout(function () {
        var L = loopLength();
        pos = L > 0 ? row.scrollLeft % L : row.scrollLeft;   // carry on from where they left it
        held = false; last = null;
      }, 4000);
    }
    row.addEventListener("touchstart", hold, { passive: true });
    row.addEventListener("touchend", release);
    row.addEventListener("pointerdown", hold);
    row.addEventListener("pointerup", release);
    row.addEventListener("focusin", hold);
    row.addEventListener("focusout", release);
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) { onScreen = es[0].isIntersecting; }).observe(row);
    }
    [phone, calm].forEach(function (m) {
      if (m.addEventListener) m.addEventListener("change", decide); else if (m.addListener) m.addListener(decide);
    });
    decide();
  })();
})();
