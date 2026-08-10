"""판별 실패 상황을 파일로 남긴다.

등록되지 않은 퀘스트가 나오면 자동화가 대기로 빠지는데, 그때 화면이 어땠는지
남겨 두면 나중에 퀘스트 지시문과 템플릿을 만들기 편하다.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import numpy as np

from .. import anchors as anchor_names
from ..anchors import AnchorSet
from ..config import CAPTURE_DIR
from ..geometry import NormRect
from ..vision import crop, imwrite
from .navigator import RED_RATIO_THRESHOLD, BattleScreenNavigator
from .panel import QuestPanelReader

log = logging.getLogger(__name__)


class DetectionReport:
    """지금 화면에서 각 인식기가 무엇을 읽고 있는지 정리한 결과."""

    def __init__(self, frame: np.ndarray, anchors: AnchorSet):
        reader = QuestPanelReader(
            anchors.get(anchor_names.QUEST_PANEL_SAMPLE),
            panel_area=anchors.get(anchor_names.QUEST_PANEL),
        )
        navigator = BattleScreenNavigator(anchors.get(anchor_names.NAV_CLOSE))

        self.panel = reader.read(frame)
        self.close_ratio = navigator.close_button_ratio(frame)
        self.is_battle_screen = navigator.is_battle_screen(frame)

    def lines(self) -> list[str]:
        return [
            f"퀘스트창 판정: {self.panel.state.value} "
            f"(황금 {self.panel.gold_ratio:.1%} / 회색 {self.panel.gray_ratio:.1%})",
            f"닫기(X) 버튼 빨강 비율: {self.close_ratio:.1%} "
            f"(기준 {RED_RATIO_THRESHOLD:.0%})",
            f"현재 화면: {'메인 전투화면' if self.is_battle_screen else '전투화면 아님'}",
        ]


def save_frame(frame: np.ndarray, directory: Path, name: str) -> Path | None:
    """화면 한 장을 지정한 폴더에 통째로 남긴다.

    ``save_snapshot`` 과 달리 영역 확대본을 만들지 않는다. 어디를 봐야 할지
    아직 모르는 화면을 모을 때 쓴다 — 자를 자리를 알면 이미 템플릿이 있다.

    이름에 한글이 들어간다. 저장에 실패하면 ``None`` 을 돌려줘 부르는 쪽이
    "저장했다" 고 알리지 않게 한다.
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{name}.png"
        if not imwrite(path, frame):
            return None
        return path
    except Exception:
        log.exception("화면 저장 실패: %s", name)
        return None


def save_snapshot(frame: np.ndarray, area: NormRect, prefix: str) -> Path | None:
    """전체 화면과 해당 영역 확대본을 함께 저장하고 영역 파일 경로를 반환."""
    try:
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        full_path = CAPTURE_DIR / f"{prefix}-{stamp}-full.png"
        area_path = CAPTURE_DIR / f"{prefix}-{stamp}-area.png"
        if not imwrite(full_path, frame) or not imwrite(area_path, crop(frame, area)):
            return None
        return area_path
    except Exception:
        log.exception("진단 이미지 저장 실패")
        return None
