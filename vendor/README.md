# vendor: 가져온 외부 프로젝트

세 프로젝트 모두 MIT 라이선스다. 각 폴더의 `LICENSE` 파일을 지우지 않는다.
가져온 시점의 커밋을 아래에 적었고, 폴더 안의 파일은 고치지 않았다. 이 프로젝트에 맞게 고친 파일은 `engine/`과 `harness/`에 사본으로 두었다.

| 폴더 | 저장소 | 커밋 (가져온 날 2026-10-06) | 이 프로젝트에서 쓰는 방식 |
|---|---|---|---|
| `consulting-pptx-skill/` | github.com/carnot-tech/consulting-pptx-skill (gozen3ji/consulting-pptx-skill에서 연결됨) | `d75bffa05b24a5f8ede2cb2dfce094e008b96ebc` | HTML을 편집 가능한 PPTX로 바꾸는 변환기의 원본 (`scripts/html_dump.mjs`, `html_to_pptx.py`, `lib_cdp.mjs` → `engine/`으로 복사해 수정). 슬라이드 규칙과 검토 지시문을 한국어로 옮겨 `harness/`에 반영. 62종 부품의 구조를 가져와 `design/parts.html`의 p26~p47로 다시 짬 |
| `mckinsey-pptx/` | github.com/seulee26/mckinsey-pptx | `201ef491d175d880bce2693f5a477ec23ccb57cf` | 40종 템플릿 목록(`mckinsey_pptx/agent/CATALOG.md`)에서 깔때기, 묶음 막대, 버블, 조직도, 인용, 득실 비교의 구성을 가져와 p26~p47에 반영. Python 엔진은 실행하지 않는다 |
| `im-not-ai/` | github.com/epoko77-ai/im-not-ai | `2f3d943d08056b612a92e12bfb72ea94dd2acd18` | 한국어 문체 교정. `skills/humanize-korean`을 `.claude/skills/humanize-korean`에 심볼릭 링크로 연결해 `/humanize-korean` 스킬로 쓰고, `quick-rules.md`와 `scripts/verify_gates.py`를 덱의 문체 교정 단계에서 쓴다 |

## mckinsey-pptx의 엔진을 쓰지 않는 이유

PPTX를 만드는 방식으로 HTML 우선 방식을 골랐기 때문이다. HTML 하나를 원본으로 두면 PPTX와 Figma를 같은 원본에서 만들 수 있다. mckinsey-pptx는 python-pptx로 슬라이드를 직접 그리는 방식이어서 Figma로 보낼 원본이 따로 필요하다.

## 새 버전으로 바꿀 때

1. 폴더를 지우고 새 버전을 복제한 뒤 `.git` 폴더를 지운다. 위 표의 커밋과 날짜를 고친다.
2. `consulting-pptx-skill`의 변환기가 바뀌었으면 `engine/`의 사본과 비교해서 필요한 변경만 옮긴다. `engine/html_dump.mjs`와 `engine/html_to_pptx.py`의 머리말에 이 프로젝트에서 고친 내용이 적혀 있다.
3. `.venv/bin/python scripts/build.py decks/_sample/deck.html`이 FAIL 없이 끝나는지 확인한다.
