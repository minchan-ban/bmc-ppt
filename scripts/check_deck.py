#!/usr/bin/env python3
"""덱의 기계 검사: 헤드메시지, 문체, 수치 근거, 서식.

  python3 scripts/check_deck.py decks/x/deck.html                  # HTML 덱 검사 (facts.md가 같은 폴더에 있으면 자동으로 대조)
  python3 scripts/check_deck.py decks/x/deck.html --facts decks/x/facts.md
  python3 scripts/check_deck.py decks/x/storyline.md --storyline   # 헤드메시지만 먼저 검사 (슬라이드를 만들기 전 단계)
  python3 scripts/check_deck.py decks/x/out/deck.pptx              # 변환된 PPTX 검사 (글꼴, 그림으로 변환된 요소)
  python3 scripts/check_deck.py deck.html --forbid ~/forbidden.txt # 대외비 단어(고객사명, 내부 코드명)가 남았는지 검사

규칙의 정본: harness/headline-rules.md (H 번호), harness/slide-rules.md, harness/copy-rules.md (C 번호)
종료 코드: FAIL이 하나라도 있으면 1.
"""
import argparse
import html as htmllib
import json
import math
import re
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEX = json.loads((ROOT / "harness" / "lexicon.json").read_text(encoding="utf-8"))
TITLE_MIN, TITLE_ONE_LINE, TITLE_MAX = 14, 40, 64
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
COUNT_RE = r"(\d+|[두세네]|다섯|여섯)\s?(가지|개의|단계|스텝|요소|축|포인트|이유|원칙)"
CHART_CLASSES = ("bars", "colchart", "kpis", "calc", "stack", "sp", "wf", "stk", "grp", "fnl", "sc", "dots", "heat",
                 "dm", "pc", "kd", "mk", "db", "dv", "tg", "nchart")
NCHART_TYPES = ("doughnut", "pie", "line", "area")
VOID = {"br", "img", "meta", "link", "hr", "input"}

fails, warns = [], []


def fail(page, code, msg):
    fails.append(f"p{page:02d} [{code}] {msg}" if page else f"덱 [{code}] {msg}")


def warn(page, code, msg):
    warns.append(f"p{page:02d} [{code}] {msg}" if page else f"덱 [{code}] {msg}")


# ── HTML 읽기 ──────────────────────────────────────────────────────────────
class Slide:
    def __init__(self, n, attrs):
        self.n, self.attrs = n, attrs
        self.classes = attrs.get("class", "").split()
        self.title, self.title_lines = "", []
        self.kicker, self.src = "", ""
        self.lists = []      # [[항목, ...], ...] 최상위 목록마다
        self.blocks = []     # (클래스 경로, 글자) 잎 글자 덩어리
        self.used_classes = set()
        self.has_svg = False
        self.inline_styles = []
        self.chart_errors = []   # data-chart(기본 차트)의 형식 오류

    @property
    def body_text(self):
        return " ".join(t for _, t in self.blocks)


class DeckParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.slides, self.cur, self.stack = [], None, []
        self.theme = ""
        self.buf = None       # 현재 모으는 글자 덩어리
        self.list_depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "main" and "data-theme" in a:
            self.theme = a["data-theme"]
        if tag == "section" and "slide" in a.get("class", "").split():
            self.cur = Slide(len(self.slides) + 1, a)
            self.slides.append(self.cur)
            self.stack = []
            return
        if self.cur is None:
            return
        cls = a.get("class", "")
        self.cur.used_classes.update(cls.split())
        if a.get("style"):
            self.cur.inline_styles.append(a["style"])
        if tag == "svg":
            self.cur.has_svg = True
        if "data-chart" in a:
            self.read_chart(a["data-chart"])
        if tag == "br":
            if self.buf is not None:
                self.buf.append("\n")
            return
        if tag in VOID:
            return
        self.stack.append((tag, cls))
        if tag in ("ul", "ol"):
            if self.list_depth == 0:
                self.cur.lists.append([])
            self.list_depth += 1
        if tag in ("h1", "li", "td", "th") or (tag == "div" and cls) or (tag == "span" and cls):
            self.flush()
            self.buf = []

    def read_chart(self, raw):
        """기본 차트의 수치와 이름을 본문 글자로 넣는다. 그래야 출처(S1), 자리표시자(C1), 팩트 원장(H10) 검사가 차트에도 걸린다.
        형식 오류는 S7로 모은다. 여기서 막지 못한 값은 nchart.js나 html_to_pptx.py에서 변환을 멈추게 한다."""
        errs = self.cur.chart_errors

        def bad_const(c):
            raise ValueError(f"{c}는 쓸 수 없다")
        try:
            spec = json.loads(raw, parse_constant=bad_const)   # NaN, Infinity는 브라우저가 읽지 못한다
        except ValueError as e:
            errs.append(f"data-chart를 JSON으로 읽지 못했다 ({e})")
            return
        if not isinstance(spec, dict):
            errs.append("data-chart는 {...} 형태의 객체여야 한다")
            return
        num = lambda v: type(v) in (int, float) and math.isfinite(v)   # bool(True, False)은 숫자로 치지 않는다
        cats, series, typ = spec.get("categories"), spec.get("series"), spec.get("type")
        if typ not in NCHART_TYPES:
            errs.append(f"type이 '{typ}'이다. {', '.join(NCHART_TYPES)} 중 하나여야 한다")
        if not isinstance(cats, list) or not cats:
            errs.append("categories는 비어 있지 않은 목록이어야 한다")
            cats = []
        if not isinstance(series, list) or not series or not all(isinstance(x, dict) for x in series):
            errs.append('series는 {"name": ..., "values": [...]} 객체의 목록이어야 한다')
            series = [x for x in series if isinstance(x, dict)] if isinstance(series, list) else []
        for sr in series:
            vals = sr.get("values")
            if not isinstance(vals, list):
                errs.append(f"계열 '{sr.get('name')}'에 values 목록이 없다")
                continue
            if len(vals) != len(cats):
                errs.append(f"계열 '{sr.get('name')}'의 값이 {len(vals)}개이고 categories는 {len(cats)}개다. 개수를 맞춘다")
            if not all(num(v) for v in vals):
                errs.append(f"계열 '{sr.get('name')}'의 values에 숫자가 아닌 값이 있다 (따옴표 없이 숫자만 적는다)")
            elif any(v < 0 for v in vals):
                errs.append(f"계열 '{sr.get('name')}'에 음수가 있다. 기본 차트는 0부터 그린다 (증감은 p55를 쓴다)")
        all_vals = [v for sr in series for v in (sr.get("values") or []) if num(v)] if series else []
        if typ in ("doughnut", "pie"):
            if len(series) != 1:
                errs.append("원형과 도넛은 계열을 하나만 쓴다")
            if len(cats) > 5:
                errs.append(f"원형과 도넛의 조각이 {len(cats)}개다. 5개 이하로 묶거나 p06·p08로 바꾼다")
            if all_vals and sum(all_vals) <= 0:
                errs.append("원형과 도넛의 값 합계가 0이다")
        if typ == "area" and len(cats) < 2:
            errs.append("영역은 시점이 2개 이상이어야 한다")
        hi = spec.get("highlight")
        if hi is not None and not (type(hi) is int and 0 <= hi < (len(cats) if typ in ("doughnut", "pie") else len(series))):
            errs.append(f"highlight {hi!r}가 범위를 벗어난다 (0부터 세는 정수)")
        d = spec.get("decimals")
        if d is not None and not (type(d) is int and 0 <= d <= 6):
            errs.append(f"decimals {d!r}는 0~6의 정수여야 한다")
        mx = spec.get("max")
        if mx is not None and not (num(mx) and mx > 0):
            errs.append(f"max {mx!r}는 0보다 큰 숫자여야 한다")
        elif mx is not None and all_vals and typ in ("line", "area") and mx < max(all_vals):
            errs.append(f"max {mx}가 가장 큰 값 {max(all_vals)}보다 작다")
        unit = spec.get("unit")
        if unit is not None and not (isinstance(unit, str) and len(unit) <= 6 and not re.search(r'["&<>\\]', unit)):
            errs.append(f'unit {unit!r}는 6자 이하이고 " & < > \\ 를 쓰지 않는다')
        if spec.get("labels") not in (None, "all", "last", "none"):
            errs.append(f"labels {spec.get('labels')!r}는 all, last, none 중 하나여야 한다")
        if spec.get("stacked") not in (None, True, False):
            errs.append("stacked는 true나 false여야 한다")
        unit = unit if isinstance(unit, str) else ""
        words = [str(c) for c in cats] + [str(sr.get("name", "")) for sr in series]
        words += [f"{v}{unit}" for v in all_vals]
        self.cur.blocks.append(("nchart", " ".join(words)))

    def handle_endtag(self, tag):
        if self.cur is None:
            return
        if tag == "section":
            self.flush()
            self.cur = None
            return
        if tag in VOID:
            return
        if tag in ("ul", "ol"):
            self.list_depth = max(0, self.list_depth - 1)
        if tag in ("h1", "li", "td", "th", "div", "span"):
            self.flush(tag)
        while self.stack:
            t, _ = self.stack.pop()
            if t == tag:
                break

    def handle_data(self, data):
        if self.cur is not None and self.buf is not None:
            self.buf.append(data)

    def flush(self, closing=None):
        if self.buf is None or self.cur is None:
            return
        raw = "".join(self.buf)
        text = re.sub(r"[ \t\r\f\v]+", " ", raw).strip()
        self.buf = None
        if not text:
            return
        path = [c for _, c in self.stack if c]
        tags = [t for t, _ in self.stack]
        last_cls = path[-1].split() if path else []
        flat = re.sub(r"\s*\n\s*", " ", text)
        if "title" in last_cls and tags and tags[-1] == "h1":
            self.cur.title = flat
            self.cur.title_lines = [x.strip() for x in text.split("\n") if x.strip()]
            return
        if "kicker" in last_cls:
            self.cur.kicker = flat
            return
        if "src" in last_cls:
            self.cur.src = flat
            return
        if any(c in ("foot", "pg", "top", "brand") for c in " ".join(path).split()):
            return
        if tags and tags[-1] == "li" and self.cur.lists:
            self.cur.lists[-1].append(flat)
        self.cur.blocks.append((" ".join(path), flat))


