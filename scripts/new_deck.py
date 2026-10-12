#!/usr/bin/env python3
"""부품 모음(design/parts.html)에서 부품을 골라 덱 HTML 한 벌을 조립한다.

  python3 scripts/new_deck.py --list
  python3 scripts/new_deck.py --type investor --palette rose --parts p01,p02,p06,p14,p21,p24 \\
      --title "사업 소개" -o decks/2026-10-investor/deck.html

하는 일:
  - design/deck.css를 <style>에 넣어 HTML 하나로 열리게 한다 (PPTX·PDF·Figma 변환의 원본).
  - 색 팔레트(--palette)를 data-theme에, 덱 유형(--type)을 data-type에 적는다. 팔레트는 rose, rose-panel, berry, navy-rose 네 가지다.
  - brand.json의 회사명, 브랜드 색, 뒤표지 연락처를 기본값으로 쓴다 (--company, --brand로 덮어쓸 수 있다).
  - {{회사명}}과 {{꼬리말}}을 채우고, 쪽 번호를 매긴다 (표지·장 구분·뒤표지는 번호에서 제외).
  - 나머지 {{ }} 자리표시자는 그대로 둔다. 하나라도 남으면 check_deck.py가 FAIL을 낸다.
  - design/deck.css를 고친 뒤에는 --refresh-css로 기존 덱의 스타일을 갱신한다.
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PARTS = ROOT / "design" / "parts.html"
CSS = ROOT / "design" / "deck.css"
TYPES = {"investor": "투자자용 사업 소개", "sales": "B2B 제품 소개서"}
PALETTES = {"rose": "A. 차콜 + 로즈 포인트 (기본)", "rose-panel": "B. 차콜 글자 + 로즈 면",
            "berry": "C. 버건디 + 로즈", "navy-rose": "D. 네이비 + 로즈 포인트"}
BRAND = json.loads((ROOT / "brand.json").read_text(encoding="utf-8"))
CONTACT = BRAND.get("contact", {})
PART_RE = re.compile(r"<!-- @part (p\d+) \| (\w+) \| ([^|]+) \| (.*?) -->\s*(<section.*?</section>)", re.S)


def load_parts():
    out = {}
    for pid, type_id, name, use, html in PART_RE.findall(PARTS.read_text(encoding="utf-8")):
        out[pid] = {"type": type_id, "name": name.strip(), "use": use.strip(), "html": html}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parts", help="부품 번호를 순서대로. 예: p01,p02,p06,p24")
    ap.add_argument("--type", default="investor", choices=sorted(TYPES), help="덱 유형 (구성과 어조의 기준. harness/deck-types.md)")
    ap.add_argument("--palette", default="rose", choices=list(PALETTES), help="색 팔레트. 덱을 새로 만들 때마다 사용자가 고른다 (design/palettes.png)")
    ap.add_argument("--title", default="덱 제목")
    ap.add_argument("--company", default=BRAND.get("company", "{{회사명}}"), help="기본값은 brand.json의 company")
    ap.add_argument("--footer", help="꼬리말 왼쪽 글자. 기본값은 '회사명 | 덱 제목'")
    ap.add_argument("--brand", default=BRAND.get("brand"), help="브랜드 색 HEX (예: #2F5BEA). 기본값은 brand.json의 brand이고, --brand 토큰을 덮어쓴다")
    ap.add_argument("--brand-soft", default=BRAND.get("brand_soft"), help="브랜드 색의 옅은 채움 HEX. 기본값은 brand.json의 brand_soft")
    ap.add_argument("-o", "--out", default="deck.html")
    ap.add_argument("--list", action="store_true", help="부품 목록을 보여 주고 끝낸다")
    ap.add_argument("--set-palette", choices=list(PALETTES), help="--refresh-css와 함께 써서 이미 만든 덱의 팔레트를 바꾼다")
    ap.add_argument("--refresh-css", metavar="DECK_HTML", help="이미 만든 덱의 스타일을 design/deck.css의 현재 내용으로 바꾼다 (내용은 그대로)")
    a = ap.parse_args()

    if a.refresh_css:
        f = pathlib.Path(a.refresh_css)
        html = f.read_text(encoding="utf-8")
        m = re.search(r"/\*deck\.css:start\*/.*?/\*deck\.css:end\*/", html, flags=re.S)
        if not m:
            sys.exit("이 파일에는 deck.css 구간 표시가 없다 (new_deck.py로 만든 덱이 아니다)")
        html = html[:m.start()] + "/*deck.css:start*/\n" + CSS.read_text(encoding="utf-8") + "/*deck.css:end*/" + html[m.end():]
        note = ""
        if a.set_palette:
            html, n = re.subn(r'(<main class="deck" data-theme=")[^"]*(")', rf"\g<1>{a.set_palette}\g<2>", html, count=1)
            note = f", 팔레트를 {a.set_palette}로 바꿨다" if n else ", 팔레트를 바꾸지 못했다 (main 태그를 찾지 못함)"
        f.write_text(html, encoding="utf-8")
        print(f"{f}: design/deck.css의 현재 내용으로 스타일을 갱신했다{note}")
        return

    parts = load_parts()
    if a.list or not a.parts:
        for pid, p in parts.items():
            print(f"{pid}  {p['type']:<22} {p['name']:<18} {p['use']}")
        if not a.list:
            print("\n--parts로 순서를 지정한다. 예: --parts p01,p02,p06,p24", file=sys.stderr)
        return

    footer = a.footer or f"{a.company} | {a.title}"
    page, body = 0, []
    for tok in [t.strip().lower() for t in a.parts.split(",") if t.strip()]:
        if tok not in parts:
            sys.exit(f"없는 부품 번호: {tok} (--list로 확인)")
        p = parts[tok]
        sec = p["html"]
        unnumbered = re.search(r'<section class="slide (cover|divider|back)"', sec) is not None
        if not unnumbered:
            page += 1
            sec = sec.replace('<span class="pg">0</span>', f'<span class="pg">{page}</span>')
        sec = sec.replace("{{회사명}}", a.company).replace("{{꼬리말}}", footer)
        # 뒤표지 연락처는 brand.json의 contact에서 채운다
        for k, v in CONTACT.items():
            sec = sec.replace("{{" + k + "}}", v)
        sec = sec.replace("<section ", f'<section data-part="{tok}" data-type="{p["type"]}" ', 1)
        body.append(f"<!-- {tok} {p['name']} -->\n{sec}")

    css = CSS.read_text(encoding="utf-8")
    override = ""
    if a.brand:
        override = f"\n:root{{--brand:{a.brand};" + (f"--brand-soft:{a.brand_soft};" if a.brand_soft else "") + "}\n"
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>{a.title}</title>
<!-- scripts/new_deck.py로 생성. 이 HTML이 덱의 원본이다. 내용 수정은 여기서 하고 scripts/build.py로 PPTX·PDF·Figma용 파일을 다시 만든다.
     규칙: harness/headline-rules.md, harness/slide-rules.md / 검사: python3 scripts/check_deck.py {out.name} -->
<style>
/*deck.css:start*/
{css}/*deck.css:end*/{override}</style></head><body>
<main class="deck" data-theme="{a.palette}" data-type="{a.type}">
{chr(10).join(body)}
</main>
</body></html>
""", encoding="utf-8")
    print(f"{out}: {len(body)}장 (쪽 번호 {page}쪽), 유형 {a.type}, 팔레트 {a.palette} ({PALETTES[a.palette]})")


if __name__ == "__main__":
    main()
