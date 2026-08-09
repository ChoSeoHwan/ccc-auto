"""색으로 버튼을 찾는 판별기.

게임 화면 없이 돈다. 실제 화면에서 잰 값(``ccc/vision/color.py`` 주석)을
그대로 옮겨 그린 판을 쓴다 — 버튼은 색이 꽉 찬 판이고, 배경의 주황
잡동사니는 성기다는 것이 이 판별기의 전제다.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from ccc.geometry import NormRect
from ccc.vision import BUTTON_ORANGE, find_color_button

pytestmark = pytest.mark.no_frames

WIDTH, HEIGHT = 506, 898
BAND = NormRect(0.20, 0.83, 0.78, 0.10)

ORANGE = (40, 163, 245)
"""실측한 버튼 색 (BGR). HSV 로 H=18 이라 실제 버튼과 같은 색상이다."""

RED_CLOSE = (40, 95, 245)
"""하단 닫기(X) 버튼 색 (BGR). HSV 로 H=8 — 실측한 X 버튼과 같은 붉은 주황이다."""


def blank() -> np.ndarray:
    """푸른 회색 배경. 주황 범위에 들지 않는 색이면 무엇이든 된다."""
    frame = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    frame[:] = (90, 70, 60)
    return frame


def draw_button(frame: np.ndarray, x: int, y: int, w: int, h: int) -> None:
    cv2.rectangle(frame, (x, y), (x + w, y + h), ORANGE, -1)


def test_꽉_찬_판을_버튼으로_찾는다():
    frame = blank()
    draw_button(frame, 259, 768, 183, 48)  # 실측: 확인창의 '정리하기'

    rect = find_color_button(frame, BUTTON_ORANGE, BAND)

    assert rect is not None
    assert rect.center == pytest.approx((0.693, 0.882), abs=0.01)


def test_글자가_색을_끊어_놓아도_한_덩어리로_본다():
    """버튼 위의 글자와 흘러가는 띠는 색을 조각낸다. 메워서 봐야 한다."""
    frame = blank()
    draw_button(frame, 259, 768, 183, 48)
    for offset in range(0, 183, 24):  # 글자처럼 세로로 파인 자국
        cv2.rectangle(frame, (259 + offset, 776), (259 + offset + 8, 806), (90, 70, 60), -1)

    rect = find_color_button(frame, BUTTON_ORANGE, BAND)

    assert rect is not None
    assert rect.center == pytest.approx((0.693, 0.882), abs=0.01)


def test_성긴_잡동사니는_버튼으로_보지_않는다():
    """전투화면의 코인 더미는 채움 0.42~0.57 이었다. 그 아래로 만들어 확인한다."""
    frame = blank()
    for index in range(9):
        cx = 300 + (index % 3) * 30
        cy = 770 + (index // 3) * 18
        cv2.circle(frame, (cx, cy), 6, ORANGE, -1)

    assert find_color_button(frame, BUTTON_ORANGE, BAND) is None


def test_좁은_버튼은_버튼으로_보지_않는다():
    """실측 잡동사니 너비는 0.17, 버튼은 0.33 이다. 그 사이를 자른다."""
    frame = blank()
    draw_button(frame, 300, 768, 90, 48)  # 너비 0.178

    assert find_color_button(frame, BUTTON_ORANGE, BAND) is None


def test_띠_밖의_버튼은_보지_않는다():
    """같은 색 판이라도 아래쪽 띠에 없으면 이 판별기의 대상이 아니다."""
    frame = blank()
    draw_button(frame, 259, 300, 183, 48)

    assert find_color_button(frame, BUTTON_ORANGE, BAND) is None


def test_둘_이상이면_큰_쪽을_고른다():
    frame = blank()
    draw_button(frame, 110, 768, 130, 40)
    draw_button(frame, 259, 768, 183, 48)

    rect = find_color_button(frame, BUTTON_ORANGE, BAND)

    assert rect is not None
    assert rect.center[0] == pytest.approx(0.693, abs=0.01)


def test_바로_아래_닫기_버튼에_이어_붙지_않는다():
    """화면이 위로 밀리면 붉은 X 가 띠 아래끝에 걸친다.

    색상 하한이 낮으면 X 까지 같은 색으로 잡히고, 덩어리를 메우는 과정에서
    버튼과 **한 덩어리로 이어져** 경계 사각형이 부풀고 채움이 무너진다. 그러면
    버튼을 통째로 놓친다 — 실제로 그 때문에 '정리하기' 확인창 앞에서 재료
    부족으로 오진하고 자동화가 멈췄다(10:23:02).

    자리는 그때 화면에서 그대로 옮겼다. 버튼 아래끝 814, X 위끝 820 이다.
    """
    frame = blank()
    draw_button(frame, 286, 770, 176, 44)
    cv2.rectangle(frame, (248, 820), (308, 860), RED_CLOSE, -1)

    rect = find_color_button(frame, BUTTON_ORANGE, BAND)

    assert rect is not None, "X 와 이어 붙어 버튼을 놓쳤습니다"
    assert rect.h < 0.06, f"X 까지 이어 붙었습니다 (높이 {rect.h:.3f})"
    assert rect.center == pytest.approx((0.740, 0.883), abs=0.01)


def test_창_크기가_달라도_같게_찾는다():
    """정규화 기준이라 큰 창에서도 같은 자리를 돌려줘야 한다."""
    big = np.zeros((HEIGHT * 2, WIDTH * 2, 3), np.uint8)
    big[:] = (90, 70, 60)
    draw_button(big, 518, 1536, 366, 96)

    rect = find_color_button(big, BUTTON_ORANGE, BAND)

    assert rect is not None
    assert rect.center == pytest.approx((0.693, 0.882), abs=0.01)