def parse_html(path):
    raw = Path(path).read_text(encoding="utf-8")
    body = re.sub(r"<style.*?</style>", "", raw, flags=re.S)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    p = DeckParser()
    p.feed(body)
    return p, raw


# ── 헤드메시지 검사 (harness/headline-rules.md) ────────────────────────────
def nums(text):
    return [n.replace(",", "") for n in NUM_RE.findall(text)]


def ending(text):
    t = re.sub(r"[\s\"'”’)\]]+$", "", text)
    return t


def check_headline(page, title, lines=None, label_ok=False, body="", src=None, facts=None, storyline=False):
    if not title:
        fail(page, "H1", "헤드메시지가 비어 있다")
        return
    if "{{" in title:
        fail(page, "H1", f"헤드메시지에 자리표시자가 남아 있다: {title}")
        return
    t = ending(title)
    n = len(title)

    # H2 종결: 명사형으로 끝낸다
    if re.search(r"[.。!！]$", t):
        fail(page, "H2", f"헤드메시지를 마침표나 느낌표로 끝내지 않는다: …{t[-12:]}")
        t = t[:-1]
    if re.search(r"(니다|세요|해요|에요|예요|어요|아요|죠|네요)$", t):
        fail(page, "H2", f"헤드메시지는 경어체로 끝내지 않고 명사형으로 끝낸다: …{t[-12:]}")
    elif re.search(r"다$", t):
        fail(page, "H2", f"헤드메시지는 '~다'로 끝내지 않고 명사형으로 끝낸다 (예: '~ 2.1배 상승'): …{t[-12:]}")
    elif re.search(r"[함임음됨]$", t) and not any(t.endswith(w) for w in LEX["gaejosik_noun_allow"]):
        warn(page, "H2", f"개조식 종결('~함/~임/~음')로 보인다. 명사형으로 끝낸다: …{t[-12:]}")
    elif re.search(r"[?？]$", t):
        warn(page, "H2", f"질문형 헤드메시지다. 답을 헤드메시지에 쓴다: …{t[-12:]}")
    elif re.search(r"(하기|되기|위해|위한|통해|에서|으로|에게|까지|부터|이며|하며|하고|하여|해서|[가-힣]를|[가-힣]을|\s및)$", t) and not label_ok:
        fail(page, "H2", f"헤드메시지가 조사나 연결어로 끝나 문장이 닫히지 않았다: …{t[-12:]}")

    # H3 주제형 제목: 주장이 있어야 한다
    last = re.split(r"\s+", t)[-1] if t else ""
    # 내용의 개수('3가지', '5단계')는 주장을 뒷받침하는 수치로 세지 않는다
    has_num = bool(NUM_RE.search(re.sub(COUNT_RE, "", title)))
    has_result = any(w in title for w in LEX["headline_result_words"])
    is_label = any(last.endswith(w) for w in LEX["headline_label_endings"]) and not has_num
    if label_ok:
        pass
    elif n < TITLE_MIN and is_label:
        fail(page, "H3", f"주제만 적은 제목이다. 그 주제에 대해 말하려는 결론을 쓴다: {title}")
    elif is_label and not has_result:
        fail(page, "H3", f"'{last}'로 끝나는 주제형 제목이다. 결론(무엇이 얼마나 어떻게 되는지)을 쓴다: {title}")
    elif not has_num and not has_result:
        warn(page, "H3", f"수치도 결과를 나타내는 말도 없다. 주장인지 확인한다: {title}")
    elif n < TITLE_MIN:
        warn(page, "H3", f"{n}자로 짧다. 주어와 대상이 빠지지 않았는지 확인한다: {title}")

    # H4 '라벨: 주장' 접두 금지
    if re.search(r"[:：]", title) or re.search(r"\s[-–|]\s", title):
        fail(page, "H4", f"'라벨: 주장' 형식을 쓰지 않는다. 라벨은 키커로 옮기고 주장만 남긴다: {title}")

    # H5 길이와 줄 수
    if n > TITLE_MAX:
        fail(page, "H5", f"{n}자로 2줄을 넘는다 (최대 {TITLE_MAX}자). 수식어를 덜어낸다: {title}")
    elif n > TITLE_ONE_LINE and lines is not None and len(lines) < 2 and not storyline:
        warn(page, "H5", f"{n}자로 1줄을 넘는다. 의미가 끊기는 자리에 <br>을 넣어 2줄로 나눈다: {title}")
    if lines and len(lines) > 2:
        fail(page, "H5", f"헤드메시지가 {len(lines)}줄이다. 2줄까지만 허용한다")
    if lines and len(lines) == 2 and len(lines[1]) <= 4:
        fail(page, "H5", f"둘째 줄이 '{lines[1]}' {len(lines[1])}자뿐이다. 줄을 나누는 자리를 옮긴다")

    # H6 내용의 개수를 제목에 쓰지 않는다
    m = re.search(COUNT_RE, title)
    if m:
        warn(page, "H6", f"'{m.group(0)}'처럼 내용의 개수는 주장이 아니다. 개수 대신 내용의 결론을 쓴다: {title}")

    # H7 과장 어휘
    for w in LEX["headline_fail"]:
        if w in title:
            fail(page, "H7", f"헤드메시지에 '{w}'을(를) 쓰지 않는다. 근거가 되는 수치나 사실로 바꾼다: {title}")
            break

    # H8 다른 슬라이드를 가리키는 말
    if re.match(r"^(이|그|위|앞서|해당|이러한|이를|이에|따라서|그러므로|또한)\s", title):
        warn(page, "H8", f"헤드메시지가 다른 장을 가리키는 말로 시작한다. 이 장만 읽어도 뜻이 통하게 쓴다: {title}")

    # H9 헤드메시지의 수치는 본문과 팩트 원장에 있어야 한다
    if has_num and not storyline:
        body_nums = set(nums(body))
        missing = [x for x in nums(title) if x not in body_nums]
        if missing:
            fail(page, "H9", f"헤드메시지의 수치 {missing}이(가) 본문에 없다. 본문이 헤드메시지를 뒷받침해야 한다")
        if src is not None and not src.strip():
            fail(page, "H9", "헤드메시지에 수치가 있는데 출처 줄이 없다")
    if has_num and facts is not None:
        fact_nums = set(nums(facts))
        unknown = [x for x in nums(title) if x not in fact_nums and len(x) > 1]
        if unknown:
            fail(page, "H10", f"헤드메시지의 수치 {unknown}이(가) 팩트 원장(facts.md)에 없다. 근거 없는 수치를 쓰지 않는다")


