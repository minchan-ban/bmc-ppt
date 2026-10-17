/* ============================================================
   nchart.js: PowerPoint 기본 차트로 바뀌는 도표의 HTML 미리보기
   - <div class="nchart" data-chart='{...}'> 안에 SVG를 그린다. 원본은 data-chart의 수치이고 SVG는 매번 다시 그린다.
   - 그린 뒤 플롯 영역, 범례, 색을 data-layout에 적는다. engine/html_to_pptx.py가 이 값으로 같은 자리에 기본 차트를 넣는다.
     PowerPoint에서는 차트를 선택하고 '데이터 편집'으로 수치를 고칠 수 있다.
   - data-chart 항목
       type        "doughnut" | "pie" | "line" | "area"
       categories  항목 이름 (원형·도넛은 조각, 꺾은선·영역은 가로축 시점)
       series      [{"name": "계열 이름", "values": [수치, ...]}, ...]  원형·도넛은 계열 하나만 쓴다
       highlight   강조색을 칠할 번호 (원형·도넛은 항목 번호, 꺾은선·영역은 계열 번호, 0부터). 없으면 강조하지 않는다
       unit        수치 뒤에 붙일 단위 글자 (예: "%", "억")
       decimals    소수 자릿수 (기본 0)
       labels      꺾은선의 값 표시: "all" | "last" | "none" (기본: 계열이 하나면 all, 여럿이면 last)
       stacked     영역을 누적할지 (기본 true)
       max         세로축 최댓값 (기본: 자동)
   - 변환 제약 때문에 부품에서 SVG를 쓰지 않는다는 규칙(S35)의 예외다. 이 SVG는 PPTX에서 그림이 아니라 기본 차트로 바뀐다.
   ============================================================ */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var ORDER = ["primary", "bar", "soft", "muted", "rule"]; // 강조하지 않는 조각과 계열의 색 순서

  function hex(c) {
    var m = (c || "").match(/rgba?\(([^)]+)\)/);
    if (!m) return "#000000";
    return "#" + m[1].split(/[ ,/]+/).slice(0, 3).map(function (v) { return Math.round(+v).toString(16).padStart(2, "0"); }).join("");
  }
  function tokens(el) {
    var t = {};
    ["primary", "accent", "ink", "muted", "rule", "hair", "soft", "bar", "slide-bg", "on-primary"].forEach(function (k) {
      var p = document.createElement("i");
      p.style.color = "var(--" + k + ")";
      el.appendChild(p);
      t[k] = hex(getComputedStyle(p).color);
      p.remove();
    });
    return t;
  }
  function dark(h) { // 채움 위 글자를 흰색으로 둘지
    var r = parseInt(h.substr(1, 2), 16), g = parseInt(h.substr(3, 2), 16), b = parseInt(h.substr(5, 2), 16);
    return 0.299 * r + 0.587 * g + 0.114 * b < 150;
  }
  function colors(n, hi, T) {
    var out = [], k = 0;
    for (var i = 0; i < n; i++) out.push(i === hi ? T.accent : T[ORDER[k++ % ORDER.length]]);
    return out;
  }
  function fmt(v, spec) {
    var d = Math.min(6, Math.max(0, Math.floor(Number(spec.decimals) || 0)));
    return Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }) + (spec.unit || "");
  }
  function niceMax(v) { // 눈금 네 칸이 깔끔한 수로 끊기도록 한 칸의 크기부터 정한다
    if (v <= 0) return 4;
    var u = (v * 1.06) / 4, p = Math.pow(10, Math.floor(Math.log10(u)));
    var steps = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];
    for (var i = 0; i < steps.length; i++) if (steps[i] * p >= u) return 4 * steps[i] * p;
    return 40 * p;
  }
  function el(tag, attrs, parent, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function txt(svg, x, y, s, o) {
    o = o || {};
    return el("text", { x: x, y: y, "font-size": o.size || 12.5, "font-weight": o.weight || 400, fill: o.fill,
      "text-anchor": o.anchor || "start", "dominant-baseline": "central" }, svg, s);
  }
  // 범례를 그리고 실제로 차지한 상자를 돌려준다. PowerPoint는 범례 상자 안에 항목을 고르게 흩어 놓으므로,
  // 상자를 항목에 꼭 맞게 잡아야 미리보기와 같은 자리에 놓인다
  function legend(svg, box, names, cols, T, vertical) {
    var g = el("g", {}, svg), n = names.length, widths = [];
    if (vertical === true) {
      var step = 28, y0 = box.y + (box.h - step * n) / 2;
      names.forEach(function (nm, i) {
        var cy = y0 + i * step + step / 2;
        el("rect", { x: box.x, y: cy - 5.5, width: 11, height: 11, fill: cols[i] }, g);
        widths.push(txt(g, box.x + 18, cy, nm, { size: 13, fill: T.ink }).getComputedTextLength());
      });
      return { x: box.x - 4, y: y0, w: 18 + Math.max.apply(null, widths) + 16, h: step * n };
    }
    var x = 0, cy = box.y + box.h / 2, key = vertical === "line" ? 26 : 18;
    names.forEach(function (nm, i) {
      if (vertical === "line") { // 꺾은선 범례는 PowerPoint처럼 선과 점으로 그린다
        el("line", { x1: x, x2: x + 20, y1: cy, y2: cy, stroke: cols[i], "stroke-width": 3 }, g);
        el("circle", { cx: x + 10, cy: cy, r: 3.5, fill: cols[i] }, g);
      } else el("rect", { x: x, y: cy - 5.5, width: 11, height: 11, fill: cols[i] }, g);
      x += key + txt(g, x + key, cy, nm, { size: 12, fill: T.ink }).getComputedTextLength() + 22;
    });
    var w = x - 22, left = box.x + (box.w - w) / 2;
    g.setAttribute("transform", "translate(" + left + " 0)");
    return { x: left - 8 - 7 * n, y: box.y, w: w + 16 + 14 * n, h: box.h };
  }

  function round(spec, W, H, T, svg) {
    var s = spec.series[0], vals = s.values.map(Number), cats = spec.categories;
    var hole = spec.type === "doughnut" ? 0.6 : 0;
    var cols = colors(vals.length, spec.highlight, T);
    var sum = vals.reduce(function (a, b) { return a + b; }, 0) || 1;
    var D, plot, leg = null;
    if (hole) { // 도넛: 왼쪽에 원, 오른쪽에 범례
      D = Math.min(H, W * 0.56);
      plot = { x: 0, y: (H - D) / 2, w: D, h: D };
      leg = { x: D + 36, y: plot.y, w: W - D - 36, h: D };
    } else {     // 원형: 가운데에 원, 바깥에 항목 이름과 값
      D = Math.min(H - 70, W - 260);
      if (D < 80) throw new Error("원형을 그릴 자리가 좁다 (가로 340px, 세로 150px 이상 필요)");
      plot = { x: (W - D) / 2, y: (H - D) / 2, w: D, h: D };
    }
    var cx = plot.x + D / 2, cy = plot.y + D / 2, R = D / 2, r = R * hole, a0 = -Math.PI / 2;
    vals.forEach(function (v, i) {
      var a1 = a0 + (v / sum) * Math.PI * 2, large = a1 - a0 > Math.PI ? 1 : 0;
      var p = function (rad, a) { return (cx + rad * Math.cos(a)).toFixed(2) + " " + (cy + rad * Math.sin(a)).toFixed(2); };
      if (v / sum > 0.9999) { // 한 조각이 전체: 호의 시작과 끝이 같으면 SVG가 호를 생략하므로 원 두 개(도넛은 가운데를 뚫어)로 그린다
        var ring = "M" + (cx - R) + " " + cy + " a" + R + " " + R + " 0 1 0 " + 2 * R + " 0 a" + R + " " + R + " 0 1 0 " + -2 * R + " 0 Z";
        if (hole) ring += " M" + (cx - r) + " " + cy + " a" + r + " " + r + " 0 1 0 " + 2 * r + " 0 a" + r + " " + r + " 0 1 0 " + -2 * r + " 0 Z";
        el("path", { d: ring, fill: cols[i], "fill-rule": "evenodd" }, svg);
      } else if (v > 0) {
        var d = "M" + p(R, a0) + " A" + R + " " + R + " 0 " + large + " 1 " + p(R, a1);
        d += hole ? " L" + p(r, a1) + " A" + r + " " + r + " 0 " + large + " 0 " + p(r, a0) + " Z" : " L" + cx + " " + cy + " Z";
        el("path", { d: d, fill: cols[i], stroke: T["slide-bg"], "stroke-width": 1.5 }, svg);
      }
      var mid = (a0 + a1) / 2;
      if (v <= 0) { a0 = a1; return; } // 값이 0인 조각에는 라벨을 달지 않는다 (PPTX에서도 지운다)
      if (hole) {
        var lr = (R + r) / 2;
        txt(svg, cx + lr * Math.cos(mid), cy + lr * Math.sin(mid), fmt(v, spec), { anchor: "middle", weight: 600, size: 13, fill: dark(cols[i]) ? T["on-primary"] : T.primary });
      } else {
        var lx = cx + (R + 16) * Math.cos(mid), ly = cy + (R + 16) * Math.sin(mid), an = Math.cos(mid) >= 0 ? "start" : "end";
        if (Math.abs(Math.cos(mid)) < 0.2) an = "middle";
        txt(svg, lx, ly - 9, cats[i], { anchor: an, size: 12.5, fill: T.ink });
        txt(svg, lx, ly + 9, fmt(v, spec), { anchor: an, size: 13, weight: 600, fill: i === spec.highlight ? T.accent : T.primary });
      }
      a0 = a1;
    });
    if (leg) leg = legend(svg, leg, cats, cols, T, true);
    return { plot: plot, legend: leg, colors: cols, labelColors: cols.map(function (c) { return dark(c) ? T["on-primary"] : T.primary; }) };
  }

  function axes(spec, W, H, T, svg) {
    var n = spec.categories.length, ser = spec.series, area = spec.type === "area";
    var stacked = area && spec.stacked !== false && ser.length > 1;
    var top = ser.length > 1 ? 30 : 0;
    // 영역은 첫 점과 끝 점이 플롯의 양 끝에 놓이므로, 가로축 라벨이 밖으로 나가지 않게 좌우를 더 비운다
    var padL = area ? 84 : 48, padR = area ? 40 : 14;
    var plot = { x: padL, y: top + 18, w: W - padL - padR, h: H - top - 18 - 26 };
    var leg = ser.length > 1 ? { x: plot.x, y: 0, w: plot.w, h: 22 } : null;
    var hi = spec.highlight;
    var cols = colors(ser.length, hi == null ? -1 : hi, T);
    var tops = spec.categories.map(function (_, j) {
      return stacked ? ser.reduce(function (a, s) { return a + Number(s.values[j] || 0); }, 0) : Math.max.apply(null, ser.map(function (s) { return Number(s.values[j] || 0); }));
    });
    var ymax = spec.max || niceMax(Math.max.apply(null, tops)), major = ymax / 4;
    var X = function (j) { return area ? plot.x + (n > 1 ? (j * plot.w) / (n - 1) : plot.w / 2) : plot.x + ((j + 0.5) * plot.w) / n; };
    var Y = function (v) { return plot.y + plot.h - (v / ymax) * plot.h; };
    for (var g = 1; g <= 4; g++) el("line", { x1: plot.x, x2: plot.x + plot.w, y1: Y(g * major), y2: Y(g * major), stroke: T.hair, "stroke-width": 1 }, svg);
    for (g = 0; g <= 4; g++) txt(svg, plot.x - 8, Y(g * major), fmt(g * major, spec), { anchor: "end", size: 11.5, fill: T.muted });
    spec.categories.forEach(function (c, j) { txt(svg, X(j), plot.y + plot.h + 14, c, { anchor: "middle", size: 12, fill: T.muted }); });
    if (area) {
      var base = spec.categories.map(function () { return 0; });
      ser.forEach(function (s, i) {
        var lo = base.slice(), hiv = base.map(function (b, j) { return (stacked ? b : 0) + Number(s.values[j] || 0); });
        var d = "M" + hiv.map(function (v, j) { return X(j) + " " + Y(v); }).join(" L");
        d += " L" + lo.map(function (v, j) { return X(j) + " " + Y(stacked ? v : 0); }).reverse().join(" L") + " Z";
        el("path", { d: d, fill: cols[i], "fill-opacity": 1 }, svg);
        if (stacked) base = hiv;
      });
    } else {
      var mode = spec.labels || (ser.length > 1 ? "last" : "all");
      ser.forEach(function (s, i) {
        var pts = s.values.map(function (v, j) { return X(j) + " " + Y(Number(v)); });
        el("path", { d: "M" + pts.join(" L"), fill: "none", stroke: cols[i], "stroke-width": 3, "stroke-linejoin": "round" }, svg);
        s.values.forEach(function (v, j) {
          el("circle", { cx: X(j), cy: Y(Number(v)), r: 4.5, fill: cols[i] }, svg);
          if (mode === "all" || (mode === "last" && j === n - 1))
            txt(svg, X(j), Y(Number(v)) - 14, fmt(v, spec), { anchor: "middle", size: 12.5, weight: 600, fill: i === hi ? T.accent : T.primary });
        });
      });
    }
    el("line", { x1: plot.x, x2: plot.x + plot.w, y1: plot.y + plot.h, y2: plot.y + plot.h, stroke: T.primary, "stroke-width": 1.5 }, svg);
    if (leg) leg = legend(svg, leg, ser.map(function (s) { return s.name; }), cols, T, area ? false : "line");
    return { plot: plot, legend: leg, colors: cols, ymax: ymax, major: major, between: !area, stacked: stacked, labels: area ? "none" : (spec.labels || (ser.length > 1 ? "last" : "all")) };
  }

  function draw(box) {
    var spec;
    try { spec = JSON.parse(box.getAttribute("data-chart")); } catch (e) { box.setAttribute("data-error", "data-chart를 읽지 못했다: " + e.message); return; }
    var old = box.querySelector("svg.nc");
    if (old) old.remove();
    var r = box.getBoundingClientRect(), W = r.width, H = r.height, T = tokens(box);
    var svg = el("svg", { class: "nc", width: W, height: H, viewBox: "0 0 " + W + " " + H });
    box.insertBefore(svg, box.firstChild);
    var lay = spec.type === "line" || spec.type === "area" ? axes(spec, W, H, T, svg) : round(spec, W, H, T, svg);
    lay.W = W; lay.H = H; lay.tokens = T;
    [["plot", lay.plot], ["legend", lay.legend]].forEach(function (kv) {
      var b = kv[1];
      if (!b) return;
      if (b.w <= 0 || b.h <= 0 || b.x < -2 || b.y < -2 || b.x + b.w > W + 2 || b.y + b.h > H + 2)
        throw new Error((kv[0] === "legend" ? "범례" : "플롯") + "가 차트 영역을 벗어난다. 항목 이름을 줄이거나 항목 수를 줄인다");
      b.x = Math.max(0, b.x); b.y = Math.max(0, b.y); b.w = Math.min(b.w, W - b.x); b.h = Math.min(b.h, H - b.y);
    });
    if (lay.major != null && !(lay.major > 0 && isFinite(lay.major))) throw new Error("세로축 눈금을 정하지 못했다 (max와 values를 확인한다)");
    box.setAttribute("data-layout", JSON.stringify(lay));
    // 도넛 가운데 글자(.nc-ctr)는 HTML 글자로 두어 PPTX에서 글상자가 된다. 원의 가운데에 맞춘다
    var ctr = box.querySelector(".nc-ctr");
    if (ctr && spec.type === "doughnut") {
      ctr.style.left = lay.plot.x + "px"; ctr.style.top = lay.plot.y + "px";
      ctr.style.width = lay.plot.w + "px"; ctr.style.height = lay.plot.h + "px";
    }
  }
  function all() {
    document.querySelectorAll(".nchart[data-chart]").forEach(function (box) {
      box.removeAttribute("data-error");
      box.removeAttribute("data-layout");
      try { draw(box); } catch (e) {
        box.removeAttribute("data-layout");
        box.setAttribute("data-error", String(e.message || e));
        if (window.console) console.error("nchart:", e.message || e);
      }
    });
  }
  window.nchartRender = all;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", all); else all();
  window.addEventListener("load", all); // 그림이 늦게 불러와져 상자 크기가 바뀌어도 다시 그린다
})();
