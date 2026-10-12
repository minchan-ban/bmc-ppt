#!/usr/bin/env node
// 실제로 그려 봐야 알 수 있는 항목의 기계 검사. Chrome을 직접 띄우므로 추가 설치가 필요 없다 (Node 22 이상).
//   node engine/check_layout.mjs deck.html
// 검사 항목:
//   L1 Pretendard 굵기 5종이 이 컴퓨터에서 실제로 그려지는지
//   L2 헤드메시지가 2줄을 넘거나, 둘째 줄에 4자 이하만 남는지
//   L3 요소가 슬라이드 밖으로 나가거나 꼬리말·출처와 겹치는지
//   L4 본문이 영역보다 커서 잘리는지
//   L5 본문 영역의 45%를 넘게 비어 있는지 (WARN)
//   L6 한 슬라이드에서 강조색으로 채운 도형이 3개를 넘는지 (WARN)
// 참고한 원본: carnot-tech/consulting-pptx-skill scripts/check_layout.mjs (MIT)
import { openPage } from "./lib_cdp.mjs";

const file = process.argv[2];
if (!file) { console.error("usage: node engine/check_layout.mjs deck.html"); process.exit(2); }

const kill = setTimeout(() => { console.error("화면 검사가 150초 안에 끝나지 않았다"); process.exit(6); }, 150000);
let page;
try { page = await openPage(file, { scale: 1 }); } catch (e) { console.error(String(e.message || e)); process.exit(3); }

