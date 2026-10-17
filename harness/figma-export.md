# Figma로 보내기

`scripts/build.py`가 만든 `out/figma/deck_figma_NN.html`을 Figma MCP의 `html_to_figma`로 보내 Figma Design 파일의 프레임으로 만든다.
사용자의 Figma 계정에 파일을 만들고 덱의 내용을 Figma 서버로 올리는 일이므로, 실행 전에 사용자의 확인을 받는다.

2026-10-06에 시험 덱 6장과 컨설팅 도형 22종(p26~p47)으로 확인한 결과: 도형 22종은 전부 프레임과 텍스트로만 들어왔고(그림으로 바뀐 것 없음), 글자는 모두 Pretendard였다. 화면 대조는 호출 한도 때문에 폭포와 누적 세로 막대 2종만 했고 둘 다 원본과 같았다. 나머지 20종의 화면 대조는 하지 못했다.

2026-10-17에 더한 데이터 도표 10종(p48~p57)은 PPTX 변환(그림으로 바뀐 요소 없음)과 화면 검사만 확인했고, Figma로는 아직 보내 보지 않았다. 처음 보낼 때 이 10종의 화면을 원본과 대조한다.

기본 차트 부품(p58~p61)은 `build.py`가 Chrome으로 그린 SVG를 Figma용 HTML에 고정해 넣는다(`engine/freeze_charts.mjs`). Figma에서는 벡터 도형과 글자로 들어오고, PowerPoint처럼 데이터를 편집하는 기능은 없다. 이 4종도 아직 Figma로 보내 보지 않았다.

시험 덱 6장의 결과: 슬라이드마다 1280×720 프레임 하나가 만들어졌고, 안쪽 프레임 대부분이 오토 레이아웃으로 변환되었으며(본문 슬라이드 4장의 프레임 156개 중 149개), 글자는 Pretendard의 굵기별 스타일(Regular, Medium, Semi Bold, Bold, Extra Bold)이 지정된 편집 가능한 텍스트로 들어왔다.

## 절차

1. **빌드**: `.venv/bin/python scripts/build.py decks/<이름>/deck.html`이 FAIL 없이 끝나 있어야 한다. `out/figma/`에 20장 단위로 나뉜 HTML이 있다 (글꼴이 파일 안에 들어 있어서 한 파일이 6MB쯤 된다).
2. **파일 정하기**:
   - 사용자가 Figma 파일 링크를 주면 그 파일에 새 페이지로 올린다 (`fileKey`는 링크의 `/design/` 다음 부분).
   - 새 파일이면 `skill://figma/figma-create-new-file/SKILL.md`를 읽은 뒤 `whoami`로 팀 목록을 받는다. 팀이 둘 이상이면 사용자에게 고르게 하고(보기 권한뿐인 팀은 제외), `create_new_file`을 `editorType: "design"`으로 부른다.
3. **보내기**: HTML 파일마다 `html_to_figma`를 `cssSelector: "section.slide"`로 불러 한 번만 쓸 수 있는 주소를 받고, 그 주소로 파일을 보낸다.
   ```bash
   curl -s -X POST "<submitUrl>" -H "Content-Type: text/html" --data-binary @decks/<이름>/out/figma/deck_figma_01.html --max-time 240
   ```
   응답의 `nodeIds`가 슬라이드 수와 같은지 확인한다. 파일이 여러 개면 파일마다 `html_to_figma`를 다시 불러 새 주소를 받고 순서대로 보낸다. 같은 `fileKey`로 보내면 프레임이 같은 페이지에 쌓인다.
4. **정리**: `skill://figma/figma-use/SKILL.md`를 읽은 뒤 `use_figma`의 `code`에 `engine/figma_post.js`의 내용을 넣어 실행한다. 프레임 이름이 `01 헤드메시지`로 바뀌고 한 줄에 4장씩 놓인다. 슬라이드 안의 내용은 건드리지 않는다.
5. **확인**: 본문 슬라이드 서너 장을 골라 원본 미리보기(`out/preview/`)와 비교한다. 화면은 4단계의 `use_figma` 호출 하나 안에서 `await node.screenshot()`으로 여러 장을 한꺼번에 받는다. `get_screenshot`을 슬라이드마다 부르지 않는다 (아래 "호출 한도" 참조).
6. 사용자에게 파일 링크를 전한다. Figma 데스크톱 앱에서 열어야 이 컴퓨터의 Pretendard로 보인다.

## 호출 한도

Figma MCP에는 요금제별 도구 호출 한도가 있다. Starter 요금제에서는 2026-10-06에 한 세션에서 30회쯤 호출한 뒤 `You've reached the Figma MCP tool call limit`으로 막혔다.

- 덱 한 벌을 보내는 데 드는 호출: 20장마다 `html_to_figma` 1회, 정리와 화면 확인을 합친 `use_figma` 1회, 새 파일이면 `whoami`와 `create_new_file` 각 1회. 40장 덱이 5회쯤이다.
- 슬라이드마다 `get_screenshot`을 부르면 한도를 금방 쓴다. 화면 확인은 `use_figma` 한 번에 모아서 한다.
- 한도에 걸리면 다시 시도하지 않는다. 사용자에게 알리고, 이미 올라간 프레임은 Figma 앱에서 직접 확인하도록 링크를 전한다. 한도가 풀리는 시점은 Figma의 안내(`file://figma/docs/rate-limits-access.md`)를 따른다.

## 알려진 차이 (Figma 쪽 변환의 한계)

| 항목 | Figma에서의 모습 | 대응 |
|---|---|---|
| 단계 화살표(p10)의 화살 모양 | `clip-path`가 재현되지 않아 사각형으로 들어온다 | Figma에서 사각형을 화살표 도형으로 바꾸거나, 화살 모양이 중요하면 PPTX를 쓴다 (PPTX에서는 다각형으로 재현된다) |
| 한글 줄바꿈 | 어절 단위가 아니라 글자 단위로 줄이 바뀌는 곳이 있다 | 눈에 띄는 곳은 Figma에서 글상자 너비를 조금 넓힌다 |
| 색과 글자 스타일 | 일반 레이어로 들어온다. Figma 변수와 텍스트 스타일에 연결되지 않는다 | 디자인 시스템이 필요해지면 `use_figma`로 변수를 만들어 연결하는 단계를 따로 더한다 |
| 표 | 표 개체가 아니라 오토 레이아웃 프레임의 중첩으로 들어온다 | 행을 복제해서 늘릴 수 있다 |

## 지키는 것

- Figma에서 고친 내용은 `deck.html`에 돌아오지 않는다. 내용(문구, 수치)은 `deck.html`에서 고치고 다시 보내고, Figma에서는 배치와 시각 요소를 다듬는 용도로 쓴다.
- 같은 파일에 다시 보내면 프레임이 같은 페이지에 더 쌓이고, 4단계의 정리 스크립트를 돌리기 전에는 기존 프레임과 겹쳐 보일 수 있다. 이전 프레임을 지울지는 사용자에게 묻는다.
- 올리는 HTML에는 덱의 모든 문구가 들어 있다. 대외비 내용이 있는 덱은 올리기 전에 사용자에게 한 번 더 확인한다.
