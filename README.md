# 쿠키런: 크럼블 자동화

블루스택에서 도는 게임을 ADB 로 조작한다. 화면은 드래그로 지정한 영역을 캡처해서 읽고,
실제 마우스 커서는 건드리지 않으므로 자동화가 도는 동안에도 PC 를 그대로 쓸 수 있다.

지금 되는 것 — 퀘스트창을 읽어 **보상 수령**과 **퀘스트 수행**을 반복한다.
등록된 퀘스트는 오븐 장비 뽑기 · 가방 상자 사용 · 쿠키 뽑기 · 펫 뽑기 네 가지이고,
새 퀘스트는 파일 하나로 추가한다.

---

## 1. 설치

파이썬 3.10 이상이 필요하다. 시스템 파이썬을 더럽히지 않도록 **가상환경(venv) 안에**
설치한다. 저장소를 받고, 가상환경을 만들고, 켠 다음 설치한다.

```bash
git clone https://github.com/ChoSeoHwan/ccc-auto.git && cd ccc-auto
python -m venv .venv
```

가상환경을 켜는 명령만 셸마다 다르다.

| 셸 | 켜기 |
| --- | --- |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows cmd | `.venv\Scripts\activate.bat` |
| macOS / Linux (bash·zsh) | `source .venv/bin/activate` |

켜지면 프롬프트 앞에 `(.venv)` 가 붙는다. 그 상태에서 설치한다.

```bash
pip install -e .
```

별도로 설치할 프로그램은 없다 — `adb` 는 블루스택이 번들로 갖고 있는 것을 자동으로 찾아
쓴다. Windows / macOS 모두 같다.

`.venv/` 는 git 에서 제외돼 있다. 지우고 위 과정을 다시 밟으면 처음 상태로 돌아간다.

> PowerShell 에서 `Activate.ps1` 이 실행 정책 때문에 막히면 그 창에서 한 번만
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` 를 실행하고 다시 켠다.

> Linux 데스크톱에서 GUI 를 쓰려면 `tkinter` 가 필요하다: `sudo apt install python3-tk`.
> 블루스택 자체가 Windows / macOS 전용이라 보통은 해당 없다.

## 2. 블루스택 준비

**ADB 를 켠다.** 블루스택 설정 > 고급 에서 ADB 연결을 켠다. 기본 주소는 `127.0.0.1:5555`.

**그래픽 엔진을 OpenGL 로 둔다.** Vulkan 이면 게임이 몇 분마다 죽는다. 실제로 겪었고
크래시 스택이 `libvulkan_enc.so` 에서 났다. 설정 > 성능 > 그래픽 엔진에서 바꾼다.

## 3. 실행

**가상환경을 켠 상태에서** 실행한다. 새 터미널을 열 때마다 한 번씩 켜 줘야 한다
(위 표의 켜기 명령).

```bash
ccc
```

창이 뜨면 자동으로 ADB 에 연결한다. `python main.py` 도 같다.

> `ccc: command not found` / `'ccc' 용어가 인식되지 않습니다` 가 나오면 가상환경이 꺼져
> 있는 것이다. 켜기 명령을 다시 실행한다.

| 명령 | 하는 일 |
| --- | --- |
| `ccc` | 컨트롤 창 |
| `ccc --check` | 연결 · 캡처 · 인식 · 템플릿 준비 상태를 찍고 종료 |
| `ccc --shot` | 지금 화면을 저장하고 기본 뷰어로 연다 |

## 4. 처음 한 번 — 두 가지 설정

### 화면 영역 잡기

설정 탭의 **영역 재감지** 로 블루스택의 게임 화면만 드래그로 감싼다.

안 잡아도 `adb 캡처` 로 동작하지만 **90배 느리다** (한 장에 579ms 대 6.5ms).
자동화가 판단할 때마다 캡처가 필요해서 이 차이가 그대로 반응 속도가 된다.
창 크기를 바꿨으면 다시 누른다.

> macOS 는 시스템 설정 > 개인정보 보호 및 보안 > **화면 기록** 에서 실행 중인 앱
> (터미널 / PyCharm)에 권한을 준 뒤 그 앱을 재시작해야 화면 캡처가 된다.
> 권한 주기가 번거로우면 `adb 캡처` 로 둬도 기능은 같다.

### 템플릿 뜨기

설정 탭의 **템플릿 설정** 을 누르면 필요한 조각 목록이 나온다. 각 항목마다 "어느 화면에서
무엇을 잘라야 하는지" 안내가 붙어 있으니 따라가면 된다. 5분쯤 걸린다.

게임 화면 이미지는 저작물이라 저장소에 넣지 않았다. 각자 자기 화면에서 뜨는 편이
정확하기도 하다 — 해상도 · 언어 · 보유 아이템이 사람마다 다르다.
뜬 파일은 전부 `local/` 아래에 쌓이고 git 에서 제외된다.

## 5. 돌리기

실행 탭에서 **시작**. 처음이라면 설정 탭의 **안전 모드** 를 켜고 돌려 보자 —
인식만 하고 실제 탭은 보내지 않아서 판단이 맞는지 로그로만 확인할 수 있다.

| 버튼 | 하는 일 |
| --- | --- |
| 시작 / 정지 | 캡처 루프 자체를 켜고 끈다 |
| 대기로 전환 | 루프는 그대로 두고 퀘스트 자동화만 멈춘다 |
| 퀘스트 재개 | 대기에서 다시 시작한다 |

오른쪽 로그 패널에 최근 100줄이 남는다.

---

## 퀘스트 자동화가 어떻게 도는가

```
대기 ─(시작)→ 퀘스트확인 ─┬─ 황금 ─→ 퀘스트완료 ─(보상 수령)─┐
                          │                                   │
                          └─ 회색 ─→ 퀘스트진행               │
                                      판별 → 수행 → 완료확인  │
                                                              │
                          ←───────────────────────────────────┘
