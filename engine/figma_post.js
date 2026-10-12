// Figma로 보낸 뒤 정리하는 스크립트. use_figma 도구의 code에 이 파일 내용을 그대로 넣어 실행한다 (harness/figma-export.md 4단계).
// 하는 일: 슬라이드 프레임의 이름을 "01 헤드메시지"로 바꾸고, 한 줄에 4장씩 격자로 놓고, 페이지 이름을 덱 제목으로 바꾼다.
// 슬라이드 안의 내용과 모양은 건드리지 않는다. 여러 번 실행해도 결과가 같다.
const COLS = 4, GAP_X = 80, GAP_Y = 120;
const page = figma.root.children.filter((p) => p.children.some((c) => c.type === "FRAME" && c.width === 1280 && c.height === 720)).pop();
if (!page) return { error: "1280×720 슬라이드 프레임이 있는 페이지를 찾지 못했다" };
await figma.setCurrentPageAsync(page);
const slides = page.children.filter((c) => c.type === "FRAME" && c.width === 1280 && c.height === 720)
  .sort((a, b) => (Math.round(a.y / 100) - Math.round(b.y / 100)) || (a.x - b.x));
const renamed = [];
slides.forEach((f, i) => {
  // 가장 큰 글자를 그 장의 제목으로 본다 (헤드메시지 또는 표지 제목). 핵심 수치(굵기 Extra Bold)는 제외한다
  const texts = f.findAllWithCriteria({ types: ["TEXT"] }).filter((t) => t.fontName !== figma.mixed && t.fontName.style !== "Extra Bold" && typeof t.fontSize === "number");
  texts.sort((a, b) => b.fontSize - a.fontSize || a.y - b.y);
  const title = texts.length ? texts[0].characters.replace(/\s+/g, " ").trim().slice(0, 44) : "";
  f.name = `${String(i + 1).padStart(2, "0")} ${title}`;
  f.x = (i % COLS) * (1280 + GAP_X);
  f.y = Math.floor(i / COLS) * (720 + GAP_Y);
  renamed.push({ id: f.id, name: f.name });
});
return { page: page.name, slides: renamed.length, mutatedNodeIds: renamed.map((r) => r.id), names: renamed.map((r) => r.name) };
