#!/usr/bin/env python3
"""기업 로고를 찾아 배경이 투명한 PNG로 만든다. 후보 수집 → 배경 제거 → 자동 검사를 통과할 때까지 후보와 방식을 바꿔 가며 되풀이한다.

  .venv/bin/python scripts/logo.py get "올리브영" --site oliveyoung.co.kr
  .venv/bin/python scripts/logo.py get "Coupang" --wiki "Coupang logo"          # 위키미디어 공용에서 찾기
  .venv/bin/python scripts/logo.py get "고객사A" --url https://.../logo.svg     # 주소를 직접 지정
  .venv/bin/python scripts/logo.py get "고객사B" --file ~/Downloads/logo.jpg    # 가진 파일의 배경만 제거
  .venv/bin/python scripts/logo.py get "올리브영" --site oliveyoung.co.kr --pick 3 --mode key   # 미리보기를 보고 후보와 방식을 바꿔 다시
  .venv/bin/python scripts/logo.py get "올리브영" --site oliveyoung.co.kr --mono "#8A8F98"      # 로고 모음용 단색판도 함께
  .venv/bin/python scripts/logo.py get "올리브영" --site oliveyoung.co.kr --deck decks/2026-10-x  # 덱 폴더의 assets/logos에도 복사
  .venv/bin/python scripts/logo.py sheet                                          # 모아 둔 로고 전체를 한 장으로 보기

결과 (기본 위치 assets/logos/):
  <이름>.png            배경이 투명한 로고 (여백을 잘라내고 긴 변을 1600px 이하로 맞춤)
  <이름>.mono.png       단색판 (--mono를 준 경우)
  <이름>.json           출처 주소, 쓴 방식, 검사 결과, 시도한 후보 전체
  _preview/<이름>.png   흰 바탕·어두운 바탕·브랜드 색 바탕에 올린 모습과 후보 목록 (반드시 눈으로 확인한다)

배경 제거 방식 (--mode):
  auto       아래 둘 중에서 고른다. 로고가 색으로 채운 상자 모양이면 connected, 글자와 선으로 된 로고면 key
  connected  바깥 가장자리에서 이어진 배경만 지운다. 로고 안쪽의 흰 글자는 남는다 (색 상자 안의 흰 글자 로고)
  key        배경과 같은 색을 전부 지운다. 글자 안쪽의 막힌 공간(o, a, ㅁ)까지 뚫린다 (흰 바탕 위의 글자 로고)
  none       이미 투명한 파일이므로 여백만 잘라낸다
종료 코드: 검사를 통과한 후보가 없으면 1.
"""
import argparse
import html as htmllib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "logos"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept-Language": "ko,en;q=0.8"}
MAX_BYTES = 8 * 1024 * 1024
LONG_SIDE = 1600
NOISE = ("footer", "partner", "client", "customer", "sns", "banner", "kakao", "facebook", "instagram", "youtube", "twitter",
         "naver", "appstore", "app-store", "googleplay", "google-play", "badge", "award", "cert", "payment", "card", "sprite", "loading", "btn", "arrow")


# ── 후보 수집 ──────────────────────────────────────────────────────────────
def fetch(url, limit=MAX_BYTES, referer=None):
    req = urllib.request.Request(url, headers=dict(UA, **({"Referer": referer} if referer else {})))
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read(limit + 1)
        if len(data) > limit:
            raise ValueError("파일이 8MB를 넘는다")
        return data, r.headers.get("Content-Type", ""), r.geturl()


def attr(tag, name):
    m = re.search(rf'\b{name}\s*=\s*("([^"]*)"|\'([^\']*)\'|([^\s>]+))', tag, flags=re.I)
    return htmllib.unescape(m.group(2) or m.group(3) or m.group(4) or "") if m else ""


