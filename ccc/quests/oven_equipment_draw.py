"""퀘스트: 오븐에서 장비 뽑기.

    퀘스트 1315 · 오븐에서 장비 뽑기 15번 · 0/15

이름 템플릿은 '오븐에서 장비 뽑기' 첫 줄만 잡아 두었다. 횟수(15번)는 다음
줄에 따로 있어서 10번이든 20번이든 같은 퀘스트로 걸린다.

수행 절차 (실측으로 확인한 순서)
    1. 오븐 왼쪽 아래의 Auto 버튼을 누른다.       → '자동 열기' 팝업이 뜬다
    2. 팝업 아래쪽의 주황 버튼을 누른다.          → 팝업이 스스로 닫히고 뽑기 시작
    3. 뽑힌 장비 비교 팝업을 빈 곳 탭으로 닫는다. → 이 팝업에는 X 버튼이 없다

3단계 팝업은 '장착 / 판매' 버튼을 갖고 있지만 어느 쪽도 누르지 않는다.
빈 곳을 누르면 아무 선택 없이 닫히고 장비는 가방에 남는다.

**2단계를 글자로 읽지 않는 이유.** 그 자리에 뜨는 버튼은 보통 '시작' 이지만,
장비가 30개(최대)로 차 있으면 대신 '정리하기' 가 뜬다. 어느 쪽이든 눌러야 할
버튼은 그 하나뿐이라 글자를 가릴 이유가 없다. 그래서 템플릿 대신 **주황색**
으로 찾는다. 버튼 위로 흘러가는 띠에도 색은 흔들리지 않는다.

**장비가 가득 찼을 때.** '정리하기' → 자동 열기 결과 목록의 '정리 하기' →
확인창의 '정리하기' 순으로 주황 버튼이 이어진다. 셋 다 같은 자리·같은 색이라
같은 방법으로 눌러 나가면 정리가 끝나고 다시 뽑을 수 있게 된다.

**재료가 모자랄 때.** 행운반죽이 없으면 '시작' 을 눌러도 뽑기가 돌지 않고
'아이템이 부족합니다' 안내가 뜬다. 이 팝업에는 X 가 있어서 빈 곳 탭으로는
닫히지 않는다. 3단계에서 X 가 보이면 두드리기를 멈추고 진행 불가로 알린다.

**오븐을 올릴 수 있을 때.** '시작' 을 누르면 가끔 "오븐을 레벨업 할 수 있습니다"
확인창이 뜬다. 이때는 레벨업 → 오븐 성장 순으로 누르고 퀘스트확인부터 다시 밟는다.
뽑기는 이번 판에 돌지 않지만, 오븐이 올라가면 같은 창이 다시 뜨지 않는다.

**Auto 버튼이 안 보이는 경우.** 이미 돌고 있으면 버튼이 노란색으로 바뀌고, 장비
자동 분해 팝업까지 겹쳐서 그 상태를 알아보기가 어렵다. 그래서 켜진 버튼을 따로
알아보려 하지 않는다. 청록색 버튼이 다시 보일 때까지 기다리기만 하고, 30초 안에
안 보이면 퀘스트확인부터 다시 본다. 기다리는 동안에도 퀘스트 완료와 정리하기
팝업을 함께 본다 — 팝업이 오븐과 퀘스트창을 같이 가리면 둘 다 영영 안 보여서,
치울 수 있는 화면을 앞에 두고 30초를 통째로 버리기 때문이다.
"""

from __future__ import annotations

import logging

from .. import anchors as anchor_names
from ..assets import load as load_asset
from ..config import LOCAL_DIR
from ..context import Context
from ..geometry import NormRect
from ..quest.definition import QuestDefinition, StepResult
from ..quest.diagnostics import save_frame
from ..quest.navigator import BattleScreenNavigator
from ..quest.panel import QuestPanelReader, panel_visible
from ..quest.states import PanelState
from ..templates_spec import NUMBER_TIP, SIZE_TIP, TemplateSpec
from ..vision import BUTTON_ORANGE, TemplateError, find, find_color_button