```

- **대기** — 아무것도 하지 않는다. 판단이 막히는 상황에서도 알림을 보내고 여기로 돌아온다.
- **퀘스트확인** — 하단 중앙의 빨간 X 가 있으면 눌러 전투화면까지 돌아온 뒤,
  퀘스트창 색으로 완료(황금)/진행중(회색)을 가른다.
- **퀘스트진행** — `판별` → `수행` → `완료확인`. 같은 퀘스트에서 3번 연속 막히면 알림 후 대기.
  기다리면 풀릴 실패(`StepResult.retry`)는 10번까지 봐 주고, 멈추는 대신 퀘스트확인으로 돌아간다.
- **퀘스트완료** — 퀘스트창을 눌러 보상을 받고 다시 확인 단계로 간다.

### 무엇을 보고 판단하는가

| 판단 | 방법 | 실측 |
| --- | --- | --- |
| 지금이 전투화면인가 | 하단 중앙 X 버튼 자리의 빨강 비율 | 전투화면 0.0% / 팝업 84.2% |
| 퀘스트 완료 여부 | 퀘스트창 본체의 황금 · 회색 픽셀 비율 비교 | 완료 금 94%·회 0% / 진행중 금 0%·회 48% |
| 퀘스트창이 화면에 있는가 | 그 영역의 흰 글씨 비율 | 있음 0.035~0.080 / 없음 0.000~0.014 |
| 어떤 퀘스트인가 | 이름을 이진화해 템플릿 매칭, 최고점 하나를 고름 | 정답 0.81~1.00 / 오답 0.00~0.47 |

색을 고정 임계값으로 자르지 않고 **두 색군의 비율을 견줘 우세한 쪽**을 고른다. 어느 쪽도
뚜렷하지 않으면 판정을 미루고 다음 프레임에서 다시 본다.

퀘스트 이름은 흰 글씨만 남기고 이진화해서 비교하므로 창이 황금이든 회색이든 같은 템플릿이
걸린다. 판별은 임계값을 넘는 첫 후보를 채택하지 않는다 — "쿠키 뽑기 10회 하기" 와
"펫 뽑기 10회 하기" 처럼 뒷부분이 같은 이름끼리 서로를 가로채기 때문이다(실측 오탐 0.82).
모든 퀘스트에 점수를 매겨 1등을 고르고 **2등과 0.08 이상 벌어졌을 때만** 확정한다.

판별이 완벽할 수는 없다. 등록되지 않은 퀘스트가 기존 것과 이름이 비슷하면 오판할 수 있다.
그래서 진짜 안전장치는 **실행 단계**에 있다 — 잘못 판별해도 그 퀘스트의 버튼을 찾지 못해
3번 연속 실패하고, 알림을 보낸 뒤 대기로 멈춘다. 재화는 소모되지 않는다.

### 막히는 상황들

**퀘스트창이 가려질 때.** 레벨업 연출처럼 X 버튼 없이 "화면을 탭하세요" 로 넘기는 전체화면
연출은, X 가 없으니 전투화면으로 인식되면서도 퀘스트창은 계속 가려진다. 판독 실패가 4회
쌓일 때마다 `빈 곳 탭 지점`(전장 한복판이라 버튼이 없다)을 한 번 눌러 넘긴다.
20회까지 눌러도 못 읽으면 알림 후 대기.

**모르는 퀘스트가 나올 때.** 바로 멈추지 않고 2초 뒤 다시 확인한다. 퀘스트창을 잠깐 잘못
읽었거나 마침 퀘스트가 바뀌는 중일 수 있다. **1분간 계속** 못 알아보면 그때 알림 후 대기하고,
그 화면을 `local/captures/` 에 저장한다.

**절전 모드.** 게임은 한동안 입력이 없으면 스스로 절전 모드로 넘어간다. 이 화면에는
하단 네비게이션도 X 버튼도 없어서 다른 판단이 전부 오염된다. 별도 모듈이 가장 먼저 감지해
뒤로가기로 빠져나온다.

### 시간을 어떻게 쓰는가

**고정 대기가 없다.** 모든 대기는 "0.1초 뒤 첫 확인 → 아직이면 0.3초 간격 재확인 → 조건이
서면 즉시 진행" 이다. 코드의 숫자들은 소모하는 시간이 아니라 **상한**이다.

```python
ctx.wait_until(조건, 상한)          # 조건이 서면 즉시 반환
ctx.wait_for_template(이름, 상한)    # 버튼이 나타나면 즉시 그걸 반환
```

남은 지연은 캡처 비용이다. adb 캡처는 한 장에 0.58초라 폴링 간격을 아무리 줄여도 그보다
자주 볼 수 없다. 화면 캡처(6.5ms)로 바꾸면 간격이 그대로 반응 속도가 된다.

---

## 퀘스트 추가하기

`ccc/quests/` 에 파일을 하나 만들면 퀘스트가 하나 등록된다. 지우면 사라진다.

```python
from ccc.context import Context
from ccc.geometry import NormRect
from ccc.quest.definition import QuestDefinition, StepResult
from ccc.templates_spec import NUMBER_TIP, SIZE_TIP, TemplateSpec


