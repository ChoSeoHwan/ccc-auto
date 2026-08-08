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
from ..vision import crop
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


def save_snapshot(frame: np.ndarray, area: NormRect, prefix: str) -> Path | None:
    """전체 화면과 해당 영역 확대본을 함께 저장하고 영역 파일 경로를 반환."""
    import cv2

    try:
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        full_path = CAPTURE_DIR / f"{prefix}-{stamp}-full.png"
        area_path = CAPTURE_DIR / f"{prefix}-{stamp}-area.png"
        cv2.imwrite(str(full_path), frame)
        cv2.imwrite(str(area_path), crop(frame, area))
        return area_path
    except Exception:
        log.exception("진단 이미지 저장 실패")
        return None
