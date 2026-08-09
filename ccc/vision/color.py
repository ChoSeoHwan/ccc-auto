"""색 기반 간단 판정 헬퍼.

템플릿 매칭까지 갈 필요 없는 경우(버튼이 켜졌는지, 로딩 화면인지 등)에
쓰는 가벼운 도구들.
"""

from __future__ import annotations

import numpy as np

from ..geometry import NormRect, Rect


def clamped_box(frame: np.ndarray, area: NormRect) -> Rect:
    """정규화 사각형을 프레임 안에 들어오는 픽셀 사각형으로 바꾼다.

    잘라낸 조각에서 찾은 자리를 다시 화면 좌표로 되돌리려면 이 좌표가 필요하다.
    """
    height, width = frame.shape[:2]
    rect = area.scaled(width, height)
    x0 = max(0, min(rect.x, width - 1))
    y0 = max(0, min(rect.y, height - 1))
    x1 = max(x0 + 1, min(rect.right, width))
    y1 = max(y0 + 1, min(rect.bottom, height))
    return Rect(x0, y0, x1 - x0, y1 - y0)


def crop(frame: np.ndarray, area: NormRect) -> np.ndarray:
    """정규화 사각형으로 프레임 일부를 잘라낸다."""
    box = clamped_box(frame, area)
    return frame[box.y : box.bottom, box.x : box.right]


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


BUTTON_ORANGE = ((8, 150, 180), (25, 255, 255))
"""게임의 주황 확인 버튼 색 (HSV 하한/상한).

'시작', '정리 하기', '정리하기' 가 모두 이 색이다. 같은 자리에 무엇이 뜨는지는
상황마다 다른데, 어느 쪽이든 눌러야 할 버튼은 그 하나뿐이라 글자를 읽어
가릴 필요가 없다.
"""

# 버튼으로 인정할 최소 크기와 채움율.
#
# 채움율은 '경계 사각형 중 실제로 그 색인 비율' 이다. 버튼은 색이 꽉 찬 판이라
# 1 에 가깝고, 배경의 주황 잡동사니(코인 더미, 아이콘)는 성기다.
#
# 실측 (506x898 화면, 아래쪽 버튼 띠)
#     정리 하기(결과창)   169x47  채움 0.969  너비 0.334
#     정리하기(확인창)    183x48  채움 0.961  너비 0.362
#     전투화면 잡동사니   77x39   채움 0.569  너비 0.152
#     전투화면 잡동사니   86x46   채움 0.424  너비 0.170
# 버튼과 잡동사니 사이가 채움 0.57~0.96, 너비 0.17~0.33 으로 둘 다 넓게 비어
# 있다. 그 가운데를 잡았다.
#
# 버튼 위로는 하얀 띠가 계속 흘러간다. 20프레임(5초)을 재 보니 채움이
# 0.962~0.971 안에서만 움직였다 — 띠는 이 색 범위를 벗어나지 않는다.
BUTTON_MIN_WIDTH = 0.25
BUTTON_MIN_HEIGHT = 0.03
BUTTON_MIN_FILL = 0.85

_CLOSE_KERNEL_RATIO = 0.026
"""덩어리를 메울 커널 크기 (화면 너비 대비). 506px 에서 13px 이다.

글자와 테두리가 색을 끊어 놓아 그냥 두면 버튼 하나가 조각난다. 화면 크기에
비례해 잡아야 창 크기가 달라져도 같게 동작한다.
"""


def find_color_button(
    frame: np.ndarray,
    color: tuple[tuple[int, int, int], tuple[int, int, int]],
    area: NormRect | None = None,
    min_width: float = BUTTON_MIN_WIDTH,
    min_height: float = BUTTON_MIN_HEIGHT,
    min_fill: float = BUTTON_MIN_FILL,
) -> NormRect | None:
    """색으로 버튼을 찾는다. 가장 큰 것 하나를 정규화 사각형으로 돌려준다.

    글자가 아니라 판의 색을 보므로, 같은 자리에 '시작' 이 뜨든 '정리하기' 가
    뜨든 똑같이 찾힌다. 템플릿을 뜰 수 없는 화면(가끔만 나오는 확인창)에도
    쓸 수 있고, 흘러가는 띠 애니메이션에도 흔들리지 않는다.

    ``min_width``/``min_height`` 는 **화면 전체** 대비 비율이다. ``area`` 를 좁혀도
    기준이 같이 좁아지지 않는다.
    """
    import cv2

    height, width = frame.shape[:2]
    # 띠만 잘라서 본다. 전체 화면을 HSV 로 바꾸는 것이 이 함수 비용의 대부분이라
    # (실측 2.2ms → 0.2ms), 볼 곳이 정해져 있으면 잘라 놓고 시작하는 편이 낫다.
    box = clamped_box(frame, area) if area is not None else Rect(0, 0, width, height)
    patch = frame[box.y : box.bottom, box.x : box.right]
    if patch.size == 0:
        return None

    lower, upper = color
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(lower, np.uint8), np.array(upper, np.uint8))

    size = max(3, int(round(width * _CLOSE_KERNEL_RATIO)) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((size, size), np.uint8))

    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    best: NormRect | None = None
    best_area = 0
    for index in range(1, count):
        x, y, w, h, filled = stats[index]
        if w < min_width * width or h < min_height * height:
            continue
        if filled / (w * h) < min_fill:
            continue
        if w * h > best_area:
            best_area = w * h
            best = NormRect(
                (box.x + x) / width, (box.y + y) / height, w / width, h / height
            )
    return best


def is_static(previous: np.ndarray | None, current: np.ndarray, tolerance: float = 2.0) -> bool:
    """두 프레임이 사실상 같은지. 화면 전환이 끝났는지 판단할 때 쓴다."""
    if previous is None or previous.shape != current.shape:
        return False
    diff = np.abs(previous.astype(np.int16) - current.astype(np.int16))
    return float(diff.mean()) <= tolerance