class 출석보상(QuestDefinition):
    name = "출석 보상 받기"
    name_templates = ["quest_daily"]

    template_group = "퀘스트 - 출석 보상"   # 템플릿 설정에서 묶일 이름
    setup_order = 50                        # 목록에서의 순서 (작을수록 위)
    template_specs = [
        TemplateSpec(
            name="quest_daily",
            label="퀘스트 창",
            where="전투화면에 이 퀘스트가 회색으로 떠 있을 때",
            what="퀘스트 이름 글자 줄",
            tips=(NUMBER_TIP, SIZE_TIP),          # 한 줄에 하나씩 표시된다
            default_area=NormRect(0.76, 0.54, 0.20, 0.018),
        ),
    ]

    def execute(self, ctx: Context) -> StepResult:
        ctx.tap_rect(ctx.anchors.get("quest_panel"))
        button = ctx.wait_for_template("daily_claim", 5.0)
        if button is None:
            return StepResult.blocked("수령 버튼을 찾지 못했습니다")
        ctx.tap_match(button)
        return StepResult.ok()
```

- `execute` 는 절차를 마치면 `StepResult.ok()`, 막히면 `StepResult.blocked(사유)`.
  전투화면 복귀는 상태기가 알아서 하므로 여기서 되돌아올 필요가 없다.
- 기다리면 풀릴 실패(연출이 가렸다, 버튼이 아직 안 나왔다)는 `StepResult.retry(사유)` 를 쓴다.
  `blocked` 와 달리 사람을 부르지 않고 10번까지 봐 준 뒤 퀘스트확인으로 돌아간다.
- `template_specs` 를 적으면 캡처 마법사가 사용자를 안내한다. 안 적으면 목록에 안 나온다.
- `default_area` 를 적어 두면 마법사가 그 자리를 미리 잡아 준다. 사용자는 맞는지 보고
  그대로 저장하거나 조금만 끌어 고치면 된다. `python tools/dev.py crop` 으로 값을 잡는다.
- 템플릿 설정 목록은 `template_group` 으로 묶이고 `setup_order` 로 정렬된다. 모듈이 먼저,
  그 다음 퀘스트다. `label` 은 묶음 안에서만 구별되면 되므로 짧게 적는다.
- 만든 뒤 `python tools/dev.py identify` 로 **다른 퀘스트와 점수 차이가 0.08 이상 나는지**
  확인한다. 이름이 비슷한 퀘스트가 있으면 여기서 드러난다.

## 자동화 모듈 추가하기

퀘스트와 무관하게 항상 감시할 것은 `ccc/modules/` 에 넣는다 (절전 모드 해제, 게임 유지 등).

```python
from ccc.context import Context
from ccc.modules.base import AutomationModule


