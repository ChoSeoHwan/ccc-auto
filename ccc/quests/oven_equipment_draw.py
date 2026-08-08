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

**Auto 버튼이 안 보이는 경우.** 이미 돌고 있으면 버튼이 노란색으로 바뀌고, 장비
자동 분해 팝업까지 겹쳐서 그 상태를 알아보기가 어렵다. 그래서 켜진 버튼을 따로
알아보려 하지 않는다. 청록색 버튼이 다시 보일 때까지 기다리기만 하고, 30초 안에
안 보이면 퀘스트확인부터 다시 본다.
"""

from __future__ import annotations

from .. import anchors as anchor_names
from ..context import Context
from ..geometry import NormRect
from ..quest.definition import QuestDefinition, StepResult
from ..quest.panel import QuestPanelReader, panel_visible
from ..quest.states import PanelState
from ..templates_spec import NUMBER_TIP, SIZE_TIP, TemplateSpec
from ..vision import TemplateError

AUTO_TEMPLATE = "oven_auto"
START_TEMPLATE = "oven_auto_start"

AUTO_SEARCH = NormRect(0.18, 0.82, 0.40, 0.12)
"""Auto 버튼을 찾을 범위. 오븐 왼쪽 아래를 넉넉히 덮는다.

실측 위치는 중심 (0.360, 0.890) 이지만 창 비율이 다르면 조금씩 밀리므로,
고정 좌표로 누르지 않고 이 범위 안에서 찾아서 누른다.
"""

START_SEARCH = NormRect(0.20, 0.82, 0.60, 0.10)
"""'시작' 버튼을 찾을 범위. 실측 중심 (0.499, 0.882)."""

AUTO_THRESHOLD = 0.80
START_THRESHOLD = 0.85

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

        self._dismiss_results(ctx)
        return StepResult.ok()

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

    def _dismiss_results(self, ctx: Context) -> None:
        """뽑힌 장비 팝업을 빈 곳 탭으로 치우며 뽑기가 끝나기를 기다린다.

        여기서 실패해도 진행 불가로 보지 않는다. 퀘스트창이 다시 보이면
        상태기가 완료 여부를 직접 확인하기 때문이다.
        """
        panel_area = ctx.anchors.get(anchor_names.QUEST_PANEL)
        safe_tap = ctx.anchors.get(anchor_names.SAFE_TAP)

        def panel_back(frame) -> bool:
            return panel_visible(frame, panel_area)

        for attempt in range(DISMISS_ROUNDS):
            if panel_back(ctx.frame):
                if attempt:
                    ctx.log(f"결과 팝업 정리 완료 ({attempt}회 탭)")
                return

            ctx.tap_rect(safe_tap)
            if ctx.wait_until(panel_back, DISMISS_TIMEOUT):
                ctx.log(f"결과 팝업 정리 완료 ({attempt + 1}회 탭)")
                return
            if ctx.stopping:
                return

        ctx.log("뽑기 결과 팝업이 계속 남아 있습니다. 상태 확인으로 넘어갑니다.")
