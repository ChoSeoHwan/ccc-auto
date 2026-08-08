"""퀘스트: 오븐에서 장비 뽑기.

    퀘스트 1315 · 오븐에서 장비 뽑기 15번 · 0/15

이름 템플릿은 '오븐에서 장비 뽑기' 첫 줄만 잡아 두었다. 횟수(15번)는 다음
줄에 따로 있어서 10번이든 20번이든 같은 퀘스트로 걸린다.

수행 절차 (실측으로 확인한 순서)
    1. 오븐 왼쪽 아래의 Auto 버튼을 누른다.       → '자동 열기' 팝업이 뜬다
    2. 팝업의 주황색 '시작' 버튼을 누른다.        → 팝업이 스스로 닫히고 뽑기 시작
    3. 뽑힌 장비 비교 팝업을 빈 곳 탭으로 닫는다. → 이 팝업에는 X 버튼이 없다

3단계 팝업은 '장착 / 판매' 버튼을 갖고 있지만 어느 쪽도 누르지 않는다.
빈 곳을 누르면 아무 선택 없이 닫히고 장비는 가방에 남는다.

**재료가 모자랄 때.** 행운반죽이 없으면 '시작' 을 눌러도 뽑기가 돌지 않고
'아이템이 부족합니다' 안내가 뜬다. 이 팝업에는 X 가 있어서 빈 곳 탭으로는
닫히지 않는다. 3단계에서 X 가 보이면 두드리기를 멈추고 진행 불가로 알린다.

**오븐을 올릴 수 있을 때.** '시작' 을 누르면 가끔 "오븐을 레벨업 할 수 있습니다"
확인창이 뜬다. 이때는 레벨업 → 오븐 성장 순으로 누르고 퀘스트확인부터 다시 밟는다.
뽑기는 이번 판에 돌지 않지만, 오븐이 올라가면 같은 창이 다시 뜨지 않는다.

**Auto 버튼이 안 보이는 경우.** 이미 돌고 있으면 버튼이 노란색으로 바뀌고, 장비
자동 분해 팝업까지 겹쳐서 그 상태를 알아보기가 어렵다. 그래서 켜진 버튼을 따로
알아보려 하지 않는다. 청록색 버튼이 다시 보일 때까지 기다리기만 하고, 30초 안에
안 보이면 퀘스트확인부터 다시 본다.
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
from ..vision import TemplateError, find

log = logging.getLogger(__name__)

AUTO_TEMPLATE = "oven_auto"
START_TEMPLATE = "oven_auto_start"
LEVELUP_TEMPLATE = "oven_levelup"
GROW_TEMPLATE = "oven_grow"

AUTO_SEARCH = NormRect(0.18, 0.82, 0.40, 0.12)
"""Auto 버튼을 찾을 범위. 오븐 왼쪽 아래를 넉넉히 덮는다.

실측 위치는 중심 (0.360, 0.890) 이지만 창 비율이 다르면 조금씩 밀리므로,
고정 좌표로 누르지 않고 이 범위 안에서 찾아서 누른다.
"""

START_SEARCH = NormRect(0.20, 0.82, 0.60, 0.10)
"""'시작' 버튼을 찾을 범위. 실측 중심 (0.499, 0.882)."""

AUTO_THRESHOLD = 0.80
START_THRESHOLD = 0.85
LEVELUP_THRESHOLD = 0.80
GROW_THRESHOLD = 0.80

LEVELUP_SEARCH = NormRect(0.45, 0.80, 0.55, 0.12)
"""'레벨업' 버튼을 찾을 범위.

실측: 확인창의 레벨업 버튼은 게임 좌표 (0.615, 0.865) 에 0.150x0.031 크기로 앉는다.
그 자리를 넉넉히 감싼다. 왼쪽 절반은 일부러 뺐다 — 거기 '그냥 열기' 가 있고,
둘을 한 범위에 넣으면 잘못 걸릴 여지를 만든다.
"""

GROW_SEARCH = None
"""'오븐 성장' 버튼을 찾을 범위. 그 화면 스크린샷이 없어 위치를 재지 못했다.

