/* Hamara Makaan Properties – progressive enhancements. The site works without JavaScript. */
(function () {
  "use strict";

  // Home search: tabs change the form target and the budget presets.
  var search = document.querySelector("[data-home-search]");
  if (search) {
    var budget = search.querySelector("select[name=budget]");
    var budgets = JSON.parse(document.getElementById("budget-presets").textContent);
    search.querySelectorAll("[data-search-tab]").forEach(function (tab) {
      tab.addEventListener("click", function () {
        search.querySelectorAll("[data-search-tab]").forEach(function (t) {
          t.classList.remove("active");
          t.setAttribute("aria-selected", "false");
        });
        tab.classList.add("active");
        tab.setAttribute("aria-selected", "true");
        search.action = tab.dataset.action;
        var list = budgets[tab.dataset.budget] || budgets.sale;
        budget.innerHTML = "";
        list.forEach(function (pair) {
          var opt = document.createElement("option");
          opt.value = pair[0];
          opt.textContent = pair[1];
          budget.appendChild(opt);
        });
      });
    });
  }

  // Auto-submit selects marked with data-autosubmit (e.g. sort order).
  document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () { el.form && el.form.submit(); });
  });

  // Remove empty query parameters before submitting GET filter forms, for clean shareable URLs.
  document.querySelectorAll("form[data-clean-get]").forEach(function (form) {
    form.addEventListener("submit", function () {
      form.querySelectorAll("input, select").forEach(function (el) {
        if (!el.name || el.type === "checkbox" || el.type === "radio") return;
        if (el.value === "") el.disabled = true;
      });
    });
  });

  // Gallery: open the modal carousel at the clicked image.
  var galleryModal = document.getElementById("galleryModal");
  if (galleryModal && window.bootstrap) {
    var carousel = bootstrap.Carousel.getOrCreateInstance(galleryModal.querySelector(".carousel"), { interval: false });
    document.querySelectorAll("[data-gallery-index]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        carousel.to(parseInt(btn.dataset.galleryIndex, 10) || 0);
        bootstrap.Modal.getOrCreateInstance(galleryModal).show();
      });
    });
  }

  // EMI calculator (indicative only).
  var emi = document.querySelector("[data-emi]");
  if (emi) {
    var fmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
    var calc = function () {
      var p = parseFloat(emi.querySelector("[name=emi_amount]").value) || 0;
      var r = (parseFloat(emi.querySelector("[name=emi_rate]").value) || 0) / 12 / 100;
      var n = (parseFloat(emi.querySelector("[name=emi_years]").value) || 0) * 12;
      var out = emi.querySelector("[data-emi-result]");
      if (!p || !n) { out.textContent = "—"; return; }
      var value = r ? (p * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1) : p / n;
      out.textContent = "₹ " + fmt.format(Math.round(value)) + " / month";
    };
    emi.addEventListener("input", calc);
    calc();
  }

  // Photo previews on the Post Property form.
  var photoInput = document.querySelector("input[type=file][name=photos]");
  var previews = document.querySelector("[data-photo-previews]");
  if (photoInput && previews && window.URL) {
    photoInput.addEventListener("change", function () {
      previews.innerHTML = "";
      Array.prototype.slice.call(photoInput.files, 0, 10).forEach(function (file) {
        if (!/^image\//.test(file.type)) return;
        var img = document.createElement("img");
        img.alt = "";
        img.src = URL.createObjectURL(file);
        img.onload = function () { URL.revokeObjectURL(img.src); };
        previews.appendChild(img);
      });
    });
  }

  // Locality dropdowns: show only localities in the chosen city.
  document.querySelectorAll("select[data-city-select]").forEach(function (citySel) {
    var locSel = document.getElementById(citySel.dataset.citySelect);
    if (!locSel) return;
    var all = Array.prototype.slice.call(locSel.options).map(function (o) { return o.cloneNode(true); });
    var cityMap = JSON.parse(document.getElementById("locality-cities").textContent);
    var keyAttr = citySel.dataset.cityKey || "id";
    var filter = function () {
      var city = citySel.value;
      var current = locSel.value;
      locSel.innerHTML = "";
      all.forEach(function (o) {
        var entry = cityMap[o.value];
        if (!o.value || !city || (entry && String(entry[keyAttr]) === city)) locSel.appendChild(o.cloneNode(true));
      });
      locSel.value = current;
      if (locSel.value !== current) locSel.value = "";
    };
    citySel.addEventListener("change", filter);
    filter();
  });

  // Confirmation for destructive actions.
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      if (!window.confirm(el.dataset.confirm)) e.preventDefault();
    });
  });
})();