def browser_candidates(site, brand, capdir):
    """Chrome으로 홈페이지를 열어 화면에 그려진 로고 요소를 찾는다 (engine/site_logos.mjs).
    자동 요청을 막는 사이트, SVG 조각이나 CSS 배경으로 그린 로고까지 잡는다."""
    base = site if site.startswith("http") else "https://" + site
    capdir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["node", str(ROOT / "engine" / "site_logos.mjs"), base, str(capdir), brand], capture_output=True, text=True, timeout=120)
    f = capdir / "site.json"
    if r.returncode != 0 or not f.exists():
        print(f"  Chrome으로 홈페이지를 열지 못했다: {r.stderr.strip()[:120]}")
        return []
    data = json.loads(f.read_text(encoding="utf-8"))
    print(f"  연 페이지: {data.get('href', '')[:80]} ({data.get('title', '')[:30]})")
    out = []
    for c in data.get("candidates", []):
        cap = str(capdir / c["capture"]) if c.get("capture") else None
        where = {"img": "홈페이지 이미지", "svg": "홈페이지에 그려진 SVG", "bg": "홈페이지의 CSS 배경 이미지"}[c["kind"]]
        if c["kind"] == "img" and c.get("src", "").startswith("http"):
            # 원본 파일이 화면에 찍은 것보다 해상도가 높으므로 원본을 먼저 받고, 막히면 화면에서 찍은 것을 쓴다
            out.append({"url": c["src"], "fallback": cap, "from": where, "score": 100 + c["score"], "alt": c.get("alt", ""), "referer": data.get("href", "")})
        elif cap:
            out.append({"file": cap, "vector": c["kind"] == "svg", "from": where + " (화면에서 따냄)", "score": 100 + c["score"], "alt": c.get("alt", "")})
    return out


def site_candidates(site, brand):
    """Chrome 없이 홈페이지의 HTML만 읽어서 찾는다 (browser_candidates가 아무것도 찾지 못했을 때의 예비 경로)."""
    base = site if site.startswith("http") else "https://" + site
    try:
        raw, _, final = fetch(base, 3 * 1024 * 1024)
    except Exception as e:
        print(f"  홈페이지를 읽지 못했다 ({base}): {e}")
        return []
    page = raw.decode("utf-8", "replace")
    label = urllib.parse.urlparse(final).netloc.replace("www.", "").split(".")[0].lower()
    keys = {label, brand.lower().replace(" ", "")}
    out = []

    def score(text, pos, kind):
        t = text.lower()
        s = 0
        s += 40 if "logo" in t else 0
        s += 25 if any(k and k in t.replace(" ", "") for k in keys) else 0
        s += 20 if kind == "svg" else 0
        s += 15 * (1 - pos / max(len(page), 1))           # 머리 영역에 가까울수록 자사 로고일 가능성이 높다
        s -= 45 if any(n in t for n in NOISE) else 0      # 홈페이지에 실린 다른 회사 로고와 아이콘을 거른다
        return s

    for m in re.finditer(r"<img\b[^>]*>", page, flags=re.I):
        tag = m.group(0)
        src = attr(tag, "src") or attr(tag, "data-src") or attr(tag, "data-lazy-src")
        if not src and attr(tag, "srcset"):
            src = attr(tag, "srcset").split(",")[-1].strip().split(" ")[0]
        if not src or src.startswith("data:"):
            continue
        ctx = page[max(0, m.start() - 300):m.start()]      # 감싸고 있는 요소의 class까지 본다
        text = " ".join([src, attr(tag, "alt"), attr(tag, "class"), attr(tag, "id"), re.sub(r"\s+", " ", ctx[-200:])])
        kind = "svg" if ".svg" in src.lower() else "img"
        s = score(text, m.start(), kind)
        if s >= 35:
            out.append({"url": urllib.parse.urljoin(final, src), "from": "홈페이지 img", "score": s, "alt": attr(tag, "alt")})
    # 머리 영역의 로고 요소 안에 직접 그려 넣은 SVG
    for m in re.finditer(r"<(a|div|h1|span|header|button)\b[^>]*\blogo\b[^>]*>(.{0,6000}?)</\1>", page, flags=re.I | re.S):
        sv = re.search(r"<svg\b.*?</svg>", m.group(2), flags=re.I | re.S)
        if sv and len(sv.group(0)) > 300 and "<use" not in sv.group(0).lower():
            out.append({"svg": sv.group(0), "from": "홈페이지에 직접 그린 SVG", "score": 60 + score(m.group(0)[:300], m.start(), "svg"), "alt": ""})
    for m in re.finditer(r"<link\b[^>]*>", page, flags=re.I):
        tag, rel, href = m.group(0), attr(m.group(0), "rel").lower(), attr(m.group(0), "href")
        if not href:
            continue
        if "icon" in rel and href.lower().endswith(".svg"):
            out.append({"url": urllib.parse.urljoin(final, href), "from": "SVG 파비콘", "score": 30, "alt": ""})
        elif "apple-touch-icon" in rel:
            out.append({"url": urllib.parse.urljoin(final, href), "from": "앱 아이콘 (심벌만 있을 수 있다)", "score": 12, "alt": ""})
    m = re.search(r'<meta\b[^>]*property=["\']og:image["\'][^>]*>', page, flags=re.I)
    if m and attr(m.group(0), "content"):
        out.append({"url": urllib.parse.urljoin(final, attr(m.group(0), "content")), "from": "대표 이미지 og:image (사진일 수 있다)", "score": 5, "alt": ""})
    seen, uniq = set(), []
    for c in sorted(out, key=lambda c: -c["score"]):
        k = c.get("url") or c["svg"][:200]
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq


def wiki_candidates(query):
    """위키미디어 공용에서 로고 파일을 찾는다. SVG는 1200px PNG로 받아 투명 배경이 유지된다."""
    api = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 8,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1200})
    try:
        data = json.loads(fetch(api)[0].decode("utf-8"))
    except Exception as e:
        print(f"  위키미디어 공용을 읽지 못했다: {e}")
        return []
    out = []
    for p in sorted((data.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99)):
        ii = (p.get("imageinfo") or [{}])[0]
        mime, title = ii.get("mime", ""), p.get("title", "")
        if mime not in ("image/svg+xml", "image/png") or not ii.get("thumburl"):
            continue
        lic = ((ii.get("extmetadata") or {}).get("LicenseShortName") or {}).get("value", "")
        s = 50 - p.get("index", 9) * 3 + (15 if "logo" in title.lower() else 0) + (8 if mime == "image/svg+xml" else 0)
        out.append({"url": ii["thumburl"], "from": f"위키미디어 공용: {title}" + (f" ({lic})" if lic else ""), "score": s, "alt": title,
                    "page": ii.get("descriptionurl", "")})
    return out


# ── 불러오기 ──────────────────────────────────────────────────────────────
def render_svg(svg_path, png_path):
    r = subprocess.run(["node", str(ROOT / "engine" / "svg_to_png.mjs"), str(svg_path), str(png_path), "1200"],
                       capture_output=True, text=True, timeout=90)
    if r.returncode != 0:
        raise ValueError("SVG를 그리지 못했다: " + r.stderr.strip()[:120])


def load(cand, work, n):
    """후보 하나를 RGBA 이미지로 불러온다. (이미지, 원본 형식)을 돌려준다."""
    if cand.get("svg"):
        svg = cand["svg"]
        if "xmlns=" not in svg[:400]:
            svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
        f = work / f"{n:02d}.svg"
        f.write_text(svg, encoding="utf-8")
        render_svg(f, work / f"{n:02d}.png")
        return Image.open(work / f"{n:02d}.png").convert("RGBA"), "svg"
    if cand.get("file"):
        data, ctype, name = Path(cand["file"]).expanduser().read_bytes(), "", str(cand["file"])
    else:
        try:
            data, ctype, name = fetch(cand["url"], referer=cand.get("referer"))
        except Exception:
            if not cand.get("fallback"):
                raise
            cand["from"] += " (원본을 받지 못해 화면에서 따냄)"
            return Image.open(cand["fallback"]).convert("RGBA"), "png"
    is_svg = "svg" in ctype or name.lower().split("?")[0].endswith(".svg") or data.lstrip()[:200].lower().find(b"<svg") >= 0
    if is_svg:
        f = work / f"{n:02d}.svg"
        f.write_bytes(data)
        render_svg(f, work / f"{n:02d}.png")
        return Image.open(work / f"{n:02d}.png").convert("RGBA"), "svg"
    f = work / f"{n:02d}.bin"
    f.write_bytes(data)
    try:
        im = Image.open(f)
        im.seek(0)
    except Exception:
        if not cand.get("fallback"):
            raise
        cand["from"] += " (원본 형식을 읽지 못해 화면에서 따냄)"
        return Image.open(cand["fallback"]).convert("RGBA"), "png"
    return im.convert("RGBA"), ("svg" if cand.get("vector") else (im.format or "?").lower())


