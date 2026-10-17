---
name: bmc-ppt
description: 회사의 덱(투자자용 사업 소개, B2B 제품 소개서 등)을 컨설팅·PE 스타일로 만들어 편집 가능한 PPTX, PDF, Figma로 내보낸다. 브리프 → 팩트 원장 → 헤드메시지 스토리라인(승인) → 슬라이드 조립 → 문체 교정 → 기계 검사 → 처음 읽는 사람의 검토 → 내보내기 순서로 진행한다. "/bmc-ppt", "덱 만들어줘", "IR 덱", "제품 소개서", "사업 소개 자료", "피피티 만들어줘" 요청에 쓴다. 이미 만든 덱을 고치거나 다시 내보낼 때도 쓴다.
---

# bmc-ppt: 덱 제작 절차

덱 한 벌의 원본은 `decks/<이름>/deck.html` 하나다. PPTX, PDF, Figma는 모두 이 파일에서 만든다.
모든 경로는 프로젝트 루트(이 저장소의 최상위 폴더) 기준이고, Python은 `.venv/bin/python`을 쓴다.
회사명, 브랜드 색, 뒤표지 연락처는 `brand.json`에 있다.

각 단계 끝의 **멈춤**에서는 사용자의 답을 받기 전에 다음 단계로 넘어가지 않는다. 사용자와는 한국어로 소통한다.

## 0. 준비 (세션에서 처음 한 번)

```bash
bash scripts/setup.sh --check
```
빠진 것이 있다고 나오면 `bash scripts/setup.sh`를 실행하기 전에 사용자에게 알린다 (글꼴 설치와 패키지 설치가 일어난다).

`brand.json`의 `company`가 아직 `Your Company`이거나 연락처가 `example.com` 예시값이면, 덱을 만들기 전에 회사명, 브랜드 색, 연락처를 사용자에게 묻고 `brand.json`을 고친다.

이미 있는 덱을 고치는 요청이면 `decks/<이름>/`의 `brief.md`, `storyline.md`, `facts.md`를 읽고 해당 단계로 바로 간다. 본문만 고치면 5단계, 헤드메시지를 고치면 3단계부터 다시 한다.

## 1. 브리프

`decks/<YYYY-MM>-<짧은 이름>/brief.md`를 만든다. 아래 항목 가운데 사용자의 요청에서 알 수 없는 것만 AskUserQuestion으로 묻는다.

- **덱 유형**: `investor`, `sales` (`harness/deck-types.md`를 읽고 정한다)
- **팔레트**: 덱을 새로 만들 때마다 AskUserQuestion으로 네 가지 가운데 고르게 한다. 선택지는 `rose`(A, 차콜 + 로즈 포인트, 기본이므로 첫 번째에 두고 추천으로 표시), `rose-panel`(B, 차콜 글자 + 로즈 면), `berry`(C, 버건디 + 로즈), `navy-rose`(D, 네이비 + 로즈 포인트)다. 묻기 전에 `open design/palettes.png`로 비교 그림을 화면에 띄운다. 사용자가 요청에서 이미 팔레트를 말했으면 묻지 않는다
- **읽는 사람**: 누구이고, 이 덱을 읽고 무엇을 결정하는가
- **쓰는 자리**: 직접 발표하는가, 파일만 보내는가 (파일만 보내는 덱은 본문이 더 자세해야 한다)
- **분량**: 본문 장수
- **이 덱에서 반드시 전해야 하는 것** 한 문장
- **검토 깊이**: 빠르게(기계 검사만), 표준(처음 읽는 사람의 검토 한 바퀴), 꼼꼼하게(사용자가 정한 횟수)

읽는 사람과 목적을 알 수 없으면 덱을 만들지 않는다. 장수를 늘릴수록 틀린 내용이 드러날 자리도 늘어난다.

## 2. 팩트 원장

`decks/<이름>/facts.md`에 이 덱에서 쓸 수 있는 사실과 수치를 표로 모은다 (열: 번호, 사실, 수치, 출처, 확인 상태. 형식은 `decks/_sample/facts.md` 참조).

- 출처는 `context/` 폴더의 자료, 사용자가 준 자료, 사용자가 알려 준 원자료 폴더다. 읽은 파일의 경로를 출처 열에 적는다.
- **원장에 없는 수치는 덱에 쓰지 않는다.** 필요한 수치가 없으면 지어내지 않고 사용자에게 묻는다. 헤드메시지의 수치가 원장에 없으면 검사가 FAIL을 낸다(H10).
- 자료끼리 수치가 다르거나 측정 시점이 불분명하면 확인 상태 열에 적고, 3단계의 멈춤에서 사용자에게 함께 보인다.
- 같은 지표의 값이 자료마다 다르면 어느 자료를 기준으로 삼을지 사용자에게 묻고, 그 답을 원장 머리말에 적는다.

## 3. 헤드메시지 스토리라인 → 멈춤

`harness/headline-rules.md`를 처음부터 끝까지 읽는다. 이 단계가 덱의 품질을 정한다.

