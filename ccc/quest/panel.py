"""퀘스트창 판독.

퀘스트창은 화면 오른쪽 끝에 붙어 있고, 완료되면 황금색 / 진행 중이면
회색이다. 반투명이라 뒤의 전투 배경이 비치는데, 스테이지에 따라 배경이
주황 계열이면 황금색과 색상이 겹친다. 그래서 고정 임계값 하나로 자르지
않고, 두 색군의 픽셀 비율을 각각 구해 **더 우세한 쪽**을 고른다. 어느
쪽도 뚜렷하지 않으면 판정불가로 두고 다음 프레임에서 다시 본다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from ..geometry import NormRect
from .states import PanelState

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HsvRange:
    """OpenCV HSV 범위 (H 0~179, S/V 0~255)."""

    h: tuple[int, int]
    s: tuple[int, int]
    v: tuple[int, int]

    @property
    def lower(self) -> np.ndarray:
        return np.array([self.h[0], self.s[0], self.v[0]], np.uint8)

    @property
    def upper(self) -> np.ndarray:
        return np.array([self.h[1], self.s[1], self.v[1]], np.uint8)


# 황금색: 노랑~주황 색상에 채도·명도가 모두 높다.
GOLD_RANGE = HsvRange(h=(10, 40), s=(110, 255), v=(130, 255))
# 회색: 색상은 상관없고 채도가 낮다. 너무 어두운 그림자는 제외한다.
#
# 채도 상한은 85 가 아니라 120 이다. 퀘스트창이 반투명이라 뒤 배경이 비쳐 들면
# 표본 전체의 채도가 올라간다. 배경이 갈색 벽일 때 85 로는 회색 비율이 0.059
# 까지 떨어져 판정불가가 되고, 그러면 판별 단계에 가 보지도 못한 채 자동화가
# 멈춘다. 120 으로 올리면 같은 프레임이 0.668 로 읽힌다.
#
# 황금과 겹치지 않는다. 황금은 채도 110 이상 + 색상 10~40 이라 조건이 더 좁고,
# 실측으로도 완료 프레임의 회색 비율은 0.011 에 그친다 (황금 0.943).
GRAY_RANGE = HsvRange(h=(0, 179), s=(0, 120), v=(45, 225))

MIN_RATIO = 0.15
"""우세한 쪽이 최소한 이 정도는 차지해야 판정한다."""

MIN_MARGIN = 1.5
"""우세한 쪽이 반대쪽보다 이 배수 이상이어야 판정한다."""

MIN_TEXT_RATIO = 0.025
"""퀘스트창이 화면에 있다고 보려면 그 영역에 이만큼은 흰 글씨가 있어야 한다.

회색은 '채도가 낮다' 로 정의돼 있어서, 절전 모드처럼 채도가 낮기만 한 화면도
퀘스트창으로 오인할 수 있다. 퀘스트창에는 항상 퀘스트 이름과 '0/15' 같은
진행도가 흰 글씨로 찍히므로, 색을 보기 전에 글씨부터 확인한다.

실측 분포 (프레임 15장)
    퀘스트창 있음   0.035 ~ 0.080
    장비 비교 팝업  0.014      ← 팝업의 흰 글씨가 그 자리에 겹친다
    절전 모드       0.004
    게임 꺼짐       0.000
