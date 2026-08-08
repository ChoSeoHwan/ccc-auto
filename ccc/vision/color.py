"""색 기반 간단 판정 헬퍼.

템플릿 매칭까지 갈 필요 없는 경우(버튼이 켜졌는지, 로딩 화면인지 등)에
쓰는 가벼운 도구들.
"""

from __future__ import annotations

import numpy as np

from ..geometry import NormRect


def crop(frame: np.ndarray, area: NormRect) -> np.ndarray:
    """정규화 사각형으로 프레임 일부를 잘라낸다."""
    height, width = frame.shape[:2]
    rect = area.scaled(width, height)
    x0 = max(0, min(rect.x, width - 1))
    y0 = max(0, min(rect.y, height - 1))
    x1 = max(x0 + 1, min(rect.right, width))
    y1 = max(y0 + 1, min(rect.bottom, height))
    return frame[y0:y1, x0:x1]


def mean_color(frame: np.ndarray, area: NormRect | None = None) -> tuple[int, int, int]:
    """영역 평균 색 (B, G, R)."""
    patch = crop(frame, area) if area else frame
    mean = patch.reshape(-1, 3).mean(axis=0)
    return int(mean[0]), int(mean[1]), int(mean[2])


def brightness(frame: np.ndarray, area: NormRect | None = None) -> float:
    """영역 평균 밝기 0~255. 로딩/암전 화면 판별에 쓴다."""
    patch = crop(frame, area) if area else frame
    return float(patch.mean())


def color_ratio(
    frame: np.ndarray,
    lower: tuple[int, int, int],
    upper: tuple[int, int, int],
    area: NormRect | None = None,
) -> float:
    """HSV 범위 안에 드는 픽셀 비율 0.0~1.0."""
    import cv2

    patch = crop(frame, area) if area else frame
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(lower, np.uint8), np.array(upper, np.uint8))
    return float(np.count_nonzero(mask)) / mask.size


def is_static(previous: np.ndarray | None, current: np.ndarray, tolerance: float = 2.0) -> bool:
    """두 프레임이 사실상 같은지. 화면 전환이 끝났는지 판단할 때 쓴다."""
    if previous is None or previous.shape != current.shape:
        return False
    diff = np.abs(previous.astype(np.int16) - current.astype(np.int16))
    return float(diff.mean()) <= tolerance