1. `harness/deck-types.md`의 표준 구성에서 출발해, 장마다 **헤드메시지 한 줄**을 `decks/<이름>/storyline.md`에 번호 목록으로 쓴다. 표지, 장 구분, 뒤표지는 `[표지]`, `[장 구분]`, `[뒤표지]`로, 라벨 제목을 쓰는 장은 `[라벨]`로 시작한다.
   ```
   1. [표지] 한끼랩 사업 소개
   2. 직장인 1명이 점심 결정에 앱 3곳 비교, 하루 12분, 한 달 4시간 소요
   3. 메뉴 결정과 배달 대기가 점심시간 60분 중 35분 차지
   ```
2. 검사한다. FAIL이 0이 될 때까지 고친다. WARN은 하나씩 읽고 고치거나 남기는 이유를 정한다.
   ```bash
   python3 scripts/check_deck.py decks/<이름>/storyline.md --storyline
   ```
3. 검사기가 출력한 목록을 위에서 아래로 통독한다. 이야기가 끊기거나 같은 말이 되풀이되는 자리를 고친다.
4. 헤드메시지마다 **근거가 되는 원장 번호**와 **권하는 부품**을 붙인 표를 `storyline.md` 아래쪽에 만든다. 부품은 `python3 scripts/new_deck.py --list`와 `design/catalog.md`에서 고른다.

**멈춤**: 헤드메시지 목록, 남긴 WARN과 그 이유, 확인이 필요한 수치를 사용자에게 보이고 승인을 받는다. 헤드메시지가 바뀌면 2~3번을 다시 한다.

## 4. 조립

```bash
python3 scripts/new_deck.py --type <유형> --palette <팔레트> --parts p01,p09,... --title "<덱 제목>" -o decks/<이름>/deck.html
```
맞는 부품이 없으면 가장 가까운 부품을 넣은 뒤 `deck.html`에서 그 장의 본문을 `design/deck.css`의 클래스로 다시 짠다. 새 CSS가 필요하면 `design/deck.css`에 토큰만 써서 더하고 `--refresh-css`로 반영한다.

## 5. 본문 작성

`harness/slide-rules.md`와 `harness/copy-rules.md`를 읽고, `deck.html`의 `{{ }}` 자리표시자를 Edit으로 채운다.

- 회사명과 뒤표지 연락처는 `new_deck.py`가 `brand.json`에서 채운다. 덱마다 다른 연락처를 쓰려면 `deck.html`의 뒤표지를 직접 고친다.
- 헤드메시지는 3단계에서 승인받은 문장을 그대로 넣는다. 40자를 넘으면 의미가 끊기는 자리에 `<br>`을 넣는다.
- 본문에는 헤드메시지를 증명하는 것만 싣는다. 헤드메시지의 수치는 본문에 그대로 있어야 한다(H9).
- 행과 열의 개수는 내용에 맞게 더하거나 뺀다. 견본의 개수에 내용을 맞추지 않는다.
- 막대의 길이와 높이는 `style`의 `width`, `height` 비율을 실제 값의 비율로 계산해서 넣는다. 강조(`on`)는 헤드메시지가 말하는 항목 하나에만 둔다.
- 기본 차트 부품(p58~p61: 도넛, 원형, 꺾은선, 누적 영역)은 비율을 계산하지 않고 `data-chart`의 `categories`, `series`의 `values`에 실제 수치를 넣는다. 강조는 `highlight`에 번호로 적는다. 항목은 `design/nchart.js` 머리말에 있다.
- 수치가 있는 장에는 출처 줄을 채운다. 출처 줄이 필요 없는 장에서는 `.src` 요소를 지운다.
- 제품 화면은 `.shot` 안의 `<span>`을 `<img src="...">`로 바꾼다. 이미지는 덱 폴더의 `assets/`에 둔다.
- **기업 로고가 필요하면** `harness/logo-rules.md`의 절차를 따른다. 회사마다 아래를 실행하고, 미리보기(`assets/logos/_preview/<이름>.png`)를 Read로 직접 본 뒤 맞지 않으면 후보(`--pick`)나 방식(`--mode`)을 바꿔 다시 한다. 세 번 다시 해도 맞는 로고를 얻지 못하면 사용자에게 묻는다.
  ```bash
  .venv/bin/python scripts/logo.py get "<회사 이름>" --site <도메인> --deck decks/<이름>
  ```
  고객사와 제휴사의 로고는 실어도 되는지 사용자가 확인한 회사만 덱에 넣는다.

## 6. 문체 교정

`harness/copy-rules.md`의 "문체 교정 단계의 절차"를 따른다.

```bash
python3 scripts/copy_pass.py extract decks/<이름>/deck.html
# vendor/im-not-ai/skills/humanize-korean/references/quick-rules.md를 읽고 copy/after.txt를 교정
python3 scripts/copy_pass.py apply decks/<이름>/deck.html
```
헤드메시지 줄은 이 단계에서 문형을 바꾸지 않는다.

## 7. 기계 검사와 내보내기

