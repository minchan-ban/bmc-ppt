# 글꼴: Pretendard의 굵기 구분

글꼴은 Pretendard 하나만 쓴다. 크기를 여러 단계로 나누지 않고 굵기로 위계를 만든다.
굵기는 `design/deck.css`의 토큰으로 지정하고, 부품의 클래스가 이미 알맞은 굵기를 갖고 있다. 인라인으로 굵기를 지정하지 않는다.

| 토큰 | 굵기 | PowerPoint의 글꼴 이름 | 쓰는 자리 |
|---|---|---|---|
| `--w-body` | 400 Regular | Pretendard | 본문, 표의 칸, 글머리표, 출처 |
| `--w-label` | 500 Medium | Pretendard Medium | 키커, 수치의 라벨, 축의 단위, 장 번호, 단계 위의 주체 이름 |
| `--w-head` | 600 SemiBold | Pretendard SemiBold | 헤드메시지, 열 제목, 축 제목, 표의 머리글과 행 축, 본문 안의 강조(`<b>`), 도표의 값 |
| `--w-cover` | 700 Bold | Pretendard (굵게) | 표지 제목, 장 구분 제목, 뒤표지의 회사 이름 |
| `--w-num` | 800 ExtraBold | Pretendard ExtraBold | 핵심 수치(`.kpi .v`, `.calc .v`, `.side .sn`, `td.big`) |

## 지키는 것

- **한 장에 굵기는 세 가지까지.** 본문(400), 제목과 강조(600), 그리고 필요할 때 수치(800)나 라벨(500) 하나.
- **헤드메시지는 600이다.** 700 이상으로 올리지 않는다. 헤드메시지가 너무 굵으면 그 아래의 수치가 묻힌다.
- **800은 수치에만 쓴다.** 문장에 쓰지 않는다.
- **본문 안의 강조는 `<b>`로 한 장에 한두 군데.** 색으로 강조하지 않고 굵기로 강조한다. 밑줄과 기울임을 쓰지 않는다.
- **300 Light는 쓰지 않는다.** 작은 글자에서 인쇄와 투사 때 흐려진다.

## 크기 (1280×720 기준, 괄호 안은 PowerPoint에서의 pt)

| 자리 | 크기 | 줄 높이 |
|---|---|---|
| 헤드메시지 | 27px (20.25pt) | 36px |
| 열 제목, 축 제목, 표의 머리글 | 16px (12pt) | 21px |
| 본문 글머리표, 표의 칸 | 15~16px (11.25~12pt) | 23~26px |
| 핵심 수치 | 50~52px (37.5~39pt) | 60~62px |
| 출처, 꼬리말 | 10~10.5px (7.5~8pt) | 14px |
| 표지 제목 | 46px (34.5pt) | 60px |

## PPTX와 Figma에서

- PPTX: 굵기마다 글꼴 이름이 따로 지정된다 (`engine/html_to_pptx.py`의 `WEIGHT_FACE`). PowerPoint의 글꼴 목록에서 `Pretendard SemiBold`처럼 굵기 이름으로 고를 수 있다. 테마 글꼴도 Pretendard라서 새로 만든 글상자도 Pretendard로 시작한다.
- 덱을 받는 사람의 컴퓨터에 Pretendard가 없으면 다른 글꼴로 바뀌어 보인다. 밖으로 보낼 때는 PDF를 함께 보내거나, PowerPoint의 "파일에 글꼴 포함" 옵션으로 저장한다.
- Figma: Figma 데스크톱 앱이 이 컴퓨터에 설치된 Pretendard를 쓴다. 브라우저의 Figma에서는 Pretendard가 보이지 않을 수 있다.
- 글꼴 파일은 `design/fonts/`에 있고 `scripts/setup.sh`가 빠진 굵기를 설치한다 (SIL Open Font License).
