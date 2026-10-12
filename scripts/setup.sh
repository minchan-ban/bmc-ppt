#!/usr/bin/env bash
# bmc-ppt 실행 환경을 확인하고 준비한다.
#   bash scripts/setup.sh --check   # 확인만 한다 (아무것도 바꾸지 않는다)
#   bash scripts/setup.sh           # 빠진 것을 준비한다: .venv와 python-pptx, Pretendard의 빠진 굵기, humanize-korean 스킬 연결
set -u
cd "$(dirname "$0")/.."
CHECK_ONLY=0; [ "${1:-}" = "--check" ] && CHECK_ONLY=1
MISSING=0
ok()   { echo "  확인  $1"; }
miss() { echo "  없음  $1"; MISSING=$((MISSING + 1)); }

echo "■ 실행 도구"
if command -v node >/dev/null && [ "$(node -p 'process.versions.node.split(".")[0]')" -ge 22 ]; then ok "Node $(node --version)"; else miss "Node 22 이상 (Chrome을 조작하는 데 쓴다)"; fi
if [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then ok "Google Chrome"; else miss "Google Chrome (화면 검사, PPTX 변환, PDF에 쓴다)"; fi
if [ -d "/Applications/Microsoft PowerPoint.app" ]; then ok "Microsoft PowerPoint"; else echo "  참고  PowerPoint가 없다. PPTX는 만들어지지만 이 컴퓨터에서 열어 볼 수 없다"; fi
if command -v pdftoppm >/dev/null; then ok "pdftoppm (미리보기 PNG)"; else echo "  참고  pdftoppm이 없다. --preview를 쓰려면 'brew install poppler'"; fi

echo "■ Python 가상환경"
if [ -x .venv/bin/python ] && .venv/bin/python -c "import pptx, lxml, PIL, numpy" 2>/dev/null; then ok ".venv와 python-pptx, Pillow, numpy"
elif [ $CHECK_ONLY = 1 ]; then miss ".venv와 python-pptx, Pillow, numpy"
else python3 -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q python-pptx pillow numpy && ok ".venv를 만들고 python-pptx, Pillow, numpy를 설치했다"; fi

echo "■ Pretendard 글꼴 (굵기별)"
for w in Light Regular Medium SemiBold Bold ExtraBold; do
  if compgen -G "$HOME/Library/Fonts/Pretendard-$w.*" >/dev/null || compgen -G "/Library/Fonts/Pretendard-$w.*" >/dev/null; then ok "Pretendard $w"
  elif [ $CHECK_ONLY = 1 ]; then miss "Pretendard $w"
  else cp "design/fonts/Pretendard-$w.otf" "$HOME/Library/Fonts/" && ok "Pretendard $w를 ~/Library/Fonts에 설치했다"; fi
done

echo "■ 문체 교정 스킬 (im-not-ai)"
if [ -e .claude/skills/humanize-korean/SKILL.md ]; then ok "/humanize-korean 스킬 연결"
elif [ $CHECK_ONLY = 1 ]; then miss "/humanize-korean 스킬 연결"
else mkdir -p .claude/skills && ln -sfn ../../vendor/im-not-ai/skills/humanize-korean .claude/skills/humanize-korean && ok "/humanize-korean 스킬을 연결했다"; fi

echo
if [ $MISSING -gt 0 ]; then echo "빠진 항목 ${MISSING}개. 'bash scripts/setup.sh'로 준비한다 (Node와 Chrome은 직접 설치한다)."; exit 1; fi
echo "준비 완료."