**수정을 주고받는 동안에는 HTML만 고치고 보여 준다.** 사용자가 "pptx 반영", "figma 반영"처럼 내보내기를 말하기 전에는 PPTX 변환과 Figma 업로드를 하지 않는다. 수정할 때마다 내보내면 느리고, 사용자가 확인할 것은 내용과 배치다.

```bash
.venv/bin/python scripts/build.py decks/<이름>/deck.html --html-only   # 수정 단계: 검사 + out/preview/ PNG
.venv/bin/python scripts/build.py decks/<이름>/deck.html --preview     # 사용자가 PPTX 반영을 말했을 때
```
수정 단계에서는 바뀐 장의 `out/preview/p-N.png`를 Read로 확인한 뒤 사용자에게 보여 준다 (`open`으로 띄운다).
내용 검사, 화면 검사, PPTX 변환, PPTX 검사, PDF, Figma용 HTML을 차례로 만든다. FAIL이 있으면 멈추므로 `deck.html`을 고치고 다시 실행한다.

- FAIL을 없애려고 규칙이나 검사기를 고치지 않는다. 검사가 틀렸다고 판단되면 그 근거를 사용자에게 보이고 정한다.
- WARN은 하나씩 읽는다. `L5`(빈 공간)는 내용을 더하거나 부품을 바꿔서 풀고, 장식으로 채우지 않는다.
- 사용자에게 넘기기 전 마지막 빌드에는 `--pptx-preview`를 붙여 PowerPoint가 실제로 그린 모습(`out/preview_pptx/`)도 확인한다. PowerPoint 창이 잠깐 열렸다 닫히므로 사용자에게 미리 알린다.
- `out/preview/`의 PNG를 Read로 모든 쪽을 직접 본다. 기계 검사는 넘침과 규칙 위반만 잡는다. 균형, 어색한 줄바꿈, 좌우 아래 끝의 어긋남, `harness/slide-rules.md` 첫머리의 다섯 가지는 눈으로만 알 수 있다.

## 8. 처음 읽는 사람의 검토 → 멈춤

브리프의 검토 깊이가 "빠르게"가 아니면 `harness/review-prompt.md`의 절차대로 새 에이전트(Agent 도구, `general-purpose`)에게 `out/<이름>.pdf`를 읽힌다. 덱을 만든 과정은 알리지 않는다.
지적을 채택 표로 만들고, 채택한 것을 고친 뒤 7단계를 다시 실행한다.

**멈춤**: 결과물의 경로, 채택 표, 남은 WARN, 확인이 필요한 수치를 사용자에게 보인다. 한 바퀴를 더 돌릴지는 사용자가 정한다.

## 9. 열기

사용자가 열어 달라고 하면:

- **PowerPoint**: `.venv/bin/python scripts/build.py decks/<이름>/deck.html --open`
- **Figma**: `harness/figma-export.md`의 절차를 따른다. 사용자의 Figma 계정에 파일을 만드는 일이므로 실행 전에 확인을 받는다.

## 끝낼 때 보고할 것

- 만든 파일의 경로 (PPTX, PDF, Figma 링크)
- 검사 결과: FAIL 0인지, 남긴 WARN과 그 이유
- 확인 상태가 "확인 필요"인 수치의 목록
- PPTX나 Figma에서 직접 고친 내용은 `deck.html`에 반영되지 않는다는 점. 내용을 다시 고칠 일이 있으면 `deck.html`을 고치고 다시 내보내는 쪽이 안전하다

## 파일 안내

| 파일 | 내용 | 읽는 때 |
|---|---|---|
| `harness/headline-rules.md` | 헤드메시지 규칙 H1~H12 | 3단계 전에 반드시 |
| `harness/deck-types.md` | 덱 유형별 읽는 사람, 표준 구성, 어조. 팔레트 네 가지 | 1단계와 3단계 |
| `design/palettes.png` | 팔레트 네 가지를 나란히 놓은 비교 그림 | 1단계에서 팔레트를 물을 때 |
| `harness/slide-rules.md` | 구성, 표, 도표, 색 규칙 | 5단계 전에 반드시 |
| `harness/copy-rules.md` | 문체 규칙 C1~C12, 문체 교정 절차 | 5단계와 6단계 |
| `harness/review-prompt.md` | 처음 읽는 사람의 검토 지시문 | 8단계 |
| `harness/figma-export.md` | Figma로 보내는 절차 | 9단계 |
| `harness/logo-rules.md` | 기업 로고를 투명 PNG로 만드는 절차와 덱에 넣는 규칙 | 로고가 필요할 때 |
| `harness/lexicon.json` | 검사기가 쓰는 어휘 목록 | 지적받은 표현을 추가할 때 |
| `design/catalog.md` | 전하려는 내용에 맞는 부품 고르기 | 3단계 |
| `design/typography.md` | Pretendard 굵기 구분 | 부품을 고치거나 새로 짤 때 |
| `design/deck.css`, `design/parts.html` | 디자인 토큰과 부품 61종 | 부품을 고치거나 새로 짤 때 |
