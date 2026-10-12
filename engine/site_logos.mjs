#!/usr/bin/env node
// 기업 홈페이지를 Chrome으로 열어 로고로 보이는 요소를 찾고, 요소마다 배경이 투명한 PNG로 따낸다. scripts/logo.py가 부른다.
//   node engine/site_logos.mjs https://example.com outdir [회사이름]
// 단순 내려받기가 아니라 브라우저로 여는 이유: 자동 요청을 막는 사이트가 많고, 로고를 SVG 조각이나 CSS 배경으로 그리는 사이트도 많다.
// 출력: outdir/site.json (후보 목록)과 outdir/cap_NN.png (요소만 남기고 찍은 투명 PNG)
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { setTimeout as delay } from "node:timers/promises";
import { openPage } from "./lib_cdp.mjs";

const [, , url, outdir, brand = ""] = process.argv;
if (!url || !outdir) { console.error("usage: node engine/site_logos.mjs URL outdir [brand]"); process.exit(2); }
mkdirSync(outdir, { recursive: true });
const blank = join(tmpdir(), `blank-${process.pid}.html`);
writeFileSync(blank, "<!doctype html><title>.</title>");

let page;
try { page = await openPage(blank, { width: 1440, height: 900, scale: 1, media: "screen" }); } catch (e) { console.error(String(e.message || e)); process.exit(3); }
await page.send("Network.enable");
await page.send("Network.setUserAgentOverride", {
  userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
  acceptLanguage: "ko-KR,ko;q=0.9,en;q=0.8", platform: "MacIntel",
});
await page.send("Page.navigate", { url });
let ready = false;
for (let i = 0; i < 60 && !ready; i++) {
  await delay(500);
  try { ready = (await page.evaluate("document.readyState")) === "complete" && (await page.evaluate("location.href")) !== "about:blank" && !(await page.evaluate("location.href")).startsWith("file:"); } catch {}
}
await delay(2500); // 늦게 그려지는 머리 영역

const found = await page.evaluate((brand) => {
  const NOISE = /footer|partner|client|customer|sns|banner|kakao|facebook|instagram|youtube|twitter|appstore|app-store|googleplay|google-play|badge|award|cert|payment|sprite|loading|arrow|search|menu|cart|close|icon-/i;
  const host = location.hostname.replace(/^www\./, "").split(".")[0].toLowerCase();
  const keys = [host, (brand || "").toLowerCase().replace(/\s+/g, "")].filter(Boolean);
  const out = [];
  const textOf = (el) => {
    let t = "";
    for (let e = el, i = 0; e && e !== document.body && i < 4; e = e.parentElement, i++) {
      t += " " + [e.id, e.getAttribute("class"), e.getAttribute("aria-label"), e.getAttribute("title"), e.getAttribute("alt"), e.getAttribute("href")].filter(Boolean).join(" ");
    }
    return t.toLowerCase();
  };
  const homeLink = (el) => {
    const a = el.closest("a[href]");
    if (!a) return false;
    try { const u = new URL(a.href, location.href); return u.hostname.replace(/^www\./, "") === location.hostname.replace(/^www\./, "") && (u.pathname === "/" || /^\/(index|main|home)/i.test(u.pathname)); } catch { return false; }
  };
  const consider = (el, kind, src) => {
    const r = el.getBoundingClientRect();
    if (r.width < 24 || r.height < 10 || r.width > 520 || r.height > 260) return;
    const st = getComputedStyle(el);
    if (st.display === "none" || st.visibility === "hidden" || parseFloat(st.opacity) < 0.1) return;
    const t = textOf(el) + " " + (src || "").toLowerCase();
    const top = r.top + scrollY;
    let s = 0;
    if (/logo|brand|\bci\b|\bbi\b/.test(t)) s += 40;
    if (keys.some((k) => k && t.replace(/\s+/g, "").includes(k))) s += 20;
    if (homeLink(el)) s += 35;                       // 첫 화면으로 가는 링크 안의 이미지는 거의 자사 로고다
    if (top < 200) s += 25; else if (top < 500) s += 8; else s -= 15;
    if (r.left < innerWidth * 0.45) s += 8;
    if (el.closest("header, nav, [class*=header i], [id*=header i], [class*=gnb i]")) s += 15;
    if (kind !== "img") s += 6;
    if (NOISE.test(t)) s -= 45;
    if (el.closest("footer, [class*=footer i]")) s -= 30;
    if (r.width / r.height < 0.6) s -= 15;
    if (s < 45) return;
    const id = out.length + 1;
    el.setAttribute("data-bmc-logo", String(id));
    out.push({ id, kind, src: src || "", alt: el.getAttribute("alt") || el.getAttribute("aria-label") || "", score: Math.round(s),
               rect: { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height } });
  };
  for (const el of document.querySelectorAll("img")) consider(el, "img", el.currentSrc || el.src);
  for (const el of document.querySelectorAll("svg")) { if (!el.parentElement.closest("svg")) consider(el, "svg", ""); }
  for (const el of document.querySelectorAll("a, div, span, h1, i, em, button")) {
    const bi = getComputedStyle(el).backgroundImage;
    if (bi && bi.startsWith("url(") && el.children.length === 0) consider(el, "bg", bi.slice(4, -1).replace(/["']/g, ""));
  }
  // 같은 자리의 중복(예: svg와 그것을 감싼 요소)을 줄인다
  out.sort((a, b) => b.score - a.score);
  const kept = [];
  for (const c of out) {
    if (!kept.some((k) => Math.abs(k.rect.x - c.rect.x) < 6 && Math.abs(k.rect.y - c.rect.y) < 6 && Math.abs(k.rect.w - c.rect.w) < 12)) kept.push(c);
  }
  return { title: document.title, href: location.href, candidates: kept.slice(0, 6) };
}, brand);

// 요소만 남기고 투명 배경으로 찍는다 (긴 변이 1200px쯤 되도록 확대)
await page.send("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } });
for (const c of found.candidates) {
  const sel = `[data-bmc-logo="${c.id}"]`;
  await page.evaluate((css) => {
    let st = document.getElementById("__bmc_cap");
    if (!st) { st = document.createElement("style"); st.id = "__bmc_cap"; document.head.appendChild(st); }
    st.textContent = css;
  }, `html *{visibility:hidden!important;transition:none!important;animation:none!important}${sel},${sel} *{visibility:visible!important}`);
  await delay(120);
  const scale = Math.max(1, Math.min(8, 1200 / Math.max(c.rect.w, c.rect.h)));
  try {
    const { data } = await page.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, fromSurface: true,
      clip: { x: c.rect.x, y: c.rect.y, width: c.rect.w, height: c.rect.h, scale } });
    c.capture = `cap_${String(c.id).padStart(2, "0")}.png`;
    writeFileSync(join(outdir, c.capture), Buffer.from(data, "base64"));
  } catch (e) { c.captureError = String(e.message || e).slice(0, 100); }
}
writeFileSync(join(outdir, "site.json"), JSON.stringify(found));
await page.close();
console.log(`${found.candidates.length} candidates @ ${found.href}`);
process.exit(0);
