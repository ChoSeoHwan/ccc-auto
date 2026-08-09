"""전투화면 복귀.

메인 전투화면이 아니면 하단 네비게이션 중앙에 빨간 X 버튼이 나타난다.
이 자리는 전투화면에서 항상 비어 있어서(실측 빨강 비율 0.00) 빨강 비율만
보면 현재 화면이 전투화면인지 아닌지 바로 알 수 있다.

화면이 여러 겹으로 쌓여 있으면 X 를 여러 번 눌러야 하므로 상한을 두고
반복한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from ..context import Context
from ..geometry import NormRect

log = logging.getLogger(__name__)

RED_RATIO_THRESHOLD = 0.06
"""이 비율을 넘으면 X 버튼이 있다고 본다."""

MAX_CLOSE_CLICKS = 6
"""전투화면까지 돌아가려고 X 를 누를 최대 횟수. 화면이 여러 겹 쌓일 수 있다."""

_LOW_RED = ((0, 110, 80), (12, 255, 255))
_HIGH_RED = ((168, 110, 80), (179, 255, 255))


@dataclass(frozen=True)
class ReturnResult:
    reached: bool
    clicks: int
    reason: str = ""


class BattleScreenNavigator:
    """X 버튼을 눌러 메인 전투화면까지 되돌아간다."""

    def __init__(
        self,
        close_area: NormRect,
        max_clicks: int = MAX_CLOSE_CLICKS,
        wait_after_click: float = 1.5,
        poll_interval: float = 0.25,
        threshold: float = RED_RATIO_THRESHOLD,
    ):
        self.close_area = close_area
        self.max_clicks = max_clicks
        self.wait_after_click = wait_after_click
        """클릭 뒤 화면이 바뀌기를 기다리는 **제한 시간**. 바뀌면 즉시 넘어간다."""
        self.poll_interval = poll_interval
        self.threshold = threshold

    # ------------------------------------------------------------------
    def close_button_ratio(self, frame: np.ndarray) -> float:
        import cv2

        from ..vision import crop

        patch = crop(frame, self.close_area)
        if patch.size == 0:
            return 0.0
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, *_np(_LOW_RED)) | cv2.inRange(hsv, *_np(_HIGH_RED))
        return float(np.count_nonzero(mask)) / mask.size

    def has_close_button(self, frame: np.ndarray) -> bool:
        return self.close_button_ratio(frame) >= self.threshold

    def is_battle_screen(self, frame: np.ndarray) -> bool:
        return not self.has_close_button(frame)

    # ------------------------------------------------------------------
    def return_to_battle(self, ctx: Context, refresh=None) -> ReturnResult:
        """전투화면이 될 때까지 X 를 누른다.

        클릭 뒤에는 정해진 시간을 재우지 않고 화면이 바뀌는지 지켜본다.
        연출이 짧게 끝나는 경우 그만큼 빨리 넘어간다.
        """
        for clicks in range(self.max_clicks + 1):
            if self.is_battle_screen(ctx.frame):
                return ReturnResult(True, clicks)
            if ctx.stopping:
                return ReturnResult(False, clicks, "정지 요청")

            ctx.log(f"전투화면이 아니라 닫기 버튼을 누릅니다 ({clicks + 1}/{self.max_clicks})")
            ctx.tap_rect(self.close_area)
            ctx.wait_until(self.is_battle_screen, self.wait_after_click, self.poll_interval)

        return ReturnResult(
            False, self.max_clicks, f"닫기 버튼을 {self.max_clicks}번 눌러도 전투화면이 아닙니다"
        )


def _np(bounds: tuple[tuple[int, int, int], tuple[int, int, int]]):
    lower, upper = bounds
    return np.array(lower, np.uint8), np.array(upper, np.uint8)
