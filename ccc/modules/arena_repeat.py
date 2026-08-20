"""아레나 반복 도전 자동화."""

from __future__ import annotations

from ..context import Context
from ..geometry import NormRect
from ..templates_spec import SIZE_TIP, TemplateSpec
from ..vision import TemplateError
from .base import AutomationModule


CHALLENGE_TEMPLATE = "arena_challenge"
RESULT_TEMPLATE = "arena_result"

CHALLENGE_SEARCH = NormRect(0.25, 0.65, 0.50, 0.16)
RESULT_SEARCH = NormRect(0.20, 0.80, 0.60, 0.15)

CHALLENGE_THRESHOLD = 0.75
RESULT_THRESHOLD = 0.80
TRANSITION_TIMEOUT = 1.0


class ArenaRepeat(AutomationModule):
    name = "아레나 무한 도전"
    description = "도전 → 결과 ESC → 다시 도전을 멈출 때까지 반복합니다."
    interval = 0.0
    priority = 40
    exclusive = True
    enabled_by_default = False
    template_group = "아레나 무한 도전"
    template_specs = [
        TemplateSpec(
            name=CHALLENGE_TEMPLATE,
            label="도전하기 버튼",
            where="아레나 상대와 내 공덱이 보이는 도전 준비 화면",
            what="주황 버튼 안의 '도전하기' 글자만",
            tips=(SIZE_TIP, "버튼 전체보다 글자 주변만 작게 잡는다."),
            default_area=NormRect(0.3828, 0.6955, 0.1563, 0.0340),
        ),
        TemplateSpec(
            name=RESULT_TEMPLATE,
            label="결과 화면",
            where="WIN과 보상이 표시된 아레나 결과 화면",
            what="아래쪽의 고정 문구 '화면을 탭하세요' 주변",
            tips=(SIZE_TIP, "점수·순위·보상처럼 매번 바뀌는 부분은 제외한다."),
            default_area=NormRect(0.3359, 0.8500, 0.2500, 0.0500),
        ),
    ]

    def setup(self, ctx: Context) -> None:
        self._active = False
        self._action: str | None = None
        self._match = None
        self._warned: set[str] = set()

    def _find(
        self,
        ctx: Context,
        template: str,
        *,
        text: bool,
        threshold: float,
        search: NormRect,
    ):
        try:
            finder = ctx.find_text if text else ctx.find
            return finder(template, threshold, search)
        except TemplateError as exc:
            if template not in self._warned:
                ctx.log(f"아레나 자동화를 준비할 수 없습니다: {exc}")
                self._warned.add(template)
            return None

    def check(self, ctx: Context) -> bool:
        self._action = None
        self._match = self._find(
            ctx,
            RESULT_TEMPLATE,
            text=False,
            threshold=RESULT_THRESHOLD,
            search=RESULT_SEARCH,
        )
        if self._match is not None:
            self._active = True
            self._action = "result"
            return True
        self._match = self._find(
            ctx,
            CHALLENGE_TEMPLATE,
            text=True,
            threshold=CHALLENGE_THRESHOLD,
            search=CHALLENGE_SEARCH,
        )
        if self._match is not None:
            self._active = True
            self._action = "challenge"
            return True
        return self._active

    def run(self, ctx: Context) -> None:
        if self._match is None:
            return
        if self._action == "result":
            ctx.log(f"아레나 결과 화면 감지 (일치도 {self._match.score:.2f}) → ESC")
            ctx.back()
            ctx.wait_until(
                lambda _frame: self._find(
                    ctx,
                    RESULT_TEMPLATE,
                    text=False,
                    threshold=RESULT_THRESHOLD,
                    search=RESULT_SEARCH,
                )
                is None,
                TRANSITION_TIMEOUT,
            )
            return
        if self._action == "challenge":
            ctx.log(f"아레나 '도전하기' 클릭 (일치도 {self._match.score:.2f})")
            ctx.tap_match(self._match)
            ctx.wait_until(
                lambda _frame: self._find(
                    ctx,
                    CHALLENGE_TEMPLATE,
                    text=True,
                    threshold=CHALLENGE_THRESHOLD,
                    search=CHALLENGE_SEARCH,
                )
                is None,
                TRANSITION_TIMEOUT,
            )
