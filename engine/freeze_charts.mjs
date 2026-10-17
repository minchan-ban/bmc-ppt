#!/usr/bin/env node
// 덱을 Chrome으로 열어 design/nchart.js가 기본 차트를 그린 뒤의 <main> 안쪽 HTML을 JSON으로 출력한다.
// scripts/build.py가 Figma용 HTML의 본문을 이것으로 바꾼다. Figma는 스크립트를 실행하지 않을 수 있어서, 그려진 SVG를 고정해 보낸다.
// 문자열로 .nchart를 찾아 바꾸면 class 순서, 따옴표 속 '>', 주석 때문에 차트가 엇갈릴 수 있어 DOM에서 통째로 꺼낸다.
//   node engine/freeze_charts.mjs deck.html  → stdout: {"main": "...", "errors": [...]}
import { openPage } from "./lib_cdp.mjs";

const file = process.argv[2];
if (!file) { console.error("usage: node engine/freeze_charts.mjs deck.html"); process.exit(2); }
let page;
try { page = await openPage(file, { scale: 1 }); } catch (e) { console.error(String(e.message || e)); process.exit(3); }
const out = await page.evaluate(() => {
  if (window.nchartRender) window.nchartRender();
  const errors = [...document.querySelectorAll(".nchart[data-error]")].map((el) => el.getAttribute("data-error"));
  const main = document.querySelector("main");
  return { main: main ? main.innerHTML : "", errors };
});
await page.close();
process.stdout.write(JSON.stringify(out));
process.exit(0);
