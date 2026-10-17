#!/usr/bin/env python3
"""덱 HTML 한 벌을 검사하고 PPTX, PDF, Figma용 HTML로 내보낸다.

  .venv/bin/python scripts/build.py decks/x/deck.html            # 검사 → PPTX → PDF → Figma용 HTML
  .venv/bin/python scripts/build.py decks/x/deck.html --open     # 끝나면 PowerPoint로 PPTX를 연다
  .venv/bin/python scripts/build.py decks/x/deck.html --preview  # 슬라이드별 PNG도 만든다 (눈으로 확인하는 용도)
  .venv/bin/python scripts/build.py decks/x/deck.html --pptx-preview  # PowerPoint가 실제로 그린 모습도 PNG로 만든다
  .venv/bin/python scripts/build.py decks/x/deck.html --html-only  # 수정 단계: 검사와 HTML 미리보기만 (PPTX·Figma 생략)
  .venv/bin/python scripts/build.py decks/x/deck.html --draft    # 검사에서 FAIL이 나도 계속 만든다 (초안 확인용)

산출물은 덱 폴더의 out/ 아래에 놓인다. 원본은 항상 deck.html이고, out/의 파일을 손으로 고친 내용은 다음 빌드에서 사라진다.
FAIL이 하나라도 있으면 내보내지 않는다 (--draft 제외). 검사를 통과하지 못한 덱이 밖으로 나가지 않게 하기 위해서다.
"""
import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
CHROME = next((p for p in ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                           "/Applications/Chromium.app/Contents/MacOS/Chromium"] if Path(p).exists()), None)
FIGMA_CHUNK = 20   # Figma html_to_figma가 한 번에 프레임으로 만드는 요소 수의 상한
FONT_WEIGHTS = [("Light", 300), ("Regular", 400), ("Medium", 500), ("SemiBold", 600), ("Bold", 700), ("ExtraBold", 800)]


