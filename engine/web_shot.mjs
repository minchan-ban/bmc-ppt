#!/usr/bin/env node
// 웹 페이지를 휴대폰 화면 크기로 열어 고화질 전체 화면을 찍는다. 덱에 넣을 제품 화면을 만들 때 쓴다.
//   node engine/web_shot.mjs <URL> <out.png> [너비=390] [배율=3]
// 결과: 페이지 전체 높이를 찍은 PNG (너비 390 × 배율 3 = 1170px). 잘라 쓰는 일은 scripts/screens.py가 한다.
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { openPage } from "./lib_cdp.mjs";

const [, , url, out, wArg, sArg] = process.argv;
if (!url || !out) { console.error("usage: node engine/web_shot.mjs URL out.png [width=390] [scale=3]"); process.exit(2); }
const width = parseInt(wArg || "390", 10), scale = parseFloat(sArg || "3");
const blank = join(mkdtempSync(join(tmpdir(), "shot-")), "b.html");
writeFileSync(blank, "<!doctype html><title>.</title>");

const kill = setTimeout(() => { console.error("90초 안에 끝나지 않았다"); process.exit(5); }, 90000);
const page = await openPage(blank, { width, height: 844, scale, media: "screen" });
await page.send("Network.enable");
await page.send("Network.setUserAgentOverride", {
  userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
  acceptLanguage: "ko-KR,ko;q=0.9", platform: "iPhone",
});
await page.send("Emulation.setDeviceMetricsOverride", { width, height: 844, deviceScaleFactor: scale, mobile: true });
await page.send("Emulation.setTouchEmulationEnabled", { enabled: true });
await page.send("Page.navigate", { url });
for (let i = 0; i < 60; i++) {
  await delay(500);
  try { if ((await page.evaluate("document.readyState")) === "complete" && (await page.evaluate("location.href")).startsWith("http")) break; } catch {}
}
// 페이지가 안쪽 스크롤 영역을 쓰면 문서 높이가 화면 높이에 묶인다. 가장 큰 스크롤 영역을 찾아 펼친다
const expanded = await page.evaluate(`(() => {
  const els = [...document.querySelectorAll("*")].filter((e) => {
    const st = getComputedStyle(e);
    return /(auto|scroll)/.test(st.overflowY) && e.scrollHeight > e.clientHeight + 40;
  }).sort((a, b) => b.scrollHeight - a.scrollHeight);
  const box = els[0];
  if (!box) return 0;
  // 늦게 불러오는 이미지를 깨우려고 끝까지 내렸다가 올린다
  return new Promise(async (res) => {
    for (let y = 0; y < box.scrollHeight; y += 500) { box.scrollTop = y; await new Promise((r) => setTimeout(r, 200)); }
    box.scrollTop = 0;
    for (let e = box; e && e !== document.documentElement; e = e.parentElement) {
      e.style.setProperty("height", "auto", "important"); e.style.setProperty("max-height", "none", "important");
      e.style.setProperty("overflow", "visible", "important");
    }
    document.documentElement.style.setProperty("height", "auto", "important");
    document.documentElement.style.setProperty("overflow", "visible", "important");
    res(box.scrollHeight);
  });
})()`);
if (!expanded) {
  const total = await page.evaluate("document.documentElement.scrollHeight");
  for (let y = 0; y < total; y += 600) { await page.evaluate(`window.scrollTo(0, ${y})`); await delay(250); }
  await page.evaluate("window.scrollTo(0, 0)");
}
await delay(2500);
const h = await page.evaluate("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)");
const { data } = await page.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, fromSurface: true, clip: { x: 0, y: 0, width, height: h, scale: 1 } });
writeFileSync(out, Buffer.from(data, "base64"));
console.log(`${width}x${h} @${scale}x → ${out}`);
clearTimeout(kill);
await page.close();
process.exit(0);