def check_headline_set(titles):
    """덱 전체의 헤드메시지를 놓고 보는 검사."""
    real = [(p, t) for p, t in titles if t]
    seen = {}
    for p, t in real:
        if t in seen:
            fail(p, "H11", f"p{seen[t]:02d}와 헤드메시지가 같다: {t}")
        seen.setdefault(t, p)
    if len(real) >= 5:
        lasts = {}
        for _, t in real:
            w = re.split(r"\s+", ending(t))[-1]
            lasts[w] = lasts.get(w, 0) + 1
        w, c = max(lasts.items(), key=lambda x: x[1])
        if c / len(real) > 0.4:
            warn(0, "H12", f"헤드메시지 {len(real)}개 중 {c}개가 '{w}'로 끝난다. 같은 문형이 반복되면 견본을 베낀 것처럼 읽힌다")
        pats = sum(1 for _, t in real if re.search(r"(으로|로)\s.+\s\S+$", t) and NUM_RE.search(t))
        if pats / len(real) > 0.6:
            warn(0, "H12", f"헤드메시지 {len(real)}개 중 {pats}개가 '~(으)로 ~ 수치 + 명사' 문형이다. 사실 제시, 전제 공유, 결론을 서로 다른 문형으로 쓴다")


# ── 본문 문체 검사 (harness/copy-rules.md) ─────────────────────────────────
def end_style(text):
    t = ending(re.sub(r"[.。]$", "", text.strip()))
    if any(t.endswith(e) for e in LEX["polite_endings"]) or re.search(r"(니다|세요|해요|에요|예요)$", t):
        return "경어"
    if re.search(r"다$", t):
        return "평서"
    if re.search(r"[함임음됨]$", t) and not any(t.endswith(w) for w in LEX["gaejosik_noun_allow"]):
        return "개조"
    return "명사"