def run(title, cmd, allow_fail=False):
    print(f"\n■ {title}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode in (3, 5, 6):  # Chrome이 응답하지 않아 끝난 경우 한 번 더 시도한다
        print("Chrome이 응답하지 않아 한 번 더 시도한다", flush=True)
        r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0 and not allow_fail:
        print(f"\n중단: '{title}' 단계에서 FAIL이 나왔다. 위의 FAIL을 고친 뒤 다시 실행한다 (초안만 보려면 --draft).")
        sys.exit(1)
    return r.returncode == 0


def freeze_charts(deck: Path, body: str) -> str:
    """기본 차트(.nchart)가 있으면 Chrome이 차트를 그린 뒤의 <main> 안쪽 HTML로 본문을 바꾼다.
    Figma가 스크립트를 실행하지 않아도 차트가 SVG로 보이게 하기 위해서다."""
    if "nchart" not in body:
        return body
    r = subprocess.run(["node", str(ROOT / "engine" / "freeze_charts.mjs"), str(deck)], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"주의: 기본 차트를 SVG로 고정하지 못했다 ({r.stderr.strip()[:200]}). Figma에서 차트가 비어 보일 수 있다")
        return body
    res = json.loads(r.stdout)
    for e in res.get("errors", []):
        print(f"주의: 그리지 못한 기본 차트가 있다: {e}")
    return "\n" + res["main"] + "\n" if res.get("main") else body


def figma_html(deck: Path, out_dir: Path):
    """Figma로 보낼 HTML을 만든다. 글꼴을 파일 안에 넣고(외부 자원은 Figma가 가져오지 않는다), 20장씩 나눈다."""
    raw = deck.read_text(encoding="utf-8")
    faces = []
    for name, weight in FONT_WEIGHTS:
        f = ROOT / "design" / "fonts" / f"Pretendard-{name}.woff2"
        if f.exists():
            b64 = base64.b64encode(f.read_bytes()).decode()
            faces.append(f'@font-face{{font-family:"Pretendard";font-weight:{weight};font-style:normal;src:url(data:font/woff2;base64,{b64}) format("woff2")}}')
    head, rest = raw.split("<main", 1)
    main_open, rest = rest.split(">", 1)
    body, tail = rest.rsplit("</main>", 1)
    head = head.replace("<style>", "<style>\n" + "\n".join(faces) + "\n", 1)
    # Figma에서는 슬라이드를 프레임으로 가져오므로 회색 바탕과 바깥 여백을 없앤다
    head = head.replace("</style>", "html,body{background:#fff}.slide{margin:0 0 40px 0}\n</style>", 1)
    # Figma는 외부 자원을 가져오지 않으므로 img가 가리키는 파일도 파일 안에 넣는다
    def inline_img(m):
        src = m.group(2)
        f = (deck.parent / src) if not src.startswith(("http", "data:", "/")) else Path(src)
        if src.startswith(("http", "data:")) or not f.exists():
            return m.group(0)
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "svg": "image/svg+xml", "webp": "image/webp"}.get(f.suffix.lower().lstrip("."), "image/png")
        return f'{m.group(1)}data:{mime};base64,{base64.b64encode(f.read_bytes()).decode()}{m.group(3)}'
    body = freeze_charts(deck, body)   # 그림을 파일 안에 넣기 전에 바꾼다 (차트를 그린 뒤의 본문으로 통째로 바뀐다)
    body = re.sub(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', inline_img, body)
    sections = re.findall(r"(?:<!--[^>]*-->\s*)?<section.*?</section>", body, flags=re.S)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("deck_figma_*.html"):
        old.unlink()
    files = []
    for k in range(0, len(sections), FIGMA_CHUNK):
        f = out_dir / f"deck_figma_{k // FIGMA_CHUNK + 1:02d}.html"
        f.write_text(f"{head}<main{main_open}>\n" + "\n".join(sections[k:k + FIGMA_CHUNK]) + f"\n</main>{tail}", encoding="utf-8")
        files.append(f)
    return files, len(sections)


def pptx_preview(pptx: Path, out_dir: Path):
    """PowerPoint로 PPTX를 열어 PDF로 내보낸 뒤 PNG로 바꾼다. PowerPoint가 실제로 그린 모습을 확인하는 용도다.
    PowerPoint는 자기 전용 폴더에만 쓸 수 있어서 그 폴더를 거친다. 방금 연 파일만 닫고, 사용자가 열어 둔 다른 파일은 건드리지 않는다."""
    box = Path.home() / "Library/Containers/com.microsoft.Powerpoint/Data/Documents/bmc_ppt_preview"
    box.mkdir(parents=True, exist_ok=True)
    pdf = box / (pptx.stem + ".pdf")
    pdf.unlink(missing_ok=True)
    script = f'''
tell application "Microsoft PowerPoint"
  set wasRunning to running
  open POSIX file "{pptx}"
  delay 2
  set thePres to active presentation
  if (full name of thePres) does not end with "{pptx.name}" then error "방금 연 파일이 활성 창이 아니다"
  save thePres in (POSIX file "{pdf}") as save as PDF
  delay 1
  close thePres saving no
end tell'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=180)
    if r.returncode != 0 or not pdf.exists():
        print(f"PowerPoint 미리보기를 만들지 못했다: {r.stderr.strip()[:200]}")
        return
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    subprocess.run(["pdftoppm", "-png", "-r", "72", str(pdf), str(out_dir / "p")])
    pdf.unlink(missing_ok=True)
    print(f"PowerPoint가 그린 미리보기 PNG: {out_dir} ({len(list(out_dir.glob('*.png')))}장)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("--open", action="store_true", help="끝나면 PowerPoint로 PPTX를 연다")
    ap.add_argument("--preview", action="store_true", help="슬라이드별 PNG를 out/preview에 만든다")
    ap.add_argument("--draft", action="store_true", help="FAIL이 있어도 계속 만든다")
    ap.add_argument("--html-only", action="store_true", help="수정 단계용: 검사와 HTML 미리보기(out/preview)만 만들고 PPTX·Figma는 건너뛴다")
    ap.add_argument("--pptx-preview", action="store_true", help="PowerPoint로 PPTX를 열어 실제로 그려진 모습을 out/preview_pptx에 PNG로 만든다 (PowerPoint 창이 잠깐 열린다)")
    ap.add_argument("--no-figma", action="store_true")
    a = ap.parse_args()

    deck = Path(a.deck).resolve()
    if not deck.exists():
        sys.exit(f"파일이 없다: {deck}")
    out = deck.parent / "out"
    out.mkdir(exist_ok=True)
    name = deck.parent.name if deck.stem == "deck" else deck.stem
    pptx, pdf = out / f"{name}.pptx", out / f"{name}.pdf"

    ok1 = run("1/5 내용 검사 (헤드메시지, 문체, 수치 근거)", [PY, "scripts/check_deck.py", str(deck)], a.draft)
    ok2 = run("2/5 화면 검사 (글꼴, 줄 수, 넘침, 빈 공간)", ["node", "engine/check_layout.mjs", str(deck)], a.draft)
    if a.html_only:
        a.preview, a.no_figma, a.pptx_preview, a.open = True, True, False, False
    else:
        run("3/5 PPTX 변환", [PY, "engine/html_to_pptx.py", str(deck), str(pptx)])
        run("3/5 PPTX 검사 (글꼴, 그림으로 변환된 요소)", [PY, "scripts/check_deck.py", str(pptx)], a.draft)

    print("\n■ 4/5 PDF")
    if CHROME:
        # chrome --print-to-pdf는 가끔 멈춰서 DevTools로 직접 인쇄한다 (engine/print_pdf.mjs, 90초 제한)
        subprocess.run(["node", str(ROOT / "engine" / "print_pdf.mjs"), str(deck), str(pdf)], stdout=subprocess.DEVNULL)
        print(f"{pdf}" if pdf.exists() else "PDF를 만들지 못했다")
    else:
        print("Chrome을 찾지 못해 PDF를 건너뛴다")

    if a.preview and pdf.exists() and shutil.which("pdftoppm"):
        prev = out / "preview"
        shutil.rmtree(prev, ignore_errors=True)
        prev.mkdir()
        subprocess.run(["pdftoppm", "-png", "-r", "72", str(pdf), str(prev / "p")])
        print(f"미리보기 PNG: {prev} ({len(list(prev.glob('*.png')))}장)")

    if a.pptx_preview and shutil.which("pdftoppm") and Path("/Applications/Microsoft PowerPoint.app").exists():
        pptx_preview(pptx, out / "preview_pptx")

    if not a.no_figma:
        print("\n■ 5/5 Figma용 HTML")
        files, n = figma_html(deck, out / "figma")
        for f in files:
            print(f"{f} ({f.stat().st_size // 1024} KB)")
        print(f"{n}장을 {len(files)}개 파일로 나눴다. Figma로 보내는 절차는 harness/figma-export.md를 따른다.")

    print("\n── 결과 ──")
    print(f"PPTX : {'(건너뜀, --html-only)' if a.html_only else pptx}")
    print(f"PDF  : {pdf}")
    if not (ok1 and ok2):
        print("주의: 검사에 FAIL이 남아 있는 초안이다. 밖으로 내보내지 않는다.")
    if a.open:
        subprocess.run(["open", "-a", "Microsoft PowerPoint", str(pptx)])


if __name__ == "__main__":
    main()
