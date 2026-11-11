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
          t.setAttribute("aria-pressed", "false");
        });
        tab.classList.add("active");
        tab.setAttribute("aria-pressed", "true");
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

  // Resize photos in the browser before upload (max 1600px, JPEG). Keeps multi-photo submissions
  // small and fast, and under hosting request limits. Falls back to the original files on any error.
  var MAX_SIDE = 1600, QUALITY = 0.82;
  function resizeImage(file) {
    return new Promise(function (resolve) {
      if (!/^image\/(jpeg|png|webp)$/.test(file.type) || !window.createImageBitmap) return resolve(file);
      createImageBitmap(file).then(function (bmp) {
        var scale = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
        if (scale === 1 && file.size < 900 * 1024) return resolve(file);
        var canvas = document.createElement("canvas");
        canvas.width = Math.round(bmp.width * scale);
        canvas.height = Math.round(bmp.height * scale);
        var ctx = canvas.getContext("2d");
        ctx.fillStyle = "#fff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(function (blob) {
          if (!blob || blob.size >= file.size) return resolve(file);
          resolve(new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" }));
        }, "image/jpeg", QUALITY);
      }).catch(function () { resolve(file); });
    });
  }
  document.querySelectorAll("input[type=file][name=photos]").forEach(function (input) {
    input.addEventListener("change", function () {
      if (!window.DataTransfer || input.dataset.resizing) return;
      var form = input.form, submit = form && form.querySelector("[type=submit]");
      input.dataset.resizing = "1";
      if (submit) submit.disabled = true;
      Promise.all(Array.prototype.map.call(input.files, resizeImage)).then(function (files) {
        var dt = new DataTransfer();
        files.forEach(function (f) { dt.items.add(f); });
        input.files = dt.files;
      }).finally(function () {
        delete input.dataset.resizing;
        if (submit) submit.disabled = false;
      });
    });
  });

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

  // Submit feedback: spinner + disabled button while a POST is sending (also stops double submits).
  document.querySelectorAll("form[method=post]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      var btn = e.submitter || form.querySelector("[type=submit]");
      if (!btn || btn.disabled) return;
      form.setAttribute("aria-busy", "true");
      // Disable after the browser has captured the form data, so the clicked button's value is still sent.
      setTimeout(function () {
        btn.disabled = true;
        btn.insertAdjacentHTML("afterbegin", '<span class="spinner-border spinner-border-sm" aria-hidden="true" data-busy></span>');
      }, 0);
    });
  });
  window.addEventListener("pageshow", function (e) { // restore buttons when returning via the back button
    if (!e.persisted) return;
    document.querySelectorAll("[data-busy]").forEach(function (s) { s.parentNode.disabled = false; s.remove(); });
    document.querySelectorAll("form[aria-busy]").forEach(function (f) { f.removeAttribute("aria-busy"); });
  });

  // After a failed submit, take keyboard and screen-reader users straight to the first problem.
  var firstInvalid = document.querySelector("form[method=post] .is-invalid");
  if (firstInvalid) {
    firstInvalid.focus({ preventScroll: true });
    firstInvalid.scrollIntoView({ block: "center" });
  }

  // Confirmation for destructive actions.
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      if (!window.confirm(el.dataset.confirm)) e.preventDefault();
    });
  });
})();