def check_body(s):
    page = s.n
    for path, text in s.blocks:
        if "{{" in text:
            fail(page, "C1", f"자리표시자가 남아 있다: {text[:40]}")
        if end_style(text) == "경어":
            fail(page, "C2", f"경어체를 쓰지 않는다: …{text[-20:]}")
        if len(re.findall(r"[가-힣a-zA-Z0-9)]\.\s+[가-힣A-Z]", text)) >= 1 and len(text) > 30:
            warn(page, "C3", f"한 덩어리에 두 문장이 들어 있다. 글머리표로 나눈다: {text[:40]}…")
        if len(text) > 110 and "ds" not in path:
            warn(page, "C3", f"{len(text)}자로 길다. 한 줄에 한 주장만 남긴다: {text[:40]}…")
    for i, items in enumerate(s.lists):
        styles = {end_style(x) for x in items} - {"경어"}
        if len(styles) > 1:
            warn(page, "C4", f"한 목록 안에서 문장 끝이 섞였다 ({', '.join(sorted(styles))}). 한 가지로 맞춘다: {items[0][:24]}…")
        if len(items) == 1:
            warn(page, "C5", f"항목이 하나뿐인 목록이다. 글머리표 없이 쓰거나 항목을 더한다: {items[0][:30]}")
        if len(items) > 6:
            warn(page, "C5", f"목록 항목이 {len(items)}개다. 상위 묶음 2개로 나누거나 덜어낸다")
    text_all = " ".join([s.title, s.body_text, s.kicker])
    for ch in LEX["banned_chars"]:
        if ch in text_all:
            fail(page, "C6", f"'{ch}' 기호를 쓰지 않는다 (엠대시는 쉼표나 콜론으로, 이모지는 삭제)")
    for group, words in LEX["body_warn"].items():
        hit = [w for w in words if w in s.body_text]
        if hit:
            warn(page, "C7", f"{group}: {', '.join(hit[:5])}")
    if re.search(r"\([^)]{1,40}\).*\([^)]{1,40}\).*\([^)]{1,40}\)", s.body_text) and len(re.findall(r"\(", s.body_text)) > 4:
        warn(page, "C8", "괄호가 5개 넘게 쓰였다. 보충 설명은 문장으로 풀거나 표의 열로 뺀다")