class 팝업닫기(AutomationModule):
    name = "팝업 닫기"
    interval = 1.0      # 최소 재시도 간격(초)
    priority = 20       # 작을수록 먼저 검사
    exclusive = True    # 동작했으면 이 tick 에서 뒤 모듈은 건너뛴다

    def check(self, ctx: Context) -> bool:
        return ctx.exists("popup_close")

    def run(self, ctx: Context) -> None:
        ctx.tap_template("popup_close")
```

### 좌표 규칙

모듈과 퀘스트는 **항상 0.0~1.0 정규화 좌표**만 쓴다. 컨텍스트가 이를 디바이스 픽셀로 바꿔
ADB 로 내보내므로, 창 크기나 해상도가 바뀌어도 코드는 고칠 필요가 없다. 템플릿도 저장 당시의
화면 대비 크기를 함께 기록해 두었다가 매칭할 때 현재 크기에 맞춰 다시 스케일한다.

### 컨텍스트 API

| 호출 | 설명 |
| --- | --- |
| `ctx.tap(nx, ny)` / `tap_rect` / `tap_match` | 정규화 좌표를 누른다 |
| `ctx.swipe(...)` / `long_press` / `back` | 드래그 · 길게 누르기 · 뒤로 가기 |
| `ctx.find(이름, 임계값, 범위)` | 템플릿 찾기 → `Match` 또는 `None` |
| `ctx.find_text(이름, ...)` | 흰 글씨를 이진화해서 찾기 (배경색 변화에 강함) |
| `ctx.exists` / `tap_template` | 있는지 확인 / 찾으면 누르기 |
| `ctx.wait_until(조건, 상한)` | 조건이 설 때까지 화면을 다시 보며 대기 |
| `ctx.wait_for_template(이름, 상한)` | 버튼이 나타날 때까지 대기했다가 반환 |
| `ctx.refresh()` | 지금 화면을 다시 캡처 |
| `ctx.sleep(초)` | 정지 요청이 오면 즉시 깨는 대기 |
| `ctx.log(메시지)` | 컨트롤 창 로그에 남기기 |
| `ctx.anchors.get(이름)` | 게임 UI 요소의 정규화 영역 |
| `ctx.option(키, 기본값)` | `config.json` 의 모듈별 설정값 |

---

## 개발 도구

작업하면서 반복하는 일은 `tools/dev.py` 에 모여 있다. 셸 힙독이나 파이프 없이 단순한 명령
하나로 끝난다. 여기도 가상환경을 켠 상태에서 실행한다.

```bash
python tools/dev.py diag                        # 연결 · 캡처 · 인식 상태
python tools/dev.py goto-battle                 # 팝업 · 절전 모드를 치우고 전투화면까지
python tools/dev.py shot --anchors              # 화면 저장 (앵커 겹쳐 그리기)
python tools/dev.py crop 0.55 0.5 0.45 0.11     # 영역만 잘라 저장 (정규화 좌표)
python tools/dev.py lines                       # 퀘스트창 안의 글자 줄 좌표
python tools/dev.py locate orange --area ...    # 색으로 버튼 위치 찾기 (눈대중 대신)
python tools/dev.py template list / save / test # 템플릿 목록 · 저장 · 배율별 점수
python tools/dev.py identify                    # 퀘스트 판별 점수를 늘어놓기
python tools/dev.py tap --anchor quest_panel    # 앵커나 좌표를 한 번 누르기
python tools/dev.py run --seconds 60            # 자동화를 잠깐 돌려 보기
python tools/dev.py bench                       # 구간별 소요 시간
```

`--from 파일.png` 을 붙이면 지금 화면 대신 저장해 둔 이미지로 검사한다.
`identify --exclude "펫 뽑기"` 는 그 퀘스트가 아직 등록되지 않은 상황을 재현한다.

`template test` 는 100% · 75% · 50% 로 줄여 가며 점수를 보여 준다. **실제 운영 해상도가
원본의 절반쯤**(블루스택 창 520x940 ≈ 1080x1920 의 48%)이라, 새 템플릿을 뜰 때는 50% 점수가
임계값(글자 0.75 / 그림 0.80)을 넘는지 반드시 확인한다. 넘지 못하면 템플릿이 너무 작은
것이므로 더 넓게 다시 잡는다.

## 테스트

가상환경을 켠 뒤 개발용 의존성까지 넣는다.

```bash
pip install -e ".[dev]"
pytest
```

한국어 Gherkin 으로 쓴 BDD 시나리오 36개다. `tests/features/*.feature` 를 읽으면 퀘스트가
무엇을 어떤 순서로 하는지 코드를 보지 않고도 확인할 수 있다.

테스트용 게임 화면(`local/fixtures/frames/`)이 없으면 전부 건너뛴다. 저장소를 갓 받은
사람도 빨간불 없이 돈다.

## 잘 안 될 때

컨트롤 창 설정 탭의 **인식 진단** 을 누르면 지금 화면을 어떻게 읽고 있는지 숫자로 나온다.
값이 이상하면 **영역 보정** 에서 퀘스트창 · 색 표본 · 닫기 버튼 · 빈 곳 탭 지점을 다시 잡는다.

## 구조

화면(UI)과 실행 로직을 갈라 두었다. `ccc/ui/` 는 tkinter 만 알고 판단을 하지 않으며,
`ccc/app.py` 아래로는 tkinter 를 전혀 모른다. 그래서 GUI 없이도 `--check` 나 스크립트로
같은 로직을 그대로 돌릴 수 있다.

```
main.py                  실행 진입점
ccc/
  app.py                 ★ 서비스 계층 — UI 와 실행 로직의 경계
  config.py              설정 저장/로드, 경로 정의
  anchors.py             게임 UI 요소의 정규화 좌표
  geometry.py            Rect / NormRect
  templates_spec.py      캡처 마법사가 읽는 템플릿 선언
  notify.py              OS 알림
  selector.py            드래그 영역 선택 오버레이
  context.py             모듈에 넘어가는 실행 컨텍스트 (좌표 변환 · 대기)
  engine.py              캡처 → 판단 → 실행 루프
  adb/                   adb 자동 탐색 + 클라이언트
  capture/               화면 캡처 / adb 캡처 백엔드
  vision/                템플릿 매칭, 색 판정, 글자 이진화 매칭
  quest/                 퀘스트 상태기 · 퀘스트창 판독 · 화면 복귀
  quests/                ★ 퀘스트 지시문 (파일 추가/삭제)
  modules/               ★ 자동화 모듈 (파일 추가/삭제)
  ui/                    컨트롤 창과 대화상자 (표시 전용)
tools/dev.py             개발용 명령 모음
tests/                   BDD 시나리오와 스텝 정의
local/                   이 컴퓨터에서만 쓰는 것 (git 제외)
  templates/             캡처한 템플릿
  fixtures/frames/       테스트용 화면
  captures/              진단 이미지
```

코드를 고칠 때 알아야 할 규칙과 배경은 [AGENT.md](AGENT.md) 에 정리해 두었다.
