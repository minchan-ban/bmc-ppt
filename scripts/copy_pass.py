#!/usr/bin/env python3
"""덱 HTML의 글자를 꺼내 문체를 교정한 뒤 다시 넣는다 (문체 교정 단계의 입출력).

  python3 scripts/copy_pass.py extract decks/x/deck.html     # decks/x/copy/before.txt, after.txt 생성
  (after.txt의 문장을 교정한다. 줄 앞의 번호와 탭은 그대로 둔다)
  python3 scripts/copy_pass.py apply decks/x/deck.html       # after.txt를 deck.html에 반영

apply가 반영을 거부하는 경우 (하나라도 있으면 아무것도 바꾸지 않는다):
  - 줄 수나 번호가 before.txt와 다르다
  - 한 줄 안의 수치가 달라졌다 (문체 교정은 내용을 바꾸지 않는다)
  - 한 줄이 25%를 넘게 길어졌다 (글상자를 넘칠 수 있다)
  - deck.html의 글자가 extract 이후에 바뀌어 before.txt와 맞지 않는다
apply가 끝나면 im-not-ai의 구조 게이트(vendor/im-not-ai/scripts/verify_gates.py)로 변경률을 함께 확인한다.
"""
import html as htmllib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEG_RE = re.compile(r">([^<>]*[가-힣A-Za-z0-9][^<>]*)<")
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
SKIP_PARENT = re.compile(r'class="(pg|brand)"[^>]*$')


def main_span(raw):
    i, j = raw.index("<main"), raw.rindex("</main>")
    return i, j


def segments(raw):
    i, j = main_span(raw)
    out = []
    for m in SEG_RE.finditer(raw, i, j):
        text = m.group(1)
        if not text.strip() or SKIP_PARENT.search(raw[max(0, m.start() - 80):m.start()]):
            continue
        if re.fullmatch(r"\s*\d+\s*", text):
            continue
        out.append(m)
    return out


def slide_of(raw, pos):
    return raw.count("<section", 0, pos)


def extract(deck):
    raw = deck.read_text(encoding="utf-8")
    lines, last = [], 0
    for k, m in enumerate(segments(raw), 1):
        s = slide_of(raw, m.start())
        if s != last:
            lines.append(f"# 슬라이드 {s}")
            last = s
        lines.append(f"{k}\t{htmllib.unescape(m.group(1)).strip()}")
    d = deck.parent / "copy"
    d.mkdir(exist_ok=True)
    text = "\n".join(lines) + "\n"
    (d / "before.txt").write_text(text, encoding="utf-8")
    (d / "after.txt").write_text(text, encoding="utf-8")
    print(f"{d / 'before.txt'}: 글자 덩어리 {sum(1 for x in lines if not x.startswith('#'))}개")
    print(f"{d / 'after.txt'}를 교정한다. 줄 앞의 번호와 탭, '# 슬라이드' 줄은 그대로 둔다.")


def read_lines(f):
    out = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        k, _, text = line.partition("\t")
        if not k.strip().isdigit():
            sys.exit(f"{f.name}: 번호와 탭으로 시작하지 않는 줄이 있다: {line[:40]}")
        out[int(k)] = text.strip()
    return out


def apply(deck):
    raw = deck.read_text(encoding="utf-8")
    d = deck.parent / "copy"
    before, after = read_lines(d / "before.txt"), read_lines(d / "after.txt")
    segs = segments(raw)
    errors = []
    if set(before) != set(after):
        errors.append(f"번호가 다르다: before {len(before)}줄, after {len(after)}줄")
    if len(segs) != len(before):
        errors.append(f"deck.html의 글자 덩어리 수({len(segs)})가 before.txt({len(before)})와 다르다. extract를 다시 한다")
    changed = 0
    for k, m in enumerate(segs, 1):
        if errors:
            break
        cur = htmllib.unescape(m.group(1)).strip()
        if cur != before.get(k):
            errors.append(f"{k}번: deck.html의 글자가 before.txt와 다르다. extract를 다시 한다")
            break
        new = after[k]
        if new == cur:
            continue
        changed += 1
        if sorted(n.replace(",", "") for n in NUM_RE.findall(cur)) != sorted(n.replace(",", "") for n in NUM_RE.findall(new)):
            errors.append(f"{k}번: 수치가 달라졌다. '{cur[:30]}' → '{new[:30]}'")
        if len(new) > len(cur) * 1.25 + 2:
            errors.append(f"{k}번: {len(cur)}자에서 {len(new)}자로 늘었다 (25% 초과). 글상자를 넘칠 수 있다")
        if "<" in new or ">" in new:
            errors.append(f"{k}번: 꺾쇠 기호를 넣을 수 없다")
    if errors:
        for e in errors:
            print("FAIL  " + e)
        sys.exit(1)
    out, pos = [], 0
    for k, m in enumerate(segs, 1):
        lead = re.match(r"\s*", m.group(1)).group(0)
        trail = re.search(r"\s*$", m.group(1)).group(0)
        out.append(raw[pos:m.start(1)])
        out.append(lead + htmllib.escape(after[k], quote=False) + trail)
        pos = m.end(1)
    out.append(raw[pos:])
    deck.write_text("".join(out), encoding="utf-8")
    total = len(before)
    print(f"{deck}: {total}개 중 {changed}개를 바꿨다 ({changed / max(total, 1):.0%})")
    gate = ROOT / "vendor" / "im-not-ai" / "scripts" / "verify_gates.py"
    if gate.exists() and changed:
        strip = lambda f: "\n".join(v for v in read_lines(f).values()) + "\n"
        (d / "_b.txt").write_text(strip(d / "before.txt"), encoding="utf-8")
        (d / "_a.txt").write_text(strip(d / "after.txt"), encoding="utf-8")
        print("\n── im-not-ai 구조 게이트 (변경률, 수치 보존, 서법) ──")
        r = subprocess.run([sys.executable, str(gate), "--before", str(d / "_b.txt"), "--after", str(d / "_a.txt"), "--genre", "report"])
        (d / "_b.txt").unlink()
        (d / "_a.txt").unlink()
        if r.returncode == 2:
            print("주의: 변경률이 50%를 넘었다. 문체가 아니라 내용을 다시 쓴 것은 아닌지 확인한다.")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("extract", "apply"):
        sys.exit(__doc__)
    deck = Path(sys.argv[2])
    extract(deck) if sys.argv[1] == "extract" else apply(deck)


if __name__ == "__main__":
    main()
