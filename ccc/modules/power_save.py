"""절전 모드 해제.

게임은 한동안 입력이 없으면 스스로 절전 모드로 넘어간다. 이 화면에는
하단 네비게이션도, 닫기(X) 버튼도, 퀘스트창도 없어서 다른 모듈이 화면을
제대로 읽지 못한다. 뒤로가기 한 번이면 빠져나오므로 가장 먼저 검사한다.

판별은 하단 오른쪽의 '더 절전 모드' 라벨로 한다. 이 문구는 절전 모드에만
있고 흰 글씨라, 이진화 매칭으로 배경과 무관하게 잡힌다.
"""

from __future__ import annotations

from ..context import Context
from ..geometry import NormRect
from ..templates_spec import TemplateSpec
from ..vision import TemplateError
from .base import AutomationModule

LABEL_TEMPLATE = "power_save_label"
SEARCH_AREA = NormRect(0.50, 0.905, 0.50, 0.075)
MATCH_THRESHOLD = 0.70


class ExitPowerSaveMode(AutomationModule):
    name = "절전 모드 해제"
    description = "절전 모드로 넘어가면 뒤로가기로 빠져나옵니다."
    interval = 2.0
    priority = 5          # 화면 판독이 오염되기 전에 가장 먼저 처리한다
    exclusive = True
    enabled_by_default = True

    template_specs = [
        TemplateSpec(
            name=LABEL_TEMPLATE,
            label="더 절전 모드 라벨",
            where="게임을 한동안 두면 저절로 들어가는 절전 모드 화면",
            what="화면 오른쪽 아래의 '더 절전 모드' 글자",
            tip="토글 스위치는 빼고 글자만 잡는다.",
        )
    ]

    def setup(self, ctx: Context) -> None:
        self._warned = False

    def check(self, ctx: Context) -> bool:
        threshold = ctx.option("threshold", MATCH_THRESHOLD)
        try:
            return ctx.find_text(LABEL_TEMPLATE, threshold, SEARCH_AREA) is not None
        except TemplateError as exc:
            if not self._warned:
                ctx.log(f"절전 모드를 감지할 수 없습니다: {exc}")
                self._warned = True
            return False

    def run(self, ctx: Context) -> None:
        ctx.log("절전 모드 감지 → 뒤로가기로 해제합니다.")
        ctx.back()
        ctx.sleep(1.5)
