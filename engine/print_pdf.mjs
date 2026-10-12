#!/usr/bin/env node
// 덱 HTML을 PDF로 인쇄한다. Chrome을 DevTools로 직접 조종하고 시간 제한을 둔다.
//   node engine/print_pdf.mjs deck.html out.pdf
// `chrome --print-to-pdf` 명령은 가끔 끝나지 않고 멈춰서(2026-10-07에 여러 번 확인) 이 방식으로 바꿨다.
import { writeFileSync } from "node:fs";
import { openPage } from "./lib_cdp.mjs";

const [, , src, out] = process.argv;
if (!src || !out) { console.error("usage: node engine/print_pdf.mjs deck.html out.pdf"); process.exit(2); }
const kill = setTimeout(() => { console.error("PDF 인쇄가 90초 안에 끝나지 않았다"); process.exit(5); }, 90000);
const page = await openPage(src, { scale: 1, media: "print" });
const { data } = await page.send("Page.printToPDF", { printBackground: true, preferCSSPageSize: true, displayHeaderFooter: false,
  marginTop: 0, marginBottom: 0, marginLeft: 0, marginRight: 0 });
writeFileSync(out, Buffer.from(data, "base64"));
clearTimeout(kill);
await page.close();
console.log(out);
process.exit(0);