전체 탐색은 범위를 준 것보다 20배 비싸다(166ms 대 6~9ms). 확인창을 만난 뒤에만
잠깐 도는 경로라 감당되지만, 위치가 실측되면 범위를 채워 넣어라.
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
        TemplateSpec(
            name=START_TEMPLATE,
            label="오븐 auto 내 시작 버튼",
            where="Auto 버튼을 누르면 뜨는 '자동 열기' 팝업",
            what="주황색 '시작' 버튼 전체",
            default_area=NormRect(0.3315, 0.8552, 0.3352, 0.0526),
        ),
    ]

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
        return self._press_start(ctx)

    def _wait_for_auto(self, ctx: Context) -> tuple[object | None, bool]:
        """Auto 버튼이 다시 보이기를 기다린다. ``(찾은 것, 완료됐는지)``.

        이미 돌고 있으면 버튼이 노란색이라 걸리지 않고, 장비 자동 분해 팝업이
        오븐을 가리기도 한다. 어느 쪽인지 가리려 하지 않는다 — 노란 버튼을
        알아보려다 잘못 눌러 자동 열기를 꺼 버리는 쪽이 더 나쁘다.

        버튼만 보고 있으면 그사이 뽑기가 다 끝나 퀘스트가 완료돼도 남은 시간을
        그대로 버린다. 그래서 볼 때마다 퀘스트창도 같이 읽는다.
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

        def settled(frame) -> bool:
            match = ctx.find(AUTO_TEMPLATE, AUTO_THRESHOLD, AUTO_SEARCH)
            if match is not None:
                found.append(match)
                return True
            if reader.read(frame).state is PanelState.GOLD:
                done.append(True)
                return True
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

        grow = self._wait_for_grow(ctx)
        if grow is None:
            ctx.log("'오븐 성장' 버튼을 찾지 못했습니다. 확인부터 다시 봅니다.")
            return True

        ctx.log(f"'오븐 성장' 클릭 (일치도 {grow.score:.2f})")
        ctx.tap_match(grow)
        self._keep_shot(ctx, "3-오븐성장-누른-뒤", settle=True)
        return True

    def _wait_for_grow(self, ctx: Context):
        """'오븐 성장' 버튼이 뜨기를 기다린다. 번들 조각으로 찾는다."""
        try:
            asset = load_asset(GROW_TEMPLATE)
        except (FileNotFoundError, KeyError) as exc:
            log.warning("번들 조각을 쓸 수 없습니다: %s", exc)
            return None

        found = []

        def appeared(frame) -> bool:
            match = find(frame, asset, GROW_THRESHOLD, GROW_SEARCH)
            if match is None:
                return False
            found.append(match)
            return True

        ctx.wait_until(appeared, LEVELUP_GROW_TIMEOUT)
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

    def _press_start(self, ctx: Context) -> StepResult:
        try:
            match = ctx.wait_for_template(
                START_TEMPLATE, POPUP_TIMEOUT, START_THRESHOLD, START_SEARCH
            )
        except TemplateError as exc:
            return StepResult.blocked(str(exc))

        if match is None:
            return StepResult.blocked("'자동 열기' 팝업의 시작 버튼을 찾지 못했습니다")

        ctx.log(f"'시작' 클릭 (일치도 {match.score:.2f})")
        ctx.tap_match(match)
        return StepResult.ok()

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
        """
        panel_area = ctx.anchors.get(anchor_names.QUEST_PANEL)
        safe_tap = ctx.anchors.get(anchor_names.SAFE_TAP)
        navigator = BattleScreenNavigator(ctx.anchors.get(anchor_names.NAV_CLOSE))

        def panel_back(frame) -> bool:
            return panel_visible(frame, panel_area)

        for attempt in range(DISMISS_ROUNDS):
            if panel_back(ctx.frame):
                if attempt:
                    ctx.log(f"결과 팝업 정리 완료 ({attempt}회 탭)")
                return StepResult.ok()

            # 레벨업 확인창 검사가 X 검사보다 먼저다. 이 창에도 하단 X 가 보여서
            # 순서를 바꾸면 레벨업을 해 보지도 못하고 진행 불가로 빠진다.
            if self._take_levelup_offer(ctx):
                return StepResult.ok()

            # 첫 판은 봐 준다. 시작 직후에는 아직 연출이 돌고 있을 수 있다.
            if attempt and navigator.has_close_button(ctx.frame):
                return StepResult.blocked(
                    "자동 열기가 시작되지 않았습니다. 재료가 부족할 수 있습니다"
                )

            ctx.tap_rect(safe_tap)
            if ctx.wait_until(panel_back, DISMISS_TIMEOUT):
                ctx.log(f"결과 팝업 정리 완료 ({attempt + 1}회 탭)")
                return StepResult.ok()
            if ctx.stopping:
                return StepResult.ok()

        ctx.log("뽑기 결과 팝업이 계속 남아 있습니다. 상태 확인으로 넘어갑니다.")
        return StepResult.ok()