def check_format(s, raw_theme):
    page = s.n
    for e in s.chart_errors:
        fail(page, "S7", f"기본 차트: {e}")
    special = [c for c in ("cover", "divider", "back") if c in s.classes]
    if not special:
        has_chart = any(c in s.used_classes for c in CHART_CLASSES)
        if has_chart and NUM_RE.search(s.body_text) and not s.src:
            if s.attrs.get("data-nosrc") != "1":
                fail(page, "S1", "수치가 있는 도표에 출처 줄이 없다 (자사 집계라면 '출처: 자사 집계, 기간, 측정 조건'을 적는다)")
        if s.src and re.fullmatch(r"출처\s*[:：]?\s*", s.src):
            fail(page, "S1", "출처 줄이 비어 있다")
        if not s.kicker:
            warn(page, "S2", "키커(오른쪽 위의 주제 라벨)가 없다")
        if "on" not in s.used_classes and any(c in s.used_classes for c in ("bars", "colchart", "grp", "fnl", "sc", "dots", "mk", "db", "dv", "tg")):
            warn(page, "S3", "막대 도표에 강조한 막대가 없다. 헤드메시지가 말하는 항목 하나만 강조한다")
    if s.has_svg:
        warn(page, "S4", "SVG는 PPTX에서 그림으로 변환되어 편집할 수 없다. 부품의 div 도형으로 그린다")
    for st in s.inline_styles:
        if re.search(r"font-family", st):
            fail(page, "S5", f"글꼴을 인라인으로 지정하지 않는다 (Pretendard 고정): {st[:50]}")
        if re.search(r"(?<![-\w])(color|background)\s*:\s*#", st):
            fail(page, "S5", f"색을 HEX로 직접 쓰지 않고 토큰(var(--accent) 등)을 쓴다: {st[:50]}")
        if re.search(r"font-weight\s*:\s*(bold|[1-9]00)", st):
            warn(page, "S5", f"굵기는 클래스나 토큰(var(--w-head) 등)으로 지정한다: {st[:50]}")
        if re.search(r"border-radius|box-shadow|gradient|transform", st):
            fail(page, "S5", f"둥근 모서리, 그림자, 그라데이션, 변형을 쓰지 않는다: {st[:50]}")