비어 있는 구간 한가운데를 잡아 양쪽으로 1.7배 이상 여유를 둔다.
"""


@dataclass(frozen=True)
class PanelReading:
    """한 프레임에서 읽어 낸 퀘스트창 상태."""

    state: PanelState
    gold_ratio: float
    gray_ratio: float
    text_ratio: float = 1.0
    """퀘스트창 영역의 흰 글씨 비율. 창이 화면에 있는지 가리는 데 쓴다."""

    @property
    def has_panel(self) -> bool:
        return self.text_ratio >= MIN_TEXT_RATIO

    @property
    def detail(self) -> str:
        if not self.has_panel:
            return f"퀘스트창 없음 (글자 {self.text_ratio:.1%})"
        return f"금 {self.gold_ratio:.0%} / 회 {self.gray_ratio:.0%}"


class QuestPanelReader:
    """퀘스트창의 색 표본을 읽어 완료/진행중을 가린다."""

    def __init__(
        self,
        sample_area: NormRect,
        panel_area: NormRect | None = None,
        gold: HsvRange = GOLD_RANGE,
        gray: HsvRange = GRAY_RANGE,
        min_ratio: float = MIN_RATIO,
        min_margin: float = MIN_MARGIN,
        min_text_ratio: float = MIN_TEXT_RATIO,
    ):
        self.sample_area = sample_area
        self.panel_area = panel_area
        self.gold = gold
        self.gray = gray
        self.min_ratio = min_ratio
        self.min_margin = min_margin
        self.min_text_ratio = min_text_ratio

    def read(self, frame: np.ndarray) -> PanelReading:
        import cv2

        from ..vision import crop

        patch = crop(frame, self.sample_area)
        if patch.size == 0:
            return PanelReading(PanelState.UNKNOWN, 0.0, 0.0, 0.0)

        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        gold_ratio = _ratio(hsv, self.gold)
        gray_ratio = _ratio(hsv, self.gray)

        text_ratio = self._text_ratio(frame)
        if text_ratio < self.min_text_ratio:
            # 퀘스트창 자체가 화면에 없다. 색만 보면 오판하므로 여기서 끊는다.
            return PanelReading(PanelState.UNKNOWN, gold_ratio, gray_ratio, text_ratio)

        return PanelReading(
            self._classify(gold_ratio, gray_ratio), gold_ratio, gray_ratio, text_ratio
        )

    def _text_ratio(self, frame: np.ndarray) -> float:
        if self.panel_area is None:
            return 1.0  # 영역을 안 받았으면 검사를 건너뛴다
        return panel_text_ratio(frame, self.panel_area)

    def _classify(self, gold_ratio: float, gray_ratio: float) -> PanelState:
        winner, loser = (
            (PanelState.GOLD, gray_ratio)
            if gold_ratio >= gray_ratio
            else (PanelState.GRAY, gold_ratio)
        )
        top = max(gold_ratio, gray_ratio)
        if top < self.min_ratio:
            return PanelState.UNKNOWN
        if loser > 0 and top / loser < self.min_margin:
            return PanelState.UNKNOWN
        return winner


def panel_text_ratio(frame: np.ndarray, panel_area: NormRect) -> float:
    """퀘스트창 영역에서 흰 글씨가 차지하는 비율."""
    from ..vision import crop, text_mask

    patch = crop(frame, panel_area)
    if patch.size == 0:
        return 0.0
    mask = text_mask(patch)
    return float(np.count_nonzero(mask)) / mask.size


def panel_visible(
    frame: np.ndarray, panel_area: NormRect, min_text_ratio: float = MIN_TEXT_RATIO
) -> bool:
    """퀘스트창이 화면에 보이는지. 연출이나 팝업에 가려졌는지 판별할 때 쓴다."""
    return panel_text_ratio(frame, panel_area) >= min_text_ratio


def _ratio(hsv: np.ndarray, rng: HsvRange) -> float:
    import cv2

    mask = cv2.inRange(hsv, rng.lower, rng.upper)
    return float(np.count_nonzero(mask)) / mask.size


class StablePanelReader:
    """연속 여러 프레임이 같은 값일 때만 확정하는 래퍼.

    완료 패널에는 밝은 띠가 지나다니고 전투 배경도 계속 움직이므로,
    한 프레임만 보고 상태를 바꾸면 튄다.
    """

    def __init__(self, reader: QuestPanelReader, required: int = 2):
        self.reader = reader
        self.required = max(1, required)
        self._last = PanelState.UNKNOWN
        self._count = 0

    def read(self, frame: np.ndarray) -> PanelReading:
        reading = self.reader.read(frame)
        if reading.state == self._last:
            self._count += 1
        else:
            self._last = reading.state
            self._count = 1

        if self._count < self.required:
            return PanelReading(
                PanelState.UNKNOWN,
                reading.gold_ratio,
                reading.gray_ratio,
                reading.text_ratio,
            )
        return reading

    def reset(self) -> None:
        self._last = PanelState.UNKNOWN
        self._count = 0
