/*! Saasta search-by-photo widget. Usage:
 *  <script src="https://saasta.pk/widget.js" data-key="sk_saasta_..." async></script>
 *  Optional: data-color="#0e5c46" data-label="Search by photo" data-target="#my-button"
 */
(function () {
  "use strict";
  var script = document.currentScript;
  if (!script || window.__saastaWidget) return;
  window.__saastaWidget = true;

  var KEY = script.getAttribute("data-key");
  var COLOR = /^#[0-9a-fA-F]{3,8}$/.test(script.getAttribute("data-color") || "") ? script.getAttribute("data-color") : "#0e5c46";
  var LABEL = (script.getAttribute("data-label") || "Search by photo").slice(0, 40);
  var TARGET = script.getAttribute("data-target");
  var BASE = new URL(script.src).origin;
  if (!KEY) return console.warn("[saasta] missing data-key");

  function safeUrl(u) {
    try {
      var p = new URL(u);
      return p.protocol === "https:" || p.protocol === "http:" ? p.href : null;
    } catch {
      return null;
    }
  }
  function el(tag, attrs, text) {
    var n = document.createElement(tag);
    for (var k in attrs || {}) n.setAttribute(k, attrs[k]);
    if (text != null) n.textContent = text;
    return n;
  }

  var host = el("div", { id: "saasta-widget" });
  var root = host.attachShadow ? host.attachShadow({ mode: "closed" }) : host;
  var style = el("style");
  style.textContent =
    ".fab{position:fixed;right:20px;bottom:20px;z-index:2147483000;background:" + COLOR + ";color:#fff;border:0;border-radius:999px;padding:12px 18px;font:600 14px system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.2);cursor:pointer}" +
    ".ov{position:fixed;inset:0;z-index:2147483001;background:rgba(0,0,0,.45);display:none;align-items:flex-end;justify-content:center}" +
    ".ov.open{display:flex}.box{background:#fff;color:#111;width:min(720px,100%);max-height:85vh;overflow:auto;border-radius:18px 18px 0 0;padding:20px;font:14px system-ui,sans-serif}" +
    "@media(min-width:640px){.ov{align-items:center}.box{border-radius:18px}}" +
    ".drop{border:2px dashed #ccc;border-radius:14px;padding:28px;text-align:center;cursor:pointer}" +
    ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;margin-top:14px}" +
    ".it{border:1px solid #eee;border-radius:12px;overflow:hidden;text-decoration:none;color:inherit}.it img{width:100%;aspect-ratio:1;object-fit:cover;display:block;background:#f6f6f6}" +
    ".it p{margin:6px 8px;font-size:12px;line-height:1.3}.pr{font-weight:700}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}" +
    ".x{background:none;border:0;font-size:22px;cursor:pointer}.muted{color:#666;font-size:12px}";
  root.appendChild(style);

  var overlay = el("div", { class: "ov", role: "dialog", "aria-modal": "true", "aria-label": LABEL });
  var box = el("div", { class: "box" });
  var top = el("div", { class: "top" });
  top.appendChild(el("strong", {}, LABEL));
  var close = el("button", { class: "x", "aria-label": "Close" }, "×");
  top.appendChild(close);
  var drop = el("div", { class: "drop", tabindex: "0" }, "Upload or drop a photo / screenshot of what you want");
  var file = el("input", { type: "file", accept: "image/jpeg,image/png,image/webp", hidden: "" });
  var status = el("p", { class: "muted" });
  var grid = el("div", { class: "grid" });
  var foot = el("p", { class: "muted" }, "Visual search by Saasta");
  [top, drop, file, status, grid, foot].forEach(function (n) { box.appendChild(n); });
  overlay.appendChild(box);
  root.appendChild(overlay);

  function open() { overlay.classList.add("open"); }
  function hide() { overlay.classList.remove("open"); }
  close.onclick = hide;
  overlay.onclick = function (e) { if (e.target === overlay) hide(); };
  drop.onclick = function () { file.click(); };
  drop.onkeydown = function (e) { if (e.key === "Enter") file.click(); };
  drop.ondragover = function (e) { e.preventDefault(); };
  drop.ondrop = function (e) { e.preventDefault(); if (e.dataTransfer.files[0]) search(e.dataTransfer.files[0]); };
  file.onchange = function () { if (file.files[0]) search(file.files[0]); };

  function search(f) {
    if (f.size > 10 * 1024 * 1024) { status.textContent = "Photo must be under 10 MB."; return; }
    status.textContent = "Finding matching products…";
    grid.textContent = "";
    var fd = new FormData();
    fd.append("file", f);
    fetch(BASE + "/w/v1/widget/search", { method: "POST", headers: { "X-API-Key": KEY }, body: fd, credentials: "omit" })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) { status.textContent = (res.d && typeof res.d.detail === "string" && res.d.detail) || "Search failed."; return; }
        var items = res.d.results || [];
        status.textContent = items.length ? "Closest matches in this store:" : "No close matches. Try a clearer photo.";
        items.forEach(function (o) {
          var href = safeUrl(o.url);
          if (!href) return;
          var a = el("a", { class: "it", href: href });
          var img = safeUrl(o.image);
          if (img) a.appendChild(el("img", { src: img, alt: "", loading: "lazy" }));
          a.appendChild(el("p", {}, o.title));
          if (o.price != null) a.appendChild(el("p", { class: "pr" }, (o.currency || "") + " " + Math.round(o.price).toLocaleString()));
          grid.appendChild(a);
        });
      })
      .catch(function () { status.textContent = "Network error. Please try again."; });
  }

  function mount() {
    document.body.appendChild(host);
    var custom = TARGET && document.querySelector(TARGET);
    if (custom) custom.addEventListener("click", open);
    else {
      var fab = el("button", { class: "fab", type: "button" }, "📷 " + LABEL);
      fab.onclick = open;
      root.appendChild(fab);
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
})();