def check_html(path, facts, forbid):
    p, raw = parse_html(path)
    slides = p.slides
    if not slides:
        fail(0, "S0", "슬라이드(section.slide)가 없다")
        return []
    if p.theme not in ("rose", "rose-panel", "berry", "navy-rose"):
        fail(0, "S0", f"data-theme이 '{p.theme}'이다. 팔레트 rose, rose-panel, berry, navy-rose 중 하나여야 한다 (new_deck.py --refresh-css <덱> --set-palette <팔레트>)")
    if "cover" not in slides[0].classes:
        warn(0, "S0", "첫 장이 표지가 아니다")
    if "back" not in slides[-1].classes:
        warn(0, "S0", "마지막 장이 뒤표지가 아니다. 마지막 장에는 메시지를 싣지 않는다")
    titles, labels = [], 0
    for s in slides:
        special = [c for c in ("cover", "divider", "back") if c in s.classes]
        if special:
            for path_, text in s.blocks:
                if "{{" in text:
                    fail(s.n, "C1", f"자리표시자가 남아 있다: {text[:40]}")
            for e in s.chart_errors:
                fail(s.n, "S7", f"기본 차트: {e}")
            continue
        label_ok = s.attrs.get("data-label") == "1"
        labels += label_ok
        check_headline(s.n, s.title, s.title_lines, label_ok, s.body_text + " " + s.src, s.src, facts)
        check_body(s)
        check_format(s, p.theme)
        titles.append((s.n, s.title))
    if labels > 2:
        fail(0, "H3", f"라벨 제목(data-label)을 {labels}장에 썼다. 회사 소개와 팀처럼 주장할 자리가 아닌 장 2개까지만 허용한다")
    check_headline_set(titles)
    if facts is not None:
        fact_nums = set(nums(facts))
        for s in slides:
            unknown = sorted({x for x in nums(s.body_text) if x not in fact_nums and len(x) > 1} - set(nums(s.title)))
            if unknown and not any(c in s.classes for c in ("cover", "divider", "back")):
                warn(s.n, "H10", f"본문의 수치 {unknown[:6]}이(가) 팩트 원장에 없다. 날짜나 번호가 아니라면 원장에 근거를 추가한다")
    if forbid:
        low = raw.lower()
        for w in forbid:
            if w.lower() in low:
                fail(0, "S6", "대외비 단어 목록에 있는 단어가 남아 있다 (주석과 속성 포함. 단어는 출력하지 않는다)")
                break
    return titles


def check_storyline(path, facts):
    """storyline.md의 번호 목록('1. 헤드메시지')에서 헤드메시지를 읽어 검사한다. 표와 그 밖의 줄은 읽지 않는다."""
    titles = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*(\d+)[.)]\s+(.+?)\s*$", line)
        if m:
            t = re.sub(r"\*\*|`", "", m.group(2)).strip()
            t = re.split(r"\s{2,}|\s+\(부품", t)[0]
            titles.append((int(m.group(1)), t))
    if not titles:
        fail(0, "S0", "storyline.md에서 헤드메시지를 찾지 못했다. '1. 헤드메시지' 형식의 번호 목록으로 쓴다")
    for n, t in titles:
        label_ok = t.startswith("[라벨]")
        t = t.replace("[라벨]", "").strip()
        if t.startswith("[표지]") or t.startswith("[뒤표지]") or t.startswith("[장 구분]"):
            continue
        check_headline(n, t, None, label_ok, facts=facts, storyline=True)
    check_headline_set([(n, t) for n, t in titles if not t.startswith("[")])
    return titles