# ── 배경 제거 ──────────────────────────────────────────────────────────────
class NotFlat(Exception):
    pass


def remove_bg(im, mode):
    """(결과 RGBA 배열 float 0~1, 실제로 쓴 방식, 참고 정보)를 돌려준다."""
    a = np.asarray(im, dtype=np.float32)
    rgb, alpha = a[..., :3], a[..., 3] / 255.0
    h, w = alpha.shape
    info = {}
    if mode == "none" or (mode == "auto" and (alpha < 0.98).mean() > 0.02):
        return np.dstack([rgb / 255.0, alpha]), "none", info
    b = max(2, min(h, w) // 100)
    border = np.concatenate([rgb[:b].reshape(-1, 3), rgb[-b:].reshape(-1, 3), rgb[:, :b].reshape(-1, 3), rgb[:, -b:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    flat = float((np.abs(border - bg).max(axis=1) <= 14).mean())
    info.update(bg="#%02X%02X%02X" % tuple(int(v) for v in bg), border_flat=round(flat, 3))
    if flat < 0.92:
        raise NotFlat(f"가장자리가 단색이 아니다 (같은 색인 비율 {flat:.0%}). 사진이거나 무늬 배경이다")
    d = np.abs(rgb - bg).max(axis=2)
    ink = d > 40
    if not ink.any():
        raise NotFlat("배경과 구분되는 로고가 없다")
    ys, xs = np.where(ink)
    fill = float(ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1].mean())
    info["ink_fill"] = round(fill, 3)
    if mode == "auto":
        mode = "connected" if fill > 0.5 else "key"       # 채운 상자 모양이면 안쪽 흰색을 남기고, 글자와 선이면 전부 뚫는다
    soft = np.clip((d - 10.0) / 38.0, 0.0, 1.0)            # 배경과의 색 거리로 가장자리의 반투명도를 어림한다
    if mode == "key":
        A = soft
    else:
        mask = Image.fromarray(np.where(d <= 24, 255, 0).astype(np.uint8), "L")
        padded = Image.new("L", (w + 2, h + 2), 255)
        padded.paste(mask, (1, 1))
        ImageDraw.floodfill(padded, (0, 0), 128)            # 바깥 가장자리에서 이어진 배경만 표시한다
        outside = (np.asarray(padded)[1:-1, 1:-1] == 128)
        outside = np.asarray(Image.fromarray((outside * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0   # 경계의 번진 픽셀까지
        A = np.where(outside, soft, 1.0)
    # 반투명 픽셀에 섞여 있는 배경색을 빼낸다 (어두운 바탕에 올렸을 때 흰 테두리가 남지 않게)
    A3 = np.clip(A, 1e-3, 1)[..., None]
    fg = np.clip((rgb - (1 - A3) * bg) / A3, 0, 255)
    rgb2 = np.where((A[..., None] > 0) & (A[..., None] < 1), fg, rgb)
    return np.dstack([rgb2 / 255.0, A]), mode, info


def trim(arr):
    A = arr[..., 3]
    ys, xs = np.where(A > 0.04)
    if len(ys) == 0:
        return arr, 1.0
    h, w = A.shape
    edge = np.concatenate([A[0], A[-1], A[:, 0], A[:, -1]])
    border_clear = float((edge < 0.05).mean())
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    pad = int(max(y1 - y0, x1 - x0) * 0.03) + 2
    canvas = np.zeros((y1 - y0 + 2 * pad, x1 - x0 + 2 * pad, 4), dtype=arr.dtype)
    canvas[pad:pad + y1 - y0, pad:pad + x1 - x0] = arr[y0:y1, x0:x1]
    return canvas, border_clear


def to_image(arr):
    im = Image.fromarray((np.clip(arr, 0, 1) * 255).round().astype(np.uint8))
    if max(im.size) > LONG_SIDE:
        k = LONG_SIDE / max(im.size)
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    return im


# ── 자동 검사 ──────────────────────────────────────────────────────────────
def qa(arr, border_clear, fmt, mode):
    A, rgb = arr[..., 3], arr[..., :3]
    h, w = A.shape
    clear, opaque = float((A < 0.05).mean()), (A > 0.95)
    semi = (A >= 0.05) & (A <= 0.95)
    out = []
    if clear < 0.04:
        out.append(("FAIL", "Q1", f"투명한 영역이 {clear:.0%}뿐이다. 배경이 지워지지 않았다"))
    if clear > 0.975:
        out.append(("FAIL", "Q1", f"투명한 영역이 {clear:.0%}다. 로고까지 지워졌다 (배경과 색이 가까운 로고일 수 있다. --mode connected로 다시)"))
    # 원래 투명한 파일(mode none)은 로고에 딱 맞게 잘려 있는 경우가 많으므로 가장자리 검사를 하지 않는다
    if mode != "none" and border_clear < 0.97:
        out.append(("FAIL", "Q2", f"가장자리의 {1 - border_clear:.0%}가 불투명하다. 로고가 잘렸거나 배경이 남았다"))
    vis = opaque.sum() + semi.sum()
    if vis and semi.sum() / vis > 0.35:
        out.append(("FAIL", "Q3", f"보이는 영역의 {semi.sum() / vis:.0%}가 반투명이다. 흐린 이미지이거나 그라데이션 배경이다"))
    long_side = max(h, w)
    if long_side < 120:
        out.append(("FAIL", "Q4", f"긴 변이 {long_side}px이다. 슬라이드에 쓰기에 너무 작다"))
    elif long_side < 400 and fmt != "svg":
        out.append(("WARN", "Q4", f"긴 변이 {long_side}px이다. 표지처럼 크게 쓰면 흐려 보인다 (로고 모음에는 쓸 수 있다)"))
    if opaque.any():
        lum = float((rgb[opaque] @ np.array([0.299, 0.587, 0.114])).mean())
        if lum > 0.92:
            out.append(("WARN", "Q5", "거의 흰색인 로고다. 흰 슬라이드에서는 보이지 않으므로 --mono로 단색판을 만들거나 어두운 판을 찾는다"))
    ratio = w / h
    if ratio > 12 or ratio < 1 / 6:
        out.append(("WARN", "Q6", f"가로세로 비율이 {ratio:.1f}:1이다. 로고가 아니라 띠 이미지일 수 있다"))
    if abs(ratio - 1) < 0.08 and opaque.mean() > 0.80:
        out.append(("WARN", "Q7", "정사각형을 거의 다 채운 이미지다. 워드마크가 아니라 앱 아이콘이나 심벌일 수 있다"))
    return out


# ── 미리보기 ──────────────────────────────────────────────────────────────
def font(size):
    for f in (Path.home() / "Library/Fonts/Pretendard-Medium.otf", ROOT / "design/fonts/Pretendard-Medium.otf"):
        if f.exists():
            return ImageFont.truetype(str(f), size)
    return ImageFont.load_default()


def fit(im, bw, bh):
    k = min(bw / im.width, bh / im.height)
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)


def preview(result, attempts, thumbs, path, title):
    W, PH, n = 1260, 250, 4
    rows = (len(thumbs) + 5) // 6
    sheet = Image.new("RGB", (W, 46 + PH + 40 + rows * 150 + 16), "#FFFFFF")
    dr = ImageDraw.Draw(sheet)
    dr.text((16, 12), title, fill="#18181C", font=font(20))
    pw = (W - 16 * (n + 1)) // n
    for i, (bg, name) in enumerate([("#FFFFFF", "흰 바탕"), ("#18181C", "어두운 바탕"), ("#D9415F", "브랜드 색 바탕"), (None, "투명 확인")]):
        x = 16 + i * (pw + 16)
        panel = Image.new("RGB", (pw, PH - 30), bg or "#FFFFFF")
        if bg is None:
            pd = ImageDraw.Draw(panel)
            for yy in range(0, PH, 14):
                for xx in range(0, pw, 14):
                    if (xx // 14 + yy // 14) % 2:
                        pd.rectangle([xx, yy, xx + 13, yy + 13], fill="#D8D8DC")
        if result is not None:
            lg = fit(result, pw - 70, PH - 100)
            panel.paste(lg, ((pw - lg.width) // 2, (PH - 30 - lg.height) // 2), lg)
        sheet.paste(panel, (x, 46))
        dr.rectangle([x, 46, x + pw - 1, 46 + PH - 31], outline="#C8C8CE")
        dr.text((x, 46 + PH - 26), name, fill="#667085", font=font(14))
    y0 = 46 + PH + 8
    dr.text((16, y0), "후보 (번호는 --pick에 쓴다. 초록 = 검사 통과, 빨강 = 실패)", fill="#18181C", font=font(15))
    for i, (num, th, status) in enumerate(thumbs):
        x, y = 16 + (i % 6) * 208, y0 + 30 + (i // 6) * 150
        cell = Image.new("RGB", (196, 112), "#F1F2F4")
        if th is not None:
            t = fit(th, 176, 92)
            cell.paste(t, ((196 - t.width) // 2, (112 - t.height) // 2), t)
        sheet.paste(cell, (x, y))
        dr.rectangle([x, y, x + 195, y + 111], outline={"ok": "#1E9E5A", "fail": "#C0392B", "picked": "#1D4E9E"}.get(status, "#C8C8CE"), width=3)
        dr.text((x + 6, y + 114), f"{num}" + ("  선택됨" if status == "picked" else ""), fill="#18181C", font=font(14))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


# ── 실행 ──────────────────────────────────────────────────────────────────
def slugify(name):
    s = re.sub(r"[^\w가-힣-]+", "-", name.strip().lower()).strip("-")
    return s or "logo"


def cmd_get(a):
    slug = a.slug or slugify(a.name)
    cands = []
    for f in a.file or []:
        cands.append({"file": f, "from": "지정한 파일", "score": 200})
    for u in a.url or []:
        cands.append({"url": u, "from": "지정한 주소", "score": 190})
    if a.site:
        print(f"■ 홈페이지에서 찾기: {a.site}")
        found = browser_candidates(a.site, a.name, a.out / "_candidates" / slug)
        cands += found or site_candidates(a.site, a.name)
    if a.wiki or not cands:
        q = a.wiki or f"{a.name} logo"
        print(f"■ 위키미디어 공용에서 찾기: {q}")
        cands += wiki_candidates(q)
    elif a.site and not a.no_wiki:
        # 홈페이지의 로고는 해상도가 낮은 경우가 많다. 이름이 맞는 위키미디어 공용의 파일을 뒤쪽 후보로 함께 둔다
        label = urllib.parse.urlparse(a.site if a.site.startswith("http") else "https://" + a.site).netloc.replace("www.", "").split(".")[0].lower()
        extra = [c for c in wiki_candidates(f"{label} logo") if label in c["alt"].lower().replace(" ", "")]
        for c in extra:
            c["score"] -= 60
        if extra:
            print(f"■ 위키미디어 공용에서 이름이 맞는 파일 {len(extra)}개를 예비 후보로 더했다")
        cands += extra
    cands = sorted(cands, key=lambda c: -c["score"])[:a.max]
    if not cands:
        sys.exit("후보를 하나도 찾지 못했다. --site, --wiki, --url, --file 가운데 하나를 준다")

    attempts, thumbs, accepted, passed = [], [], None, []
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        for n, c in enumerate(cands, 1):
            src = c.get("url") or c.get("file") or "(홈페이지에 직접 그린 SVG)"
            rec = {"n": n, "from": c["from"], "source": src, "page": c.get("page", ""), "tries": []}
            attempts.append(rec)
            try:
                im, fmt = load(c, work, n)
            except Exception as e:
                rec["error"] = f"불러오지 못했다: {str(e)[:100]}"
                thumbs.append((n, None, "fail"))
                print(f"  {n}. 실패  {c['from']}: {rec['error']}")
                continue
            rec["format"], rec["size"] = fmt, list(im.size)
            ok_try = None
            modes = [a.mode] if a.mode != "auto" else ["auto", None]
            for mode in modes:
                if mode is None:                               # auto가 고른 방식이 실패했으면 다른 방식으로 한 번 더
                    used = rec["tries"][-1].get("mode")
                    if used not in ("connected", "key") or not any(l == "FAIL" for l, _, _ in rec["tries"][-1]["checks"]):
                        break
                    mode = "key" if used == "connected" else "connected"
                try:
                    arr, used, info = remove_bg(im, mode)
                    arr, border_clear = trim(arr)
                    checks = qa(arr, border_clear, fmt, used)
                except NotFlat as e:
                    used, info, arr, checks = mode, {}, None, [("FAIL", "Q0", str(e))]
                rec["tries"].append({"mode": used, "info": info, "checks": checks})
                if arr is not None and not any(l == "FAIL" for l, _, _ in checks):
                    ok_try = (arr, used, checks)
                    break
            status = "ok" if ok_try else "fail"
            line = f"  {n}. {'통과' if ok_try else '실패'}  {c['from']} [{fmt}, {im.width}x{im.height}]"
            if ok_try:
                line += f" 방식 {ok_try[1]}"
            else:
                line += " : " + "; ".join(m for t in rec["tries"] for l, _, m in t["checks"] if l == "FAIL")[:150]
            print(line)
            if ok_try:
                passed.append((n, max(ok_try[0].shape[:2]), fmt))
            want = (a.pick == n) if a.pick else (ok_try is not None and accepted is None)
            if want and ok_try:
                accepted = {"n": n, "arr": ok_try[0], "mode": ok_try[1], "checks": ok_try[2], "cand": c, "format": fmt}
                status = "picked"
            thumbs.append((n, im.copy(), status))

        a.out.mkdir(parents=True, exist_ok=True)
        report = {"name": a.name, "slug": slug, "accepted": None, "attempts": attempts}
        result = None
        if accepted:
            result = to_image(accepted["arr"])
            result.save(a.out / f"{slug}.png")
            report["accepted"] = {"candidate": accepted["n"], "mode": accepted["mode"], "format": accepted["format"], "size": list(result.size),
                                  "source": accepted["cand"].get("url") or accepted["cand"].get("file") or "홈페이지에 직접 그린 SVG",
                                  "from": accepted["cand"]["from"], "page": accepted["cand"].get("page", ""),
                                  "checks": accepted["checks"]}
            if a.mono:
                rgba = np.asarray(result, dtype=np.float32) / 255.0
                col = np.array([int(a.mono.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0
                mono = np.dstack([np.broadcast_to(col, rgba[..., :3].shape), rgba[..., 3]])
                to_image(mono).save(a.out / f"{slug}.mono.png")
                report["accepted"]["mono"] = a.mono
            if a.deck:
                dst = Path(a.deck) / "assets" / "logos"
                dst.mkdir(parents=True, exist_ok=True)
                for f in a.out.glob(f"{slug}*.png"):
                    shutil.copy(f, dst / f.name)
                report["accepted"]["copied_to"] = str(dst)
        (a.out / f"{slug}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        prev = a.out / "_preview" / f"{slug}.png"
        preview(result, attempts, thumbs, prev, f"{a.name}" + (f"  |  후보 {accepted['n']}, 방식 {accepted['mode']}" if accepted else "  |  통과한 후보 없음"))

    print()
    if not accepted:
        print(f"검사를 통과한 후보가 없다. 미리보기에서 후보를 확인한다: {prev}")
        print("다음에 해 볼 것: --wiki \"영문 회사명 logo\", 로고 파일 주소를 --url로 지정, 가진 파일을 --file로 지정, --pick N --mode connected|key")
        sys.exit(1)
    print(f"로고    : {a.out / (slug + '.png')} ({result.width}x{result.height}, 후보 {accepted['n']}, 방식 {accepted['mode']})")
    print(f"출처    : {report['accepted']['source'][:110]}")
    for level, code, msg in accepted["checks"]:
        print(f"{level}  [{code}] {msg}")
    better = [(n, size) for n, size, fmt in passed if n != accepted["n"] and size >= max(result.size) * 1.8 and max(result.size) < 600]
    if better:
        print("참고    : 해상도가 더 높은 통과 후보가 있다 → " + ", ".join(f"후보 {n} ({size}px)" for n, size in better) + ". 미리보기에서 같은 로고인지 확인한 뒤 --pick으로 바꾼다")
    print(f"미리보기: {prev}")
    print("미리보기를 눈으로 확인한다: 그 회사의 로고가 맞는가, 글자 안쪽이 뚫려야 할 곳이 뚫렸는가, 어두운 바탕에서 흰 테두리가 남지 않는가.")


def cmd_sheet(a):
    files = sorted(f for f in a.out.glob("*.png") if not f.name.endswith(".mono.png"))
    if not files:
        sys.exit(f"{a.out}에 로고가 없다")
    cols = 5
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 250 + 10, rows * 300 + 10), "#FFFFFF")
    dr = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGBA")
        x, y = 10 + (i % cols) * 250, 10 + (i // cols) * 300
        for k, bg in enumerate(("#FFFFFF", "#18181C")):
            cell = Image.new("RGB", (240, 128), bg)
            t = fit(im, 200, 96)
            cell.paste(t, ((240 - t.width) // 2, (128 - t.height) // 2), t)
            sheet.paste(cell, (x, y + k * 132))
            dr.rectangle([x, y + k * 132, x + 239, y + k * 132 + 127], outline="#C8C8CE")
        dr.text((x, y + 268), f.stem[:28], fill="#18181C", font=font(14))
    out = a.out / "_preview" / "_all.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"{len(files)}개: {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get", help="로고를 찾아 투명 PNG로 만든다")
    g.add_argument("name", help="회사 이름 (파일 이름과 검색에 쓴다)")
    g.add_argument("--site", help="회사 홈페이지 도메인. 예: oliveyoung.co.kr")
    g.add_argument("--wiki", help="위키미디어 공용 검색어. 예: \"Coupang logo\"")
    g.add_argument("--url", action="append", help="로고 이미지 주소 (여러 번 줄 수 있다)")
    g.add_argument("--file", action="append", help="가지고 있는 로고 파일")
    g.add_argument("--mode", default="auto", choices=["auto", "connected", "key", "none"])
    g.add_argument("--pick", type=int, help="미리보기의 후보 번호를 지정해서 그 후보를 쓴다")
    g.add_argument("--mono", help="단색판의 색 HEX. 예: #8A8F98")
    g.add_argument("--slug", help="파일 이름 (기본값은 회사 이름)")
    g.add_argument("--deck", help="덱 폴더. 지정하면 그 폴더의 assets/logos에도 복사한다")
    g.add_argument("--max", type=int, default=8, help="시도할 후보의 최대 개수")
    g.add_argument("--no-wiki", action="store_true", help="위키미디어 공용의 예비 후보를 더하지 않는다")
    g.add_argument("--out", type=Path, default=OUT)
    s = sub.add_parser("sheet", help="모아 둔 로고 전체를 한 장으로 본다")
    s.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    cmd_get(a) if a.cmd == "get" else cmd_sheet(a)


if __name__ == "__main__":
    main()
