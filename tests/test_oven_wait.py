"""Auto 버튼을 기다리는 동안 가리고 있는 팝업을 치운다.

장비가 가득 차면 정리하기 팝업이 오븐과 퀘스트창을 **함께** 가린다. 그러면
Auto 버튼도 완료도 영영 보이지 않아, 치울 수 있는 화면을 앞에 두고 30초를
통째로 버린다.

게임 화면 없이 돈다. Auto 버튼 찾기는 템플릿이 필요하므로 '못 찾음' 으로
바꿔 끼운다 — 여기서 보려는 것은 못 찾았을 때 무엇을 하느냐다.
"""

from __future__ import annotations

import threading

import cv2
import numpy as np
import pytest

from ccc.anchors import AnchorSet
from ccc.context import Context
from ccc.geometry import NormRect
from ccc.notify import Notifier
from ccc.quests.oven_equipment_draw import MAX_TIDY_TAPS, OvenEquipmentDraw
from ccc.vision import TemplateStore

from .conftest import DEVICE, TEMPLATE_DIR, FakeAdbClient

pytestmark = pytest.mark.no_frames

WIDTH, HEIGHT = 506, 898
ORANGE = (40, 163, 245)
"""실측한 버튼 색 (BGR). HSV 로 H=18."""

BUTTON = (286, 770, 176, 44)
"""막혔던 화면에서 그대로 옮긴 '정리하기' 버튼 자리."""


def frame(*, tidy_popup: bool) -> np.ndarray:
    """어두운 화면. 퀘스트창도 Auto 도 안 보이고, 팝업만 있고 없고가 다르다."""
    image = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    image[:] = (30, 30, 30)
    if tidy_popup:
        x, y, w, h = BUTTON
        cv2.rectangle(image, (x, y), (x + w, y + h), ORANGE, -1)
    return image


class Screen:
    def __init__(self, image: np.ndarray):
        self.image = image

    def grab(self) -> np.ndarray:
        return self.image


def build(image: np.ndarray, polls: int) -> tuple[Context, FakeAdbClient]:
    client = FakeAdbClient()
    ctx = Context(
        client,  # type: ignore[arg-type]
        TemplateStore(TEMPLATE_DIR),
        threading.Event(),
        anchors=AnchorSet(),
        notifier=Notifier(enabled=False),
        frame_provider=Screen(image).grab,
    )
    ctx.set_frame(image)
    # Auto 버튼은 늘 '못 찾음'. 기다리는 동안 무엇을 하는지가 이 테스트의 관심사다.
    ctx.find = lambda *a, **k: None  # type: ignore[method-assign]
    # 기다림은 정해진 횟수만 돌린다. 실제 시계를 태울 이유가 없다.
    ctx.wait_until = lambda condition, timeout, interval=0.0, first_delay=0.0: any(  # type: ignore[method-assign]
        condition(ctx.refresh()) for _ in range(polls)
    )
    return ctx, client


def taps_in(client: FakeAdbClient, area: NormRect) -> int:
    count = 0
    for x, y in client.taps:
        nx, ny = x / (DEVICE.width - 1), y / (DEVICE.height - 1)
        if area.x <= nx <= area.x + area.w and area.y <= ny <= area.y + area.h:
            count += 1
    return count


def button_area() -> NormRect:
    x, y, w, h = BUTTON
    return NormRect(x / WIDTH, y / HEIGHT, w / WIDTH, h / HEIGHT)


def test_가리고_있는_정리하기_팝업을_누른다():
    ctx, client = build(frame(tidy_popup=True), polls=1)

    OvenEquipmentDraw()._wait_for_auto(ctx)

    assert taps_in(client, button_area()) == 1, f"누르지 않았습니다: {client.taps}"


def test_팝업이_없으면_아무것도_누르지_않는다():
    """빈 화면을 기다릴 때 화면을 건드리면 엉뚱한 것이 눌린다."""
    ctx, client = build(frame(tidy_popup=False), polls=3)

    OvenEquipmentDraw()._wait_for_auto(ctx)

    assert not client.taps, f"눌렀습니다: {client.taps}"


def test_같은_팝업을_끝없이_두드리지_않는다():
    """눌러도 안 치워지는 화면일 수 있다. 상한을 넘기면 그냥 기다린다."""
    ctx, client = build(frame(tidy_popup=True), polls=MAX_TIDY_TAPS + 5)

    OvenEquipmentDraw()._wait_for_auto(ctx)

    assert taps_in(client, button_area()) == MAX_TIDY_TAPS


def test_기다림의_결과는_못_찾음_그대로다():
    """팝업을 치운 것과 Auto 를 찾은 것은 다르다. 섞이면 없는 버튼을 누른다."""
    ctx, _ = build(frame(tidy_popup=True), polls=2)

    match, completed = OvenEquipmentDraw()._wait_for_auto(ctx)

    assert match is None
    assert completed is False