def check_pptx(path):
    ok_faces = {"Pretendard", "Pretendard Light", "Pretendard Medium", "Pretendard SemiBold", "Pretendard ExtraBold", "Pretendard Black"}
    titles = []
    with zipfile.ZipFile(path) as z:
        names = sorted([n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)], key=lambda n: int(re.findall(r"\d+", n)[-1]))
        for i, name in enumerate(names, 1):
            xml = z.read(name).decode("utf-8")
            faces = set(re.findall(r'<a:(?:latin|ea) typeface="([^"+][^"]*)"', xml)) - ok_faces
            if faces:
                fail(i, "P1", f"Pretendard가 아닌 글꼴이 있다: {sorted(faces)[:4]}")
            pics = len(re.findall(r"<p:pic>", xml))
            if pics:
                warn(i, "P2", f"그림 {pics}개가 있다. 그림 안의 글자와 수치는 PowerPoint에서 편집할 수 없다 (로고와 제품 화면 이미지는 정상)")
            if re.search(r'<a:schemeClr val="(?!bg1|tx1|bg2|tx2|accent[1-6]|hlink|folHlink|dk1|lt1|dk2|lt2|phClr)', xml):
                fail(i, "P3", "테마 색 이름이 잘못되었다. PowerPoint가 파일을 열지 못한다")
            if "{{" in htmllib.unescape(re.sub(r"<[^>]+>", "", xml)):
                fail(i, "C1", "자리표시자가 남아 있다")
            m = re.search(r'<p:ph type="title"/>.*?</p:sp>', xml, flags=re.S)
            if m:
                titles.append((i, htmllib.unescape(" ".join(re.findall(r"<a:t>([^<]*)</a:t>", m.group(0))))))
        for name in sorted(n for n in z.namelist() if re.match(r"ppt/charts/chart\d+\.xml$", n)):
            xml = z.read(name).decode("utf-8")
            faces = set(re.findall(r'<a:(?:latin|ea) typeface="([^"+][^"]*)"', xml)) - ok_faces
            if faces:
                fail(0, "P1", f"차트 {name.rsplit('/', 1)[-1]}에 Pretendard가 아닌 글꼴이 있다: {sorted(faces)[:4]}")
            if "{{" in htmllib.unescape(re.sub(r"<[^>]+>", " ", xml)):
                fail(0, "C1", f"차트 {name.rsplit('/', 1)[-1]}의 항목 이름이나 계열 이름에 자리표시자가 남아 있다")
        theme = z.read("ppt/theme/theme1.xml").decode("utf-8")
        if 'typeface="Pretendard' not in theme:
            fail(0, "P1", "테마 글꼴이 Pretendard가 아니다")
    return titles


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--facts", help="팩트 원장 파일. 지정하지 않으면 덱과 같은 폴더의 facts.md를 쓴다")
    ap.add_argument("--storyline", action="store_true", help="storyline.md의 헤드메시지만 검사한다")
    ap.add_argument("--forbid", help="대외비 단어를 한 줄에 하나씩 적은 파일")
    ap.add_argument("--strict", action="store_true", help="WARN도 실패로 처리한다")
    a = ap.parse_args()

    f = Path(a.file)
    facts_path = Path(a.facts) if a.facts else next((d / "facts.md" for d in (f.parent, f.parent.parent) if (d / "facts.md").exists()), None)
    facts = facts_path.read_text(encoding="utf-8") if facts_path and facts_path.exists() else None
    forbid = [w.strip() for w in Path(a.forbid).expanduser().read_text(encoding="utf-8").splitlines() if w.strip()] if a.forbid else []

    if f.suffix == ".pptx":
        titles = check_pptx(f)
    elif a.storyline or f.suffix == ".md":
        titles = check_storyline(f, facts)
    else:
        titles = check_html(f, facts, forbid)

    print(f"── 헤드메시지 통독 ({len(titles)}개) : 위에서 아래로 이어 읽어 한 편의 이야기가 되는지 사람이 확인한다 ──")
    for n, t in titles:
        print(f"  {n:>2}. {t}")
    print(f"\n팩트 원장: {facts_path if facts is not None else '없음 (수치 대조를 건너뜀)'}")
    for m in fails:
        print("FAIL  " + m)
    for m in warns:
        print("WARN  " + m)
    print(f"\nFAIL {len(fails)} / WARN {len(warns)}")
    sys.exit(1 if fails or (a.strict and warns) else 0)


if __name__ == "__main__":
    main()