log = logging.getLogger(__name__)

AUTO_TEMPLATE = "oven_auto"
LEVELUP_TEMPLATE = "oven_levelup"

GROW_TEMPLATES = ("oven_grow", "oven_grow_levelup")
"""'오븐 레벨' 화면 아래 한가운데 버튼. 같은 자리에 둘 중 하나가 뜬다.

    성장 게이지 안 참   청록 '오븐 성장'
    성장 게이지 다 참   주황 '레벨업!'

글자도 색도 바뀌므로 하나로는 못 잡는다. 둘 다 찾아보고 잡히는 쪽을 누른다.
어느 쪽이든 눌러야 오븐이 올라가므로 가릴 이유는 없다.
"""

AUTO_SEARCH = NormRect(0.18, 0.82, 0.40, 0.12)
"""Auto 버튼을 찾을 범위. 오븐 왼쪽 아래를 넉넉히 덮는다.

실측 위치는 중심 (0.360, 0.890) 이지만 창 비율이 다르면 조금씩 밀리므로,
고정 좌표로 누르지 않고 이 범위 안에서 찾아서 누른다.
"""

BUTTON_BAND = NormRect(0.20, 0.83, 0.78, 0.10)
"""주황 버튼이 놓이는 띠. 팝업마다 좌우 위치가 달라 가로로 넓게 잡는다.

실측 (506x898 화면)
    시작        x 0.332~0.667
    정리 하기   x 0.378~0.712   (자동 열기 결과 목록)
    정리하기    x 0.512~0.874   (확인창, 왼쪽에 청록 '그만두기')
세로는 셋 다 0.855~0.909 로 같다. 왼쪽 끝 0.20 아래는 전투화면의 주황
잡동사니가 있는 자리라 일부러 뺐다.
"""

AUTO_THRESHOLD = 0.80
GROW_THRESHOLD = 0.80

LEVELUP_THRESHOLD = 0.65
"""레벨업 확인창을 알아볼 임계값.

0.80 은 참값에 너무 붙어 있었다. 실측하면 확인창이 0.848 이고 나머지 화면은
0.24~0.48 이라, 0.80 은 빈 구간의 **꼭대기**다. 창이 뜨는 순간이나 창 크기가
달라 점수가 조금만 흔들려도 놓친다.

놓치면 그냥 못 알아보고 마는 게 아니다. 확인창의 '레벨업' 은 '정리하기' 와
똑같은 주황 버튼이라, 색으로 찾는 쪽이 대신 눌러 버린다. 그러면 오븐 레벨
화면까지는 갔는데 아무도 마무리를 하지 않는다.

빈 구간(0.48~0.85) 한가운데인 0.65 로 내렸다. 아래로 1.36배, 위로 1.3배다.
"""

LEVELUP_SEARCH = NormRect(0.45, 0.80, 0.55, 0.12)
"""'레벨업' 버튼을 찾을 범위.

실측: 확인창의 레벨업 버튼은 게임 좌표 (0.615, 0.865) 에 0.150x0.031 크기로 앉는다.
그 자리를 넉넉히 감싼다. 왼쪽 절반은 일부러 뺐다 — 거기 '그냥 열기' 가 있고,
둘을 한 범위에 넣으면 잘못 걸릴 여지를 만든다.
"""

GROW_SEARCH = NormRect(0.30, 0.82, 0.40, 0.10)
"""'오븐 성장' 버튼을 찾을 범위. 실측 중심 (0.497, 0.866).

'오븐 레벨' 화면은 전용 화면이라 버튼이 아래 한가운데에 고정으로 앉는다.
그 자리를 넉넉히 감싼다. 전체 탐색은 20배 비싸다(166ms 대 6~9ms).
"""

LEVELUP_GROW_TIMEOUT = 5.0
"""'레벨업' 을 누르고 '오븐 성장' 버튼이 뜨기까지 기다릴 상한."""

