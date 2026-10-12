#!/usr/bin/env node
// SVG(또는 브라우저가 그릴 수 있는 이미지)를 배경이 투명한 PNG로 그린다. scripts/logo.py가 부른다.
//   node engine/svg_to_png.mjs in.svg out.png [너비px=1200]
// Chrome으로 그리므로 글꼴과 그라데이션이 있는 SVG도 브라우저에서 보이는 그대로 나온다.
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { openPage } from "./lib_cdp.mjs";

const [, , src, out, widthArg] = process.argv;
if (!src || !out) { console.error("usage: node engine/svg_to_png.mjs in.svg out.png [width]"); process.exit(2); }
const width = parseInt(widthArg || "1200", 10);
const dir = mkdtempSync(join(tmpdir(), "logo-"));
const html = join(dir, "w.html");
writeFileSync(html, `<!doctype html><html><body style="margin:0;background:transparent"><img id="i" src="${pathToFileURL(resolve(src)).href}" style="display:block;width:${width}px;height:auto"></body></html>`);

let page;
try { page = await openPage(html, { width: width + 40, height: 2400, scale: 1, media: "screen" }); } catch (e) { console.error(String(e.message || e)); process.exit(3); }
const rect = await page.evaluate(() => {
  const i = document.getElementById("i");
  if (!i.complete || !i.naturalWidth) return null;
  const r = i.getBoundingClientRect();
  return { w: r.width, h: r.height, nw: i.naturalWidth, nh: i.naturalHeight };
});
if (!rect || rect.h < 1) { await page.close(); console.error("이미지를 그리지 못했다 (깨진 파일이거나 크기 정보가 없는 SVG)"); process.exit(4); }
await page.send("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } });
const { data } = await page.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, fromSurface: true, clip: { x: 0, y: 0, width: rect.w, height: rect.h, scale: 1 } });
writeFileSync(out, Buffer.from(data, "base64"));
await page.close();
console.log(`${Math.round(rect.w)}x${Math.round(rect.h)}`);
process.exit(0);
