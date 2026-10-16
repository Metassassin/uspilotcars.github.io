/* Advertising cart + order form (Advertise pages only).
   The cart lives in this browser (localStorage), so it survives page changes.
   The order form emails grandma through FormSubmit, with any artwork attached.
   When Square is set up, payment slots in after this step. */
(function () {
  "use strict";
  var KEY = "uspc-cart";
  var MAX_UPLOAD = 10 * 1024 * 1024;           // FormSubmit's total limit
  var pkEl = document.getElementById("uspc-packages");
  if (!pkEl) return;
  var PACKAGES = {};
  JSON.parse(pkEl.textContent).forEach(function (p) { PACKAGES[p.id] = p; });

  function load() {
    try {
      var c = JSON.parse(localStorage.getItem(KEY) || "[]");
      return c.filter(function (i) { return PACKAGES[i.id] && price(i) != null; });   // drop anything no longer sold
    } catch (e) { return []; }
  }
  function save(c) { try { localStorage.setItem(KEY, JSON.stringify(c)); } catch (e) {} }
  function price(item) { var p = PACKAGES[item.id]; return item.billing === "annual" ? p.annual : p.monthly; }
  function money(v) { return "$" + v.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
  function totals(c) {
    var m = 0, y = 0;
    c.forEach(function (i) { if (i.billing === "annual") y += price(i); else m += price(i); });
    return { m: m, y: y };
  }
  function totalsText(c) {
    var t = totals(c), parts = [];
    if (t.m) parts.push(money(t.m) + " a month");
    if (t.y) parts.push(money(t.y) + " a year");
    return parts.join(" + ");
  }
  function el(tag, attrs, html) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  // ------------------------------------------------ Advertise page: add to cart
  var bar = document.getElementById("cart-bar");
  function refreshBar() {
    if (!bar) return;
    var c = load();
    bar.hidden = c.length === 0;
    bar.querySelector(".cart-count").textContent =
      c.length + (c.length === 1 ? " package" : " packages") + " in your cart \u2014 " + totalsText(c);
  }
  document.querySelectorAll("[data-add]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var c = load();
      c.push({ id: btn.getAttribute("data-add"), billing: btn.getAttribute("data-billing") });
      save(c);
      refreshBar();
      var old = btn.textContent;
      btn.textContent = "Added \u2713";
      btn.classList.add("is-added");
      setTimeout(function () { btn.textContent = old; btn.classList.remove("is-added"); }, 1600);
    });
  });
  refreshBar();

  // ------------------------------------------------ Order page
  var form = document.getElementById("order-form");
  var list = document.getElementById("cart-list");
  if (!form || !list) return;
  var tpl = document.getElementById("state-options");
  var holder = document.getElementById("item-forms");

  function stateSelect(name, label) {
    var w = el("label", {}, esc(label) + " ");
    var s = el("select", { name: name, required: "" }, tpl ? tpl.innerHTML : "");
    w.appendChild(s);
    return w;
  }
  function input(label, name, type, opts) {
    opts = opts || {};
    var w = el("label", {}, esc(label) + " ");
    var i = type === "textarea" ? el("textarea", { name: name, rows: opts.rows || 3 }) : el("input", { type: type || "text", name: name });
    if (opts.required) i.setAttribute("required", "");
    if (opts.placeholder) i.setAttribute("placeholder", opts.placeholder);
    if (opts.accept) i.setAttribute("accept", opts.accept);
    w.appendChild(i);
    return w;
  }
  function services(prefix) {
    var box = el("fieldset", { class: "svc-pick" }, "<legend>Services you offer</legend>");
    ["Height pole", "Route survey", "Multiple cars", "Steering"].forEach(function (s) {
      box.appendChild(el("label", { class: "check" }, '<input type="checkbox" name="' + esc(prefix + " \u2014 " + s) + '" value="Yes"> ' + s));
    });
    return box;
  }

  function render() {
    var c = load();
    if (!c.length) {
      list.innerHTML = '<p>Your cart is empty. <a href="index.html">Choose a package</a>.</p>';
      form.hidden = true;
      return;
    }
    // cart table
    var rows = c.map(function (i, n) {
      var p = PACKAGES[i.id];
      return "<tr><td>" + (n + 1) + ". <strong>" + esc(p.name) + "</strong></td><td>" +
        (i.billing === "annual" ? "Yearly" : "Monthly") + "</td><td>" + money(price(i)) + (i.billing === "annual" ? "/yr" : "/mo") +
        '</td><td><button type="button" class="btn-remove" data-remove="' + n + '" aria-label="Remove ' + esc(p.name) + '">Remove</button></td></tr>';
    }).join("");
    list.innerHTML = '<div class="table-scroll"><table class="data-table cart-table"><thead><tr><th>Package</th><th>Billing</th><th>Price</th><th></th></tr></thead><tbody>' +
      rows + '</tbody></table></div><p class="cart-total"><strong>Total: ' + totalsText(c) + '</strong></p>' +
      '<p><a href="index.html">&larr; Add another package</a></p>';
    list.querySelectorAll("[data-remove]").forEach(function (b) {
      b.addEventListener("click", function () {
        var cc = load(); cc.splice(+b.getAttribute("data-remove"), 1); save(cc); render();
      });
    });
    // one details section per package -- only the questions that package needs
    holder.innerHTML = "";
    c.forEach(function (i, n) {
      var p = PACKAGES[i.id], pre = "Item " + (n + 1) + " \u2014 " + p.name;
      var box = el("div", { class: "panel item-form", "data-states": p.states });
      box.appendChild(el("h2", {}, "Item " + (n + 1) + ": " + esc(p.name) +
        ' <span class="hotel-meta">(' + (i.billing === "annual" ? "yearly" : "monthly") + ")</span>"));
      var row = el("div", { class: "form-row state-row" });
      if (p.section === "nationwide") {
        box.appendChild(el("p", {}, "Shown on every page of the site."));
      } else {
        for (var k = 1; k <= Math.max(1, p.states); k++) {
          row.appendChild(stateSelect(pre + " \u2014 State" + (p.states > 1 ? " " + k : ""), p.states > 1 ? "State " + k : "State"));
        }
        box.appendChild(row);
      }
      if (p.section === "hotel") {
        var r1 = el("div", { class: "form-row" });
        r1.appendChild(input("Hotel name", pre + " \u2014 Hotel name", "text", { required: true }));
        r1.appendChild(input("City", pre + " \u2014 City", "text", { required: true }));
        box.appendChild(r1);
        var r2 = el("div", { class: "form-row" });
        r2.appendChild(input("Street address", pre + " \u2014 Address"));
        r2.appendChild(input("Hotel phone", pre + " \u2014 Hotel phone", "tel"));
        box.appendChild(r2);
        box.appendChild(input("Highlights (e.g. free breakfast, truck parking, pilot car rate)", pre + " \u2014 Highlights", "textarea"));
      } else if (p.section === "state" || p.section === "nationwide") {
        box.appendChild(input("What should your ad say?", pre + " \u2014 Ad wording", "textarea",
          { required: p.section === "state", rows: 4, placeholder: "Company name, city, phone, services, a short slogan..." }));
        if (p.section === "state") box.appendChild(input("Colours you'd like (optional)", pre + " \u2014 Colours", "text", { placeholder: "e.g. green background, red phone number" }));
        box.appendChild(input("Your ad picture or logo (optional)", pre + " \u2014 Artwork", "file", { accept: "image/png,image/jpeg,image/gif,application/pdf" }));
        box.appendChild(el("p", { class: "hotel-meta" }, "No artwork yet? Leave this empty \u2014 we can design it with you."));
      } else {
        box.appendChild(input(p.section === "super" ? "City / area line (e.g. RIFLE, CO)" : "City or area you serve",
          pre + " \u2014 City or area", "text", { required: true }));
        box.appendChild(services(pre));
        if (p.section === "super") box.appendChild(input("Short description (optional)", pre + " \u2014 Description", "textarea", { rows: 2 }));
      }
      holder.appendChild(box);
    });
    form.hidden = false;
  }

  form.addEventListener("submit", function (ev) {
    var err = document.getElementById("order-error");
    var c = load(), problem = "";
    // each multi-state package needs different states
    form.querySelectorAll(".item-form").forEach(function (box) {
      var picked = Array.prototype.map.call(box.querySelectorAll(".state-row select"), function (s) { return s.value; }).filter(Boolean);
      if (new Set(picked).size !== picked.length) problem = "Please choose different states within each package.";
    });
    var bytes = 0;
    form.querySelectorAll('input[type="file"]').forEach(function (f) {
      Array.prototype.forEach.call(f.files || [], function (x) { bytes += x.size; });
    });
    if (bytes > MAX_UPLOAD) problem = "Your pictures add up to more than 10 MB. Please send smaller files, or leave them out and email them to us afterwards.";
    if (!c.length) problem = "Your cart is empty.";
    if (problem) {
      ev.preventDefault();
      err.textContent = problem; err.hidden = false; err.scrollIntoView({ block: "center" });
      return;
    }
    err.hidden = true;
    document.getElementById("order-summary").value = c.map(function (i, n) {
      var p = PACKAGES[i.id];
      return (n + 1) + ". " + p.name + " \u2014 " + (i.billing === "annual" ? "yearly " + money(p.annual) + "/yr" : "monthly " + money(p.monthly) + "/mo");
    }).join("\n") + "\nTOTAL: " + totalsText(c);
    var sub = form.querySelector('[name="_subject"]'), co = form.querySelector('[name="Company name"]');
    if (sub && co && co.value) sub.value = "New advertising order: " + co.value;
  });
  render();
})();