LEVELUP_SHOT_DIR = LOCAL_DIR / "oven_level_up"
"""레벨업 확인창을 만났을 때의 화면을 모아 두는 곳.

가끔만 뜨는 화면이라 사람이 다시 만들어 내기 어렵다. 지나갈 때마다 세 장
(확인창 / 레벨업 누른 뒤 / 오븐 성장 누른 뒤)을 남겨서, 나중에 여기서
템플릿을 뜨고 좌표를 잴 수 있게 한다.
"""

LEVELUP_SHOT_DELAY = 1.2
"""화면이 바뀌기를 기다렸다가 찍는 시간.

여기만은 고정 대기를 쓴다. 다음 화면이 어떻게 생겼는지 몰라서 기다릴 조건을
세울 수가 없다 — 그걸 알아내려고 찍는 것이다. 진단 경로에만 있고 정상 흐름의
속도에는 영향을 주지 않는다.
"""

POPUP_TIMEOUT = 5.0
"""Auto 를 누르고 '자동 열기' 팝업이 뜨기까지 기다릴 상한."""

TIDY_TIMEOUT = 5.0
"""'정리 하기' 를 누르고 화면이 넘어가기를 기다릴 상한."""

MAX_TIDY_TAPS = 4
"""주황 버튼을 이어서 누를 최대 횟수.

정리는 '정리하기 → 정리 하기 → 정리하기' 세 번이면 끝난다. 한 번의 여유를
두되 그 이상은 같은 버튼을 헛누르고 있는 것이니 멈춘다.
"""

AUTO_POLL = 3.0
"""Auto 버튼이 다시 보이는지 확인할 간격. 몇 분씩 걸리는 일이라 자주 볼 이유가 없다."""

AUTO_WAIT_TIMEOUT = 30.0
"""Auto 버튼을 이만큼 기다려도 안 보이면 퀘스트확인부터 다시 본다.

돌고 있는 중일 수도, 팝업에 가려진 것일 수도 있다. 어느 쪽인지 가리려 하지 않고
그냥 처음부터 다시 본다. 상태기가 `retry` 로 열 번까지 봐 주므로 그동안 끝난다.
"""

DISMISS_ROUNDS = 20
"""결과 팝업을 빈 곳 탭으로 치우는 최대 횟수."""

DISMISS_TIMEOUT = 3.0
"""한 번 탭한 뒤 퀘스트창이 다시 보이기를 기다릴 상한."""