const result = await page.evaluate(() => {
  const fails = [], warns = [];
  const p = (n) => `p${String(n).padStart(2, "0")}`;
  // L1 글꼴
  for (const w of [400, 500, 600, 700, 800]) {
    if (!document.fonts.check(`${w} 16px Pretendard`)) fails.push(`덱 [L1] Pretendard ${w} 굵기를 찾지 못했다. design/fonts의 글꼴을 설치한다 (scripts/setup.sh)`);
  }
  const probe = document.createElement("span");
  probe.textContent = "가나다ABC123"; probe.style.cssText = "position:absolute;visibility:hidden;font:400 40px Pretendard,monospace";
  document.body.appendChild(probe); const w1 = probe.getBoundingClientRect().width;
  probe.style.fontFamily = "monospace"; const w2 = probe.getBoundingClientRect().width; probe.remove();
  if (Math.abs(w1 - w2) < 0.5) fails.push("덱 [L1] Pretendard가 설치되어 있지 않아 대체 글꼴로 그려지고 있다");

  const accent = getComputedStyle(document.querySelector(".deck") || document.body).getPropertyValue("--accent").trim();
  const probe2 = document.createElement("i"); probe2.style.color = "var(--accent)"; (document.querySelector(".deck") || document.body).appendChild(probe2);
  const accentRgb = getComputedStyle(probe2).color; probe2.remove();

  [...document.querySelectorAll("section.slide")].forEach((s, i) => {
    const n = i + 1, sr = s.getBoundingClientRect();
    const special = s.matches(".cover, .divider, .back");
    const title = s.querySelector("h1.title");
    // L2 헤드메시지 줄 수
    if (title) {
      const rg = document.createRange(); rg.selectNodeContents(title);
      const rects = [...rg.getClientRects()].filter((q) => q.width > 1);
      const tops = [...new Set(rects.map((q) => Math.round(q.top)))].sort((a, b) => a - b);
      if (tops.length > 2) fails.push(`${p(n)} [L2] 헤드메시지가 ${tops.length}줄로 그려진다. 2줄 안으로 줄인다`);
      if (tops.length === 2) {
        const lastW = rects.filter((q) => Math.round(q.top) === tops[1]).reduce((a, q) => a + q.width, 0);
        const fs = parseFloat(getComputedStyle(title).fontSize);
        if (lastW < fs * 4.2) fails.push(`${p(n)} [L2] 헤드메시지 둘째 줄에 4자 이하만 남는다. <br>로 줄을 나누는 자리를 정한다`);
        if (!title.querySelector("br")) warns.push(`${p(n)} [L2] 헤드메시지가 자동으로 2줄이 되었다. 의미가 끊기는 자리에 <br>을 넣는다`);
      }
      if (title.scrollHeight > title.clientHeight + 2) fails.push(`${p(n)} [L2] 헤드메시지가 제목 영역을 넘친다`);
    }
    const foot = s.querySelector(".foot"), src = s.querySelector(".src"), body = s.querySelector(".body");
    const fr = foot?.getBoundingClientRect(), srr = src?.getBoundingClientRect();
    // L3 넘침과 겹침
    const leaves = [...s.querySelectorAll("*")].filter((el) => {
      if (foot && foot.contains(el)) return false;
      if (el.closest(".bleed")) return false; // 슬라이드 밖으로 일부러 잘려 나가게 둔 장식 (slide-rules S46)
      const st = getComputedStyle(el);
      if (st.display === "none" || st.visibility === "hidden") return false;
      return el.children.length === 0 && ((el.textContent || "").trim().length > 0 || parseFloat(st.height) > 0);
    });
    const seen = new Set();
    for (const el of leaves) {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      const label = `<${el.tagName.toLowerCase()}${el.className ? "." + String(el.className).split(" ")[0] : ""}> "${(el.textContent || "").trim().slice(0, 24)}"`;
      const add = (m) => { if (!seen.has(m)) { seen.add(m); fails.push(m); } };
      if (r.right > sr.right + 1) add(`${p(n)} [L3] 오른쪽으로 ${Math.round(r.right - sr.right)}px 넘친다: ${label}`);
      if (r.bottom > sr.bottom + 1) add(`${p(n)} [L3] 아래로 ${Math.round(r.bottom - sr.bottom)}px 넘친다: ${label}`);
      if (special || (src && src.contains(el))) continue;
      const limit = srr ? srr.top : fr ? fr.top : sr.bottom;
      if (r.bottom > limit + 1 && r.top < (fr ? fr.bottom : sr.bottom)) add(`${p(n)} [L3] ${srr ? "출처 줄" : "꼬리말"}과 겹친다 (${Math.round(r.bottom - limit)}px): ${label}`);
    }
    // L4 잘림
    if (body) {
      for (const el of [body, ...body.querySelectorAll(".cols>div, .fill, .side .sb, td, .bars, .colchart .plot")]) {
        if (el.scrollHeight > el.clientHeight + 3 && getComputedStyle(el).overflow !== "visible") { fails.push(`${p(n)} [L4] 내용이 영역보다 커서 잘린다 (${el.scrollHeight - el.clientHeight}px)`); break; }
      }
      const br = body.getBoundingClientRect();
      let top = Infinity, bottom = -Infinity;
      for (const el of body.querySelectorAll("*")) {
        const st = getComputedStyle(el), r = el.getBoundingClientRect();
        if (!r.width || !r.height || st.display === "none") continue;
        const own = [...el.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim());
        const bg = st.backgroundColor, filled = bg && bg !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(bg);
        if (!own && !filled && el.tagName !== "IMG") continue;
        top = Math.min(top, r.top); bottom = Math.max(bottom, r.bottom);
      }
      if (bottom > br.bottom + 2) fails.push(`${p(n)} [L4] 본문이 본문 영역 아래로 ${Math.round(bottom - br.bottom)}px 넘친다. 내용을 줄이거나 두 장으로 나눈다`);
      // L5 빈 공간
      const empty = bottom > top ? 1 - (Math.min(bottom, br.bottom) - Math.max(top, br.top)) / br.height : 1;
      if (empty > 0.45) warns.push(`${p(n)} [L5] 본문 영역의 ${Math.round(empty * 100)}%가 비어 있다. 내용을 더하거나 정보량에 맞는 부품으로 바꾼다 (채우려고 장식을 넣지 않는다)`);
      // L6 강조 과다
      const strong = [...body.querySelectorAll("*")].filter((el) => { const r = el.getBoundingClientRect(); return r.width > 6 && r.height > 6 && getComputedStyle(el).backgroundColor === accentRgb; }).length;
      if (strong > 3) warns.push(`${p(n)} [L6] 강조색으로 채운 도형이 ${strong}개다. 헤드메시지가 말하는 대상만 강조한다`);
    }
  });
  return { fails, warns, slides: document.querySelectorAll("section.slide").length };
});

clearTimeout(kill);
await page.close();
for (const m of result.fails) console.log("FAIL  " + m);
for (const m of result.warns) console.log("WARN  " + m);
console.log(`\n화면 검사 ${result.slides}장: FAIL ${result.fails.length} / WARN ${result.warns.length}`);
process.exit(result.fails.length ? 1 : 0);
