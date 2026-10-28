/* NAVORA front-end: progressive enhancement only. Pages work without JS. */
(function () {
  "use strict";
  document.body.classList.add("js");
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

  // mobile nav
  var burger = document.getElementById("burger"), nav = document.getElementById("nav");
  if (burger) burger.addEventListener("click", function () {
    var open = nav.classList.toggle("open"); burger.setAttribute("aria-expanded", open);
  });

  // auto-dismiss flash messages
  document.querySelectorAll(".flash").forEach(function (f) { setTimeout(function () { f.remove(); }, 6000); });

  // reveal on scroll
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }); }, { threshold: .12 });
    document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });
  } else document.querySelectorAll(".reveal").forEach(function (el) { el.classList.add("in"); });

  // animated progress bars
  document.querySelectorAll(".progress > i[data-w]").forEach(function (b) { requestAnimationFrame(function () { b.style.width = b.dataset.w + "%"; }); });

  // stepper (onboarding)
  var form = document.getElementById("onboard-form");
  if (form) {
    var steps = [].slice.call(form.querySelectorAll(".step")), bars = [].slice.call(document.querySelectorAll(".steps i")), cur = 0;
    var back = document.getElementById("step-back"), next = document.getElementById("step-next"), submit = document.getElementById("step-submit");
    var label = document.getElementById("step-label");
    function show(i) {
      cur = i; steps.forEach(function (s, k) { s.classList.toggle("active", k === i); });
      bars.forEach(function (b, k) { b.classList.toggle("on", k <= i); });
      back.style.visibility = i === 0 ? "hidden" : "visible";
      next.style.display = i === steps.length - 1 ? "none" : "inline-flex";
      submit.style.display = i === steps.length - 1 ? "inline-flex" : "none";
      if (label) label.textContent = "Step " + (i + 1) + " of " + steps.length;
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
    next.addEventListener("click", function () {
      var req = steps[cur].querySelector("[required]");
      if (req && !req.value) { req.reportValidity(); return; }
      show(Math.min(cur + 1, steps.length - 1));
    });
    back.addEventListener("click", function () { show(Math.max(cur - 1, 0)); });
    show(0);
  }

  // generic fetch forms: data-fetch => POST, show message
  function toast(msg, kind) {
    var box = document.querySelector(".flashes") || (function () { var d = document.createElement("div"); d.className = "flashes"; d.setAttribute("role", "status"); document.body.appendChild(d); return d; })();
    var f = document.createElement("div"); f.className = "flash " + (kind || "ok"); f.textContent = msg; box.appendChild(f);
    setTimeout(function () { f.remove(); }, 4500);
  }
  document.querySelectorAll("form[data-fetch]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      fetch(f.action, { method: "POST", body: new FormData(f), headers: { "X-Requested-With": "fetch", "X-CSRF-Token": csrf }, credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (d) { toast(d.message || "Saved."); var p = f.closest("[data-fb]"); if (p) p.querySelector(".fb-reasons").classList.remove("show"); })
        .catch(function () { toast("Could not save - check your connection and try again.", "error"); });
    });
  });
  // "not useful" reveals the reason chips
  document.querySelectorAll("[data-fb-no]").forEach(function (b) {
    b.addEventListener("click", function () { b.closest("[data-fb]").querySelector(".fb-reasons").classList.toggle("show"); });
  });

  // confirm destructive actions (CSP forbids inline handlers)
  document.querySelectorAll("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) { if (!window.confirm(f.dataset.confirm)) e.preventDefault(); });
  });

  // compare picker
  var bar = document.getElementById("compare-bar");
  if (bar) {
    var picks = [].slice.call(document.querySelectorAll(".compare-pick input"));
    var upd = function () {
      var on = picks.filter(function (p) { return p.checked; });
      picks.forEach(function (p) { p.disabled = !p.checked && on.length >= 3; });
      bar.classList.toggle("show", on.length >= 2);
      document.getElementById("compare-go").href = "/compare?" + on.map(function (p) { return "id=" + p.value; }).join("&");
      document.getElementById("compare-n").textContent = on.length;
    };
    picks.forEach(function (p) { p.addEventListener("change", upd); });
  }

  // AI mentor chat
  var chat = document.getElementById("chat-form");
  if (chat) {
    var log = document.getElementById("chat-log"), mode = "explain", input = document.getElementById("chat-input");
    function add(cls, text, links) {
      var d = document.createElement("div"); d.className = "msg " + cls; d.textContent = text;
      (links || []).forEach(function (l) { var a = document.createElement("a"); a.href = l.url; a.textContent = l.label; d.appendChild(a); });
      log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
    }
    document.querySelectorAll("[data-mode]").forEach(function (b) {
      b.addEventListener("click", function () {
        mode = b.dataset.mode; document.querySelectorAll("[data-mode]").forEach(function (x) { x.classList.toggle("btn-primary", x === b); x.classList.toggle("btn-ghost", x !== b); x.setAttribute("aria-pressed", x === b); });
        input.placeholder = b.dataset.ph || ""; input.focus();
      });
    });
    document.querySelectorAll("[data-prompt]").forEach(function (b) { b.addEventListener("click", function () { input.value = b.dataset.prompt; chat.requestSubmit(); }); });
    chat.addEventListener("submit", function (e) {
      e.preventDefault(); var text = input.value.trim(); if (!text) return;
      add("user", text); input.value = ""; var wait = add("bot", "Thinking...");
      fetch("/api/mentor", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, credentials: "same-origin", body: JSON.stringify({ message: text, mode: mode }) })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (x) {
          wait.remove();
          if (!x.ok) { add("bot", x.d.error || "Something went wrong. Please try again."); return; }
          add("bot", x.d.text + (x.d.note ? "\n\n(" + x.d.note + ")" : ""), x.d.links);
        })
        .catch(function () { wait.remove(); add("bot", "I couldn't reach the server. Check your connection and try again."); });
    });
  }

  // search suggestions
  var sq = document.getElementById("global-q"), sl = document.getElementById("suggest");
  if (sq && sl) {
    var t;
    sq.addEventListener("input", function () {
      clearTimeout(t); var v = sq.value.trim();
      if (v.length < 2) { sl.hidden = true; return; }
      t = setTimeout(function () {
        fetch("/api/suggest?q=" + encodeURIComponent(v)).then(function (r) { return r.json(); }).then(function (items) {
          sl.innerHTML = ""; if (!items.length) { sl.hidden = true; return; }
          items.forEach(function (i) { var a = document.createElement("a"); a.href = i.url; a.textContent = i.label + "  · " + i.type; a.style.display = "block"; a.style.padding = "8px 12px"; sl.appendChild(a); });
          sl.hidden = false;
        }).catch(function () { sl.hidden = true; });
      }, 200);
    });
    document.addEventListener("click", function (e) { if (!sl.contains(e.target) && e.target !== sq) sl.hidden = true; });
  }
})();