class OvenEquipmentDraw(QuestDefinition):
    name = "오븐에서 장비 뽑기"
    name_templates = ["quest_oven_draw"]

    template_group = "퀘스트 - 장비 뽑기"
    setup_order = 40
    template_specs = [
        TemplateSpec(
            name="quest_oven_draw",
            label="퀘스트 창",
            where="전투화면에 '오븐에서 장비 뽑기 N번' 퀘스트가 회색으로 떠 있을 때",
            what="퀘스트 이름 글자 줄",
            tips=(NUMBER_TIP, SIZE_TIP),
            default_area=NormRect(0.7611, 0.5354, 0.1880, 0.0177),
        ),
        TemplateSpec(
            name=AUTO_TEMPLATE,
            label="오븐 auto 버튼",
            where="전투화면 아래쪽 '플레이트 강화' 의 오븐 모형",
            what="오븐 왼쪽 아래의 청록색 'Auto' 버튼",
            tips=("꺼져 있는 상태를 잡는다. 돌고 있으면 노란색이라 걸리지 않는다.",),
            default_area=NormRect(0.3208, 0.8896, 0.0733, 0.0167),
        ),
    ]
    # '시작' 버튼은 템플릿을 두지 않는다. 같은 자리에 '정리하기' 가 대신 뜨는
    # 경우가 있어 글자로 가리면 그때마다 막힌다. 색으로 찾는다.

    def execute(self, ctx: Context) -> StepResult:
        result = self._start_auto(ctx)
        if not result.success:
            return result

        return self._dismiss_results(ctx)

    # ------------------------------------------------------------------
    def _start_auto(self, ctx: Context) -> StepResult:
        """자동 열기를 시작한다. 버튼이 안 보이면 다시 보일 때까지 기다린다."""
        try:
            match = ctx.find(AUTO_TEMPLATE, AUTO_THRESHOLD, AUTO_SEARCH)
        except TemplateError as exc:
            return StepResult.blocked(str(exc))

        if match is None:
            match, completed = self._wait_for_auto(ctx)
            if completed:
                ctx.log("기다리는 사이에 퀘스트가 완료됐습니다. 확인부터 다시 봅니다.")
                return StepResult.ok()
            if match is None:
                if ctx.stopping:
                    # 정지 요청으로 깬 것이라 퀘스트가 막힌 게 아니다.
                    return StepResult.ok()
                return StepResult.retry(
                    f"{AUTO_WAIT_TIMEOUT:.0f}초 동안 오븐의 Auto 버튼을 찾지 못했습니다"
                )

        ctx.log(f"Auto 버튼 클릭 (일치도 {match.score:.2f})")
        ctx.tap_match(match)
        return self._press_confirm(ctx)

    def _wait_for_auto(self, ctx: Context) -> tuple[object | None, bool]:
        """Auto 버튼이 다시 보이기를 기다린다. ``(찾은 것, 완료됐는지)``.

        이미 돌고 있으면 버튼이 노란색이라 걸리지 않고, 장비 자동 분해 팝업이
        오븐을 가리기도 한다. 어느 쪽인지 가리려 하지 않는다 — 노란 버튼을
        알아보려다 잘못 눌러 자동 열기를 꺼 버리는 쪽이 더 나쁘다.

        버튼만 보고 있으면 그사이 뽑기가 다 끝나 퀘스트가 완료돼도 남은 시간을
        그대로 버린다. 그래서 볼 때마다 퀘스트창도 같이 읽는다.

        **정리하기 팝업도 같이 본다.** 장비가 가득 차면 그 팝업이 오븐과
        퀘스트창을 함께 가려서, Auto 버튼도 완료도 영영 보이지 않는다. 그러면
        치울 수 있는 화면을 앞에 두고 30초를 통째로 버린다. 보이면 눌러 치우고
        계속 기다린다 — 다음 확인은 3초 뒤라 화면이 넘어갈 틈은 넉넉하다.
        """
        ctx.log(
            f"Auto 버튼이 안 보입니다. {AUTO_POLL:.0f}초 간격으로 "
            f"{AUTO_WAIT_TIMEOUT:.0f}초까지 기다립니다."
        )
        reader = QuestPanelReader(
            ctx.anchors.get(anchor_names.QUEST_PANEL_SAMPLE),
            panel_area=ctx.anchors.get(anchor_names.QUEST_PANEL),
        )
        found: list = []
        done: list = []
        tidy_taps = 0

        def settled(frame) -> bool:
            nonlocal tidy_taps
            match = ctx.find(AUTO_TEMPLATE, AUTO_THRESHOLD, AUTO_SEARCH)
            if match is not None:
                found.append(match)
                return True
            if reader.read(frame).state is PanelState.GOLD:
                done.append(True)
                return True

            if tidy_taps < MAX_TIDY_TAPS:
                rect = find_color_button(frame, BUTTON_ORANGE, BUTTON_BAND)
                if rect is not None:
                    tidy_taps += 1
                    ctx.log(
                        f"기다리는 사이 정리하기 팝업이 가리고 있습니다. 눌러서 치웁니다 "
                        f"({tidy_taps}/{MAX_TIDY_TAPS}, 중심 {rect.center[0]:.3f})"
                    )
                    ctx.tap_rect(rect)
            return False

        ctx.wait_until(settled, AUTO_WAIT_TIMEOUT, interval=AUTO_POLL)
        return (found[0] if found else None), bool(done)

    def _take_levelup_offer(self, ctx: Context) -> bool:
        """'오븐을 레벨업 할 수 있습니다' 확인창이면 레벨업까지 마치고 True.

        레벨업 → 오븐 성장 순으로 누른다. 뽑기는 이번 판에 돌지 않으므로
        여기서 끝내고 퀘스트확인부터 다시 밟게 한다. 오븐이 올라간 뒤에는
        같은 창이 다시 뜨지 않으니 다음 판에서 정상적으로 진행된다.

        두 버튼 다 **찾은 자리를** 누른다. 확인창은 '그냥 열기' 가 바로 옆에
        붙어 있어서, 좌표를 짐작해 누르면 원치 않는 쪽이 눌린다.

        두 버튼은 저장소에 함께 든 조각(``ccc/assets/``)으로 찾는다. 몇 시간에
        한 번 스쳐 가는 창이라 사용자가 그 순간을 붙잡아 캡처하기 어렵다.
        """
        try:
            offer = find(ctx.frame, load_asset(LEVELUP_TEMPLATE), LEVELUP_THRESHOLD, LEVELUP_SEARCH)
        except (FileNotFoundError, KeyError) as exc:
            log.warning("번들 조각을 쓸 수 없습니다: %s", exc)
            return False
        if offer is None:
            return False

        self._keep_shot(ctx, "1-확인창")
        ctx.log(f"오븐 레벨업 확인창 감지 (일치도 {offer.score:.2f}) → '레벨업' 클릭")
        ctx.tap_match(offer)
        self._keep_shot(ctx, "2-레벨업-누른-뒤", settle=True)

        if not self._grow_oven(ctx, LEVELUP_GROW_TIMEOUT):
            ctx.log("'오븐 성장' 버튼을 찾지 못했습니다. 확인부터 다시 봅니다.")
        return True

    def _grow_oven(self, ctx: Context, timeout: float = 0.0) -> bool:
        """'오븐 성장' 버튼이 보이면 누르고 True.

        **어떤 경로로 그 화면에 왔든 누른다.** 확인창의 '레벨업' 은 '정리하기'
        와 똑같은 주황 버튼이라, 확인창을 못 알아본 판에서는 색으로 찾는 쪽이
        먼저 눌러 버린다. 그러면 오븐 레벨 화면까지는 갔는데 아무도 마무리를
        하지 않아, 네비게이터가 X 로 닫고 레벨업은 영영 안 된다.

        그래서 '확인창을 눌렀으니 다음은 성장' 이라는 순서에 기대지 않고,
        **성장 버튼이 화면에 있으면 그것만으로 누를 이유가 된다.**
        """
        grow = self._wait_for_grow(ctx, timeout)
        if grow is None:
            return False

        ctx.log(f"'오븐 성장' 클릭 (일치도 {grow.score:.2f})")
        ctx.tap_match(grow)
        self._keep_shot(ctx, "3-오븐성장-누른-뒤", settle=True)
        return True

    def _wait_for_grow(self, ctx: Context, timeout: float):
        """성장 버튼을 찾는다. ``timeout`` 이 0 이면 지금 화면만 본다.

        게이지가 찼는지에 따라 '오븐 성장' 과 '레벨업!' 중 하나가 뜬다. 둘 다
        찾아보고 먼저 걸리는 쪽을 돌려준다.
        """
        assets = []
        for name in GROW_TEMPLATES:
            try:
                assets.append(load_asset(name))
            except (FileNotFoundError, KeyError) as exc:
                log.warning("번들 조각을 쓸 수 없습니다: %s", exc)
        if not assets:
            return None

        def look(frame):
            for asset in assets:
                match = find(frame, asset, GROW_THRESHOLD, GROW_SEARCH)
                if match is not None:
                    return match
            return None

        if timeout <= 0:
            return look(ctx.frame)

        found = []

        def appeared(frame) -> bool:
            match = look(frame)
            if match is None:
                return False
            found.append(match)
            return True

        ctx.wait_until(appeared, timeout)
        return found[0] if found else None

    def _keep_shot(self, ctx: Context, name: str, settle: bool = False) -> None:
        """레벨업 과정의 화면을 남긴다.

        가끔만 지나가는 길이라, 지날 때 찍어 두지 않으면 나중에 무엇을 보고
        무엇을 눌러야 하는지 잴 수가 없다.
        """
        if settle:
            # 화면이 바뀔 틈을 준다. 다음 화면 모습을 모르니 기다릴 조건을
            # 세울 수 없어 여기서만 고정 대기를 쓴다.
            if not ctx.sleep(LEVELUP_SHOT_DELAY):
                return
            ctx.refresh()
        saved = save_frame(ctx.frame, LEVELUP_SHOT_DIR, name)
        if saved:
            ctx.log(f"화면 저장: {saved}")

    def _press_confirm(self, ctx: Context) -> StepResult:
        """'자동 열기' 팝업의 주황 버튼을 누른다.

        보통은 '시작' 이고, 장비가 가득 차 있으면 '정리하기' 다. 글자를 가리지
        않고 색으로 찾아 누른다 — 어느 쪽이든 눌러야 할 버튼은 그것 하나다.
        """
        rect = self._wait_for_button(ctx, POPUP_TIMEOUT)
        if rect is None:
            return StepResult.blocked("'자동 열기' 팝업의 시작/정리하기 버튼을 찾지 못했습니다")

        ctx.log(f"주황 버튼 클릭 (중심 {rect.center[0]:.3f}, {rect.center[1]:.3f})")
        self._tap_button(ctx, rect)
        return StepResult.ok()

    def _wait_for_button(self, ctx: Context, timeout: float) -> NormRect | None:
        """주황 버튼이 띠 안에 나타나기를 기다렸다가 그 자리를 돌려준다."""
        found: list[NormRect] = []

        def appeared(frame) -> bool:
            rect = find_color_button(frame, BUTTON_ORANGE, BUTTON_BAND)
            if rect is None:
                return False
            found.append(rect)
            return True

        ctx.wait_until(appeared, timeout)
        return found[0] if found else None

    def _tap_button(self, ctx: Context, rect: NormRect) -> None:
        """버튼을 누르고, 그 버튼이 **그 자리에서** 없어질 때까지 기다린다.

        '없어질 때까지' 가 아니라 '그 자리에서' 인 것이 중요하다. 정리 과정은
        같은 띠의 좌우 다른 자리에 다음 버튼을 띄우므로, 버튼의 유무만 보면
        다음 화면의 버튼을 보고 아직 안 넘어갔다고 착각한다.

        기다리지 않고 돌아가면 방금 누른 버튼이 화면에 남아 있는 동안 다음
        검사가 돌아 같은 버튼을 또 누른다.
        """
        ctx.tap_rect(rect)

        def moved(frame) -> bool:
            now = find_color_button(frame, BUTTON_ORANGE, BUTTON_BAND)
            return now is None or not now.near(rect)

        ctx.wait_until(moved, TIDY_TIMEOUT)

    def _dismiss_results(self, ctx: Context) -> StepResult:
        """뽑힌 장비 팝업을 빈 곳 탭으로 치우며 뽑기가 끝나기를 기다린다.

        빈 곳 탭은 **X 버튼이 없는 팝업**을 넘기는 수단이다. 장비 비교 팝업이
        그런 경우다. 반대로 X 가 있는 팝업은 빈 곳을 아무리 눌러도 닫히지 않는다.
        재료(행운반죽)가 모자라 '아이템이 부족합니다' 안내가 뜨는 경우가 그렇고,
        예전에는 여기서 스무 번을 두드리며 1분을 버린 뒤에야 넘어갔다.

        그래서 X 가 보이면 두드리기를 멈추고 진행 불가로 알린다. 팝업을 치우는
        건 상태기의 몫이고(그쪽이 X 를 누른다), 재료가 없어 못 하는 것이라면
        사람이 알아야 한다.

        X 가 없는 채로 상한까지 못 치웠을 때는 진행 불가로 보지 않는다.
        퀘스트창이 다시 보이면 상태기가 완료 여부를 직접 확인하기 때문이다.

        검사 순서가 곧 규칙이다.

            레벨업 확인창 → 주황 버튼 → 퀘스트창 → X → 빈 곳 탭

        레벨업 확인창과 정리 화면에는 하단 X 가 같이 보인다. X 를 먼저 보면
        눌러 볼 것을 눌러 보지도 못하고 재료 부족으로 오진한다. 정리 화면은
        퀘스트창까지 가리지 않아서, 퀘스트창을 먼저 보면 아직 '정리 하기' 가
        떠 있는데도 다 끝난 줄 알고 나가 버린다.

        **정리를 한 판은 실패가 아니다.** 정리하느라 이번 판의 뽑기는 돌지
        않지만, 자리가 생겼으니 다음 판은 정상으로 돌아간다. 그런데도 재료
        부족으로 알리면 사람을 헛되이 부르고 실패 3회를 향해 쌓인다.
        """
        panel_area = ctx.anchors.get(anchor_names.QUEST_PANEL)
        safe_tap = ctx.anchors.get(anchor_names.SAFE_TAP)
        navigator = BattleScreenNavigator(ctx.anchors.get(anchor_names.NAV_CLOSE))
        tidy_taps = 0
        empty_taps = 0

        def panel_back(frame) -> bool:
            return panel_visible(frame, panel_area)

        for _ in range(DISMISS_ROUNDS):
            if self._take_levelup_offer(ctx):
                return StepResult.ok()

            # 확인창을 못 알아본 판에서는 색으로 찾는 쪽이 '레벨업' 을 먼저 눌러
            # 여기까지 와 있을 수 있다. 어떻게 왔든 성장 버튼이 보이면 누른다.
            if self._grow_oven(ctx):
                return StepResult.ok()

            rect = find_color_button(ctx.frame, BUTTON_ORANGE, BUTTON_BAND)
            if rect is not None and tidy_taps < MAX_TIDY_TAPS:
                tidy_taps += 1
                ctx.log(
                    f"'정리 하기' 를 눌러 장비를 정리합니다 "
                    f"({tidy_taps}/{MAX_TIDY_TAPS}, 중심 {rect.center[0]:.3f})"
                )
                self._tap_button(ctx, rect)
                continue

            if panel_back(ctx.frame):
                if empty_taps:
                    ctx.log(f"결과 팝업 정리 완료 (빈 곳 {empty_taps}회 탭)")
                return StepResult.ok()

            if navigator.has_close_button(ctx.frame):
                if tidy_taps:
                    # 이번 판은 뽑기가 아니라 정리에 썼다. 정리를 마치면 자리가
                    # 생겨 다음 판은 정상으로 돌아가므로 실패로 세지 않는다.
                    # 여기서 '재료 부족' 으로 알리면 사람을 헛되이 부른다.
                    return StepResult.retry(
                        f"장비를 정리했습니다 ({tidy_taps}회). 다시 확인합니다"
                    )
                return StepResult.blocked(
                    "자동 열기가 시작되지 않았습니다. 재료가 부족할 수 있습니다"
                )

            ctx.tap_rect(safe_tap)
            empty_taps += 1
            if ctx.wait_until(panel_back, DISMISS_TIMEOUT):
                ctx.log(f"결과 팝업 정리 완료 (빈 곳 {empty_taps}회 탭)")
                return StepResult.ok()
            if ctx.stopping:
                return StepResult.ok()

        ctx.log("뽑기 결과 팝업이 계속 남아 있습니다. 상태 확인으로 넘어갑니다.")
        return StepResult.ok()
