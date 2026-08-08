"""뽑기 계열 퀘스트의 공통 절차.

쿠키 뽑기와 펫 뽑기는 화면만 다르고 하는 일이 같다.

    1. 퀘스트창을 누르면 해당 뽑기 화면으로 자동 이동한다.
    2. 주황색 '10회' 버튼을 누르면 뽑기가 진행된다.

결과 화면에는 닫기(X) 버튼이 있어서 상태기가 알아서 치운다.

뽑기권이 모자라면 '10회' 버튼이 주황색에서 청록색으로 바뀌며 다이아 결제로
전환된다. 템플릿이 주황 버튼이라 그때는 매칭이 실패하고 진행 불가로 멈춘다.
다이아를 모르는 사이에 쓰지 않기 위한 것이므로 고치지 말 것.

시간은 어디서도 고정으로 재우지 않는다. 화면이 바뀌면 바로 다음으로 넘어가고,
아래 값들은 "이만큼까지만 기다린다" 는 상한이다.

파일명이 밑줄로 시작해서 퀘스트 목록에는 올라가지 않는다.
"""

from __future__ import annotations

from .. import anchors as anchor_names
from ..context import Context
from ..geometry import NormRect
from ..quest.definition import QuestDefinition, StepResult
from ..quest.navigator import BattleScreenNavigator
from ..templates_spec import NUMBER_TIP, SIZE_TIP, TemplateSpec
from ..vision import TemplateError

DRAW_SEARCH = NormRect(0.20, 0.74, 0.60, 0.12)
"""'10회' 버튼을 찾을 범위. 실측 중심 (0.498, 0.810)."""

DRAW_THRESHOLD = 0.85
"""버튼이 커서 여유 있게 잡힌다 (실측 100% 1.000 / 75% 0.968 / 50% 0.991)."""

SCREEN_TIMEOUT = 6.0
"""퀘스트창을 누르고 뽑기 화면이 뜨기까지 기다릴 상한."""

DRAW_TIMEOUT = 8.0
"""뽑기 결과 화면이 뜨기까지 기다릴 상한."""


class TenDrawQuest(QuestDefinition):
    """퀘스트창을 눌러 이동한 뒤 '10회' 버튼을 누르는 퀘스트."""

    draw_template: str = ""
    """해당 뽑기 화면의 주황색 '10회' 버튼 템플릿."""

    def execute(self, ctx: Context) -> StepResult:
        ctx.log("퀘스트창을 눌러 뽑기 화면으로 이동합니다.")
        ctx.tap_rect(ctx.anchors.get(anchor_names.QUEST_PANEL))

        try:
            match = ctx.wait_for_template(
                self.draw_template, SCREEN_TIMEOUT, DRAW_THRESHOLD, DRAW_SEARCH
            )
        except TemplateError as exc:
            return StepResult.blocked(str(exc))

        if match is None:
            return StepResult.blocked(
                "'10회' 뽑기 버튼을 찾지 못했습니다. 뽑기권이 부족해 다이아 결제로 "
                "바뀌었을 수 있습니다."
            )

        ctx.log(f"'10회' 뽑기 (일치도 {match.score:.2f})")
        ctx.tap_match(match)
        self._wait_for_result(ctx)
        return StepResult.ok()

    @staticmethod
    def _wait_for_result(ctx: Context) -> None:
        """뽑기 결과 화면이 뜰 때까지 기다린다.

        결과 화면에는 닫기(X) 버튼이 있으므로 그것이 보이면 연출이 끝난 것이다.
        상한을 넘겨도 실패로 보지 않는다 — 상태기가 어차피 전투화면으로
        되돌리며 다시 확인한다.
        """
        navigator = BattleScreenNavigator(ctx.anchors.get(anchor_names.NAV_CLOSE))
        ctx.wait_until(navigator.has_close_button, DRAW_TIMEOUT)
