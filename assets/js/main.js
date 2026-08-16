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
})();
