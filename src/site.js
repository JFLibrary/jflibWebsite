(function () {
  "use strict";
  var root = document.documentElement;
  // the page's language: its texts for this script come from build.py, pictures lie in base
  var base = root.getAttribute("data-base") || "";
  var S = {};
  try { S = JSON.parse(document.getElementById("strings").textContent); } catch (e) {}
  function t(k) { return S[k] || k; }
  function esc(k) { return t(k).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;"); }

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

  // the menu folds into a button on narrow screens
  root.classList.add("js");
  var bar = document.querySelector(".topbar"), menuBtn = document.querySelector(".menu-btn");
  if (menuBtn) {
    var setMenu = function (open) { bar.classList.toggle("open", open); menuBtn.setAttribute("aria-expanded", open ? "true" : "false"); };
    menuBtn.addEventListener("click", function () { setMenu(!bar.classList.contains("open")); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && bar.classList.contains("open")) { setMenu(false); menuBtn.focus(); } });
    document.addEventListener("click", function (e) { if (bar.classList.contains("open") && !bar.contains(e.target)) setMenu(false); });
  }
  var menu = document.querySelector("details.lang");
  if (menu) {
    document.addEventListener("click", function (e) { if (menu.open && !menu.contains(e.target)) menu.open = false; });
    menu.addEventListener("keydown", function (e) { if (e.key === "Escape") { menu.open = false; menu.querySelector("summary").focus(); } });
  }
  [].forEach.call(document.querySelectorAll("a[data-lang]"), function (a) {
    a.addEventListener("click", function () { try { localStorage.setItem("jflib-lang", a.getAttribute("data-lang")); } catch (e) {} });
  });
  if (S.hints) {
    var chosen = null;
    try { chosen = localStorage.getItem("jflib-lang"); } catch (e) {}
    var want = (navigator.languages || [navigator.language || ""]).map(function (l) { return String(l).slice(0, 2).toLowerCase(); });
    var code = chosen ? null : want.filter(function (l) { return S.hints[l]; })[0];
    if (code && want[0] !== "en") {
      var h = S.hints[code], hint = document.createElement("div");
      hint.className = "lang-hint";
      hint.lang = code;
      hint.innerHTML = '<div class="wrap"><span></span><a></a><button type="button">&#10005;</button></div>';
      hint.querySelector("span").textContent = h[0];
      hint.querySelector("a").textContent = h[1];
      hint.querySelector("a").href = h[2];
      hint.querySelector("button").setAttribute("aria-label", h[3]);
      hint.querySelector("a").addEventListener("click", function () { try { localStorage.setItem("jflib-lang", code); } catch (e) {} });
      hint.querySelector("button").addEventListener("click", function () { hint.remove(); try { localStorage.setItem("jflib-lang", "en"); } catch (e) {} });
      var main = document.getElementById("top");
      main.parentNode.insertBefore(hint, main);
    }
  }

  // the gallery popup: the WebAssembly is loaded on the first click, and stopped on close
  var demo = document.createElement("dialog");
  demo.id = "demo";
  demo.setAttribute("aria-labelledby", "demo-title");
  demo.innerHTML =
    '<div class="demo-bar"><b id="demo-title">' + esc("Feature Gallery") + '</b>' +
    "<span>" + esc("Running in your browser as WebAssembly") + "</span>" +
    '<button class="btn" id="demo-close" type="button">' + esc("Close") + '</button></div>' +
    '<iframe id="demo-frame" title="' + esc("Feature Gallery, running live") + '" hidden></iframe>' +
    '<div id="demo-fallback" hidden><p>' + esc("The gallery could not be loaded here. This is what it looks like:") + '</p>' +
    '<img src="' + base + 'img/gallery-winui.png" width="1000" height="700" alt="' + esc("A picture of the Feature Gallery.") + '"></div>';
  document.body.appendChild(demo);
  var frame = document.getElementById("demo-frame");
  var fallback = document.getElementById("demo-fallback");
  var stopCycle = function () {};
  function openDemo() {
    stopCycle();
    demo.showModal();
    fetch(base + "gallery/variants.json").then(function (r) {
      if (!r.ok) throw new Error("no gallery");
      frame.hidden = false; fallback.hidden = true;
      frame.src = base + "gallery/index.html?theme=" + (isDark() ? "dark" : "light");
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

  // the Cargo commands in the hero: one button copies all four lines
  var cmds = document.querySelector(".get-cmds");
  var copy = document.querySelector(".get-copy");
  if (copy && cmds && navigator.clipboard && window.isSecureContext) {
    var copyLabel = copy.textContent, copyTimer = 0;
    var said = document.createElement("span");
    said.className = "vh";
    said.setAttribute("role", "status");
    copy.after(said);
    copy.hidden = false;
    copy.addEventListener("click", function () {
      navigator.clipboard.writeText(cmds.textContent.trim()).then(function () {
        copy.textContent = said.textContent = t("Copied");
        clearTimeout(copyTimer);
        copyTimer = setTimeout(function () { copy.textContent = copyLabel; said.textContent = ""; }, 1600);
      });
    });
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
    code.innerHTML = text.replace(/(\/\/[^\n]*)|("(?:[^"\\]|\\.)*")|(#!?\[[^\]]*\])|\b(const|struct|impl|fn|for|use|extern|crate|if|mut|self)\b|\b(AppDesc|Counter|App|Ui|u32)\b/g, function (m, d, s, a, k, t) {
      var c = d ? "d" : s ? "s" : a ? "t" : k ? "k" : "a";
      return '<span class="' + c + '">' + m + "</span>";
    });
  }

  // the script player on the test page: the picture after each line
  [].forEach.call(document.querySelectorAll("[data-player]"), function (pl) {
    var imgs = [].slice.call(pl.querySelectorAll(".player-view img"));
    var lines = [].slice.call(pl.querySelectorAll(".player-lines li"));
    var ctl = pl.querySelector(".player-ctl"), playBtn = pl.querySelector('[data-p="play"]');
    var state = pl.querySelector(".player-state");
    var at = 0, timer = null, playing = false, stopped = false;
    function go(i) {
      at = (i + lines.length) % lines.length;
      var f = +lines[at].getAttribute("data-f");
      imgs.forEach(function (im, k) { im.classList.toggle("on", k === f); });
      lines.forEach(function (li, k) {
        li.classList.toggle("now", k === at);
        li.classList.toggle("ok", k <= at);
        li.classList.toggle("ahead", k > at);
      });
      state.textContent = t("Line {n} of {m}").replace("{n}", at + 1).replace("{m}", lines.length);
    }
    function tick() {
      var last = at === lines.length - 1;
      timer = setTimeout(function () {
        if (!playing) return;
        go(last ? 0 : at + 1);
        tick();
      }, last ? 2800 : lines[at].classList.contains("exp") ? 700 : 1300);
    }
    function setPlay(on) {
      playing = on;
      playBtn.textContent = t(on ? "Pause" : "Play");
      clearTimeout(timer);
      if (on) tick();
    }
    function byHand(f) { return function () { stopped = true; setPlay(false); f(); }; }
    ctl.hidden = false;
    lines.forEach(function (li, k) { li.addEventListener("click", byHand(function () { go(k); })); });
    pl.querySelector('[data-p="prev"]').addEventListener("click", byHand(function () { go(at - 1); }));
    pl.querySelector('[data-p="next"]').addEventListener("click", byHand(function () { go(at + 1); }));
    playBtn.addEventListener("click", function () { stopped = playing; setPlay(!playing); });
    go(0);
    setPlay(false);
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          if (e.isIntersecting && !playing && !stopped) setPlay(true);
          else if (!e.isIntersecting && playing) setPlay(false);
        });
      }, { threshold: 0.35 }).observe(pl);
    } else setPlay(true);
  });

  // pictures open large: wheel, pinch, buttons or keys zoom, dragging pans
  var pics = [].slice.call(document.querySelectorAll("main img")).filter(function (img) {
    return !img.closest("#shots, .phone, .compare, a, button, [data-nozoom]");
  });
  if (pics.length) {
    var lb = document.createElement("dialog");
    lb.id = "lb";
    lb.setAttribute("aria-label", t("Picture viewer"));
    lb.innerHTML =
      '<div class="lb-stage"><img id="lb-img" alt="" draggable="false"></div>' +
      '<div class="lb-bar"><span class="lb-cap" id="lb-cap"></span>' +
      '<span class="lb-nav"><button type="button" data-lb="prev" aria-label="' + esc("Previous picture") + '">&#8249;</button>' +
      '<button type="button" data-lb="next" aria-label="' + esc("Next picture") + '">&#8250;</button></span>' +
      '<button type="button" data-lb="out" aria-label="' + esc("Zoom out") + '">&#8722;</button>' +
      '<output id="lb-zoom" aria-live="polite">100%</output>' +
      '<button type="button" data-lb="in" aria-label="' + esc("Zoom in") + '">+</button>' +
      '<button type="button" data-lb="fit" aria-label="' + esc("Fit to the screen") + '">' + esc("Fit") + '</button>' +
      '<button type="button" data-lb="close" aria-label="' + esc("Close") + '">&#10005;</button></div>';
    document.body.appendChild(lb);
    var stage = lb.querySelector(".lb-stage"), big = document.getElementById("lb-img");
    var cap = document.getElementById("lb-cap"), zoomOut = document.getElementById("lb-zoom");
    var at = 0, w = 1, h = 1, s = 1, fit = 1, x = 0, y = 0, ptrs = {}, pinch = null, drag = null;
    var clamp = function (v, a, b) { return Math.max(a, Math.min(b, v)); };
    function place() {
      var sw = stage.clientWidth, sh = stage.clientHeight;
      x = w * s <= sw ? (sw - w * s) / 2 : clamp(x, sw - w * s, 0);
      y = h * s <= sh ? (sh - h * s) / 2 : clamp(y, sh - h * s, 0);
      big.style.transform = "translate(" + x + "px," + y + "px) scale(" + s + ")";
      big.classList.toggle("px", s >= 2);
      zoomOut.textContent = Math.round(s * 100) + "%";
      stage.classList.toggle("zoomed", s > fit * 1.001);
    }
    function toFit() {
      fit = Math.min(stage.clientWidth / w, stage.clientHeight / h, 1);
      s = fit;
      place();
    }
    function zoomAt(f, cx, cy) {
      var ns = clamp(s * f, fit, Math.max(8, fit));
      if (cx === undefined) { cx = stage.clientWidth / 2; cy = stage.clientHeight / 2; }
      x = cx - (cx - x) * ns / s;
      y = cy - (cy - y) * ns / s;
      s = ns;
      place();
    }
    function show(i) {
      at = (i + pics.length) % pics.length;
      var img = pics[at], fig = img.closest("figure"), fc = fig && fig.querySelector("figcaption");
      cap.textContent = fc ? fc.textContent : img.alt;
      big.alt = img.alt;
      big.onload = function () {
        w = big.naturalWidth || 1; h = big.naturalHeight || 1;
        big.style.width = w + "px"; big.style.height = h + "px";
        toFit();
      };
      big.src = img.currentSrc || img.src;
    }
    pics.forEach(function (img, i) {
      img.classList.add("zoomable");
      img.tabIndex = 0;
      img.setAttribute("role", "button");
      img.setAttribute("aria-label", t("Enlarge: ") + img.alt);
      var open = function () { show(i); lb.showModal(); root.classList.add("lb-open"); };
      img.addEventListener("click", open);
      img.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
    });
    lb.querySelector(".lb-nav").hidden = pics.length < 2;
    // the close event alone comes late or not at all in some embedded browsers
    var shut = function () { root.classList.remove("lb-open"); big.removeAttribute("src"); };
    var closeLb = function () { if (lb.open) lb.close(); shut(); };
    lb.addEventListener("close", shut);
    lb.addEventListener("cancel", shut);
    lb.addEventListener("click", function (e) {
      var b = e.target.closest("[data-lb]");
      if (!b) return;
      var a = b.getAttribute("data-lb");
      if (a === "close") closeLb();
      else if (a === "prev") show(at - 1);
      else if (a === "next") show(at + 1);
      else if (a === "in") zoomAt(1.5);
      else if (a === "out") zoomAt(1 / 1.5);
      else toFit();
    });
    lb.addEventListener("keydown", function (e) {
      var k = e.key, zoomed = s > fit * 1.001;
      if (k === "+" || k === "=") zoomAt(1.5);
      else if (k === "-") zoomAt(1 / 1.5);
      else if (k === "0") toFit();
      else if (k === "ArrowLeft" && !zoomed) show(at - 1);
      else if (k === "ArrowRight" && !zoomed) show(at + 1);
      else if (k.indexOf("Arrow") === 0 && zoomed) {
        x += k === "ArrowLeft" ? 60 : k === "ArrowRight" ? -60 : 0;
        y += k === "ArrowUp" ? 60 : k === "ArrowDown" ? -60 : 0;
        place();
      } else return;
      e.preventDefault();
    });
    stage.addEventListener("click", function (e) { if (e.target === stage && !stage.classList.contains("zoomed")) closeLb(); });
    stage.addEventListener("wheel", function (e) {
      e.preventDefault();
      var r = stage.getBoundingClientRect(), d = e.deltaY * (e.deltaMode === 1 ? 40 : 1);
      zoomAt(Math.exp(-d * 0.0015), e.clientX - r.left, e.clientY - r.top);
    }, { passive: false });
    stage.addEventListener("dblclick", function (e) {
      var r = stage.getBoundingClientRect();
      if (s > fit * 1.001) toFit();
      else zoomAt(Math.max(1, fit * 2.5) / s, e.clientX - r.left, e.clientY - r.top);
    });
    var ptrList = function () { return Object.keys(ptrs).map(function (k) { return ptrs[k]; }); };
    stage.addEventListener("pointerdown", function (e) {
      stage.setPointerCapture(e.pointerId);
      ptrs[e.pointerId] = { x: e.clientX, y: e.clientY };
      var p = ptrList();
      if (p.length === 2) {
        pinch = { d: Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y), s: s };
        drag = null;
      } else if (p.length === 1) {
        drag = { x: e.clientX - x, y: e.clientY - y };
      }
    });
    stage.addEventListener("pointermove", function (e) {
      if (!ptrs[e.pointerId]) return;
      ptrs[e.pointerId] = { x: e.clientX, y: e.clientY };
      var p = ptrList(), r = stage.getBoundingClientRect();
      if (pinch && p.length === 2) {
        var d = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
        zoomAt(pinch.s * d / pinch.d / s, (p[0].x + p[1].x) / 2 - r.left, (p[0].y + p[1].y) / 2 - r.top);
      } else if (drag) {
        x = e.clientX - drag.x; y = e.clientY - drag.y;
        stage.classList.add("drag");
        place();
      }
    });
    var lift = function (e) {
      delete ptrs[e.pointerId];
      if (ptrList().length < 2) pinch = null;
      var p = ptrList();
      drag = p.length === 1 ? { x: p[0].x - x, y: p[0].y - y } : null;
      stage.classList.remove("drag");
    };
    stage.addEventListener("pointerup", lift);
    stage.addEventListener("pointercancel", lift);
    window.addEventListener("resize", function () { if (lb.open) { var was = s <= fit * 1.001; fit = Math.min(stage.clientWidth / w, stage.clientHeight / h, 1); if (was) s = fit; place(); } });
  }
})();
