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

**이미 돌고 있는 경우.** Auto 가 켜져 있으면 버튼이 청록색에서 노란색으로 바뀐다.
그러면 1단계의 청록색 템플릿이 걸리지 않아 "Auto 버튼을 찾지 못했습니다" 로 3번
연속 실패하고 멈춰 버렸다. 지금은 꺼진 버튼을 못 찾으면 켜진 버튼을 확인하고,
켜져 있으면 누르지 않고 끝나기를 기다린다.
"""

from __future__ import annotations

from .. import anchors as anchor_names
from ..context import Context
from ..geometry import NormRect
from ..quest.definition import QuestDefinition, StepResult
from ..quest.panel import panel_visible
from ..templates_spec import NUMBER_TIP, SIZE_TIP, TemplateSpec
from ..vision import TemplateError

AUTO_TEMPLATE = "oven_auto"
AUTO_ON_TEMPLATE = "oven_auto_on"
START_TEMPLATE = "oven_auto_start"

AUTO_SEARCH = NormRect(0.18, 0.82, 0.40, 0.12)
"""Auto 버튼을 찾을 범위. 오븐 왼쪽 아래를 넉넉히 덮는다.

실측 위치는 중심 (0.360, 0.890) 이지만 창 비율이 다르면 조금씩 밀리므로,
고정 좌표로 누르지 않고 이 범위 안에서 찾아서 누른다.
"""

START_SEARCH = NormRect(0.20, 0.82, 0.60, 0.10)
"""'시작' 버튼을 찾을 범위. 실측 중심 (0.499, 0.882)."""

AUTO_THRESHOLD = 0.80
AUTO_ON_THRESHOLD = 0.80
START_THRESHOLD = 0.85

POPUP_TIMEOUT = 5.0
"""Auto 를 누르고 '자동 열기' 팝업이 뜨기까지 기다릴 상한."""

RUNNING_POLL = 3.0
"""이미 돌고 있을 때 다시 볼 간격. 몇 분씩 걸리는 일이라 자주 볼 이유가 없다."""

RUNNING_TIMEOUT = 300.0
"""자동 열기가 끝나기를 기다릴 상한. 넘으면 진행 불가로 본다."""

DISMISS_ROUNDS = 20
"""결과 팝업을 빈 곳 탭으로 치우는 최대 횟수."""

DISMISS_TIMEOUT = 3.0
"""한 번 탭한 뒤 퀘스트창이 다시 보이기를 기다릴 상한."""


class OvenEquipmentDraw(QuestDefinition):
    name = "오븐에서 장비 뽑기"
    name_templates = ["quest_oven_draw"]

    template_specs = [
        TemplateSpec(
            name="quest_oven_draw",
            label="퀘스트 이름 · 오븐에서 장비 뽑기",
            where="전투화면에 '오븐에서 장비 뽑기 N번' 퀘스트가 회색으로 떠 있을 때",
            what="퀘스트 이름 글자 줄",
            tips=(NUMBER_TIP, SIZE_TIP),
            default_area=NormRect(0.7611, 0.5354, 0.1880, 0.0177),
        ),
        TemplateSpec(
            name=AUTO_TEMPLATE,
            label="오븐 Auto 버튼",
            where="전투화면 아래쪽 '플레이트 강화' 의 오븐 모형",
            what="오븐 왼쪽 아래의 청록색 'Auto' 버튼",
            tips=("꺼져 있는 상태를 잡는다. 켜져 있으면 노란색이라 따로 뜬다.",),
            default_area=NormRect(0.3208, 0.8896, 0.0733, 0.0167),
        ),
        TemplateSpec(
            name=AUTO_ON_TEMPLATE,
            label="오븐 Auto 버튼 (켜짐)",
            where="자동 열기가 돌고 있는 동안의 전투화면",
            what="같은 자리에서 노란색으로 바뀐 'Auto' 버튼",
            tips=("돌고 있는지 알아보는 데만 쓴다. 이 버튼은 누르지 않는다.",),
            default_area=NormRect(0.3208, 0.8896, 0.0733, 0.0167),
        ),
        TemplateSpec(
            name=START_TEMPLATE,
            label="자동 열기 시작 버튼",
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
        """자동 열기를 시작한다. 이미 돌고 있으면 끝나기를 기다린다."""
        try:
            match = ctx.find(AUTO_TEMPLATE, AUTO_THRESHOLD, AUTO_SEARCH)
        except TemplateError as exc:
            return StepResult.blocked(str(exc))

        if match is not None:
            ctx.log(f"Auto 버튼 클릭 (일치도 {match.score:.2f})")
            ctx.tap_match(match)
            return self._press_start(ctx)

        # 꺼진(청록) 버튼이 없다. 이미 켜져 있으면 같은 자리가 노란색이다.
        return self._wait_until_auto_done(ctx)

    def _wait_until_auto_done(self, ctx: Context) -> StepResult:
        """이미 돌고 있는 자동 열기가 끝나기를 기다린다.

        여기서 Auto 를 다시 누르면 안 된다. 켜진 버튼을 누르면 자동 열기가
        꺼져 버려서, 기다리면 저절로 끝날 일을 스스로 망친다.
        """
        try:
            running = ctx.find(AUTO_ON_TEMPLATE, AUTO_ON_THRESHOLD, AUTO_SEARCH)
        except TemplateError as exc:
            return StepResult.blocked(f"오븐의 Auto 버튼을 찾지 못했습니다 ({exc})")

        if running is None:
            # 연출이 오븐을 가렸거나 화면이 아직 안 돌아온 것일 수 있다. 사람을
            # 부르지 말고 퀘스트확인부터 다시 보게 한다.
            return StepResult.retry("오븐의 Auto 버튼을 찾지 못했습니다")

        ctx.log(
            f"자동 열기가 이미 돌고 있습니다 (일치도 {running.score:.2f}). "
            f"{RUNNING_POLL:.0f}초 간격으로 끝나기를 기다립니다."
        )

        def finished(_frame) -> bool:
            return ctx.find(AUTO_ON_TEMPLATE, AUTO_ON_THRESHOLD, AUTO_SEARCH) is None

        if ctx.wait_until(finished, RUNNING_TIMEOUT, interval=RUNNING_POLL):
            ctx.log("자동 열기가 끝났습니다.")
            return StepResult.ok()

        if ctx.stopping:
            # 정지 요청으로 깬 것이라 퀘스트가 막힌 게 아니다. 실패로 세지 않는다.
            return StepResult.ok()

        return StepResult.blocked(
            f"자동 열기가 {RUNNING_TIMEOUT:.0f}초 안에 끝나지 않았습니다"
        )

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
