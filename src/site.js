(function () {
  "use strict";
  var root = document.documentElement;

  // light and dark
  try {
    var saved = localStorage.getItem("jflib-theme");
    if (saved === "dark" || saved === "light") root.setAttribute("data-theme", saved);
  } catch (e) {}
  function isDark() {
    var t = root.getAttribute("data-theme");
    return t ? t === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  document.getElementById("theme").addEventListener("click", function () {
    var t = isDark() ? "light" : "dark";
    root.setAttribute("data-theme", t);
    try { localStorage.setItem("jflib-theme", t); } catch (e) {}
  });

  // the gallery popup: the WebAssembly is loaded on the first click, and stopped on close
  var demo = document.createElement("dialog");
  demo.id = "demo";
  demo.setAttribute("aria-labelledby", "demo-title");
  demo.innerHTML =
    '<div class="demo-bar"><b id="demo-title">Feature Gallery</b>' +
    "<span>Running in your browser as WebAssembly</span>" +
    '<button class="btn" id="demo-close" type="button">Close</button></div>' +
    '<iframe id="demo-frame" title="Feature Gallery, running live" hidden></iframe>' +
    '<div id="demo-fallback" hidden><p>The gallery could not be loaded here. This is what it looks like:</p>' +
    '<img src="img/gallery-winui.png" width="1000" height="700" alt="A picture of the Feature Gallery."></div>';
  document.body.appendChild(demo);
  var frame = document.getElementById("demo-frame");
  var fallback = document.getElementById("demo-fallback");
  var stopCycle = function () {};
  function openDemo() {
    stopCycle();
    demo.showModal();
    fetch("gallery/variants.json").then(function (r) {
      if (!r.ok) throw new Error("no gallery");
      frame.hidden = false; fallback.hidden = true;
      frame.src = "gallery/index.html?theme=" + (isDark() ? "dark" : "light");
    }).catch(function () { frame.hidden = true; fallback.hidden = false; });
  }
  [].forEach.call(document.querySelectorAll("[data-demo]"), function (b) { b.addEventListener("click", openDemo); });
  document.getElementById("demo-close").addEventListener("click", function () { demo.close(); });
  demo.addEventListener("click", function (e) { if (e.target === demo) demo.close(); });
  demo.addEventListener("close", function () { frame.removeAttribute("src"); frame.hidden = true; });

  // the style of the hero window, and with it every button on the page
  var radios = [].slice.call(document.querySelectorAll('input[name="ui"]'));
  if (radios.length) {
    var shots = [].slice.call(document.querySelectorAll("#shots img"));
    var nameEl = document.getElementById("style-name");
    var setStyle = function (radio) {
      radio.checked = true;
      root.setAttribute("data-ui", radio.value);
      nameEl.textContent = radio.getAttribute("data-label");
      shots.forEach(function (img) { img.classList.toggle("on", img.getAttribute("data-ui") === radio.value); });
    };
    var timer = null;
    stopCycle = function () { if (timer) { clearInterval(timer); timer = null; } };
    radios.forEach(function (r) { r.addEventListener("change", function () { stopCycle(); setStyle(r); }); });
    if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      var at = 0;
      timer = setInterval(function () {
        if (document.hidden || demo.open) return;
        at = (at + 1) % radios.length;
        setStyle(radios[at]);
      }, 3000);
    }
    document.querySelector(".pick").addEventListener("pointerdown", stopCycle);
  }

  // before and after sliders
  [].forEach.call(document.querySelectorAll(".compare"), function (c) {
    var input = c.querySelector("input");
    input.addEventListener("input", function () { c.style.setProperty("--x", input.value + "%"); });
  });

  // colours for the Rust sample
  var code = document.getElementById("rust-sample");
  if (code) {
    var text = code.textContent.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    code.innerHTML = text.replace(/("(?:[^"\\]|\\.)*")|(#!?\[[^\]]*\])|\b(const|struct|impl|fn|for|use|extern|crate|if|mut|self)\b|\b(AppDesc|Counter|App|Ui|u32)\b/g, function (m, s, a, k, t) {
      var c = s ? "s" : a ? "t" : k ? "k" : "a";
      return '<span class="' + c + '">' + m + "</span>";
    });
  }
})();
