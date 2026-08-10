"""오븐 레벨업 마무리.

확인창의 '레벨업' 은 '정리하기' 와 **똑같은 주황 버튼**이다. 확인창을 못
알아본 판에서는 색으로 찾는 쪽이 대신 눌러 버리고, 그러면 오븐 레벨 화면까지
갔는데 아무도 마무리를 하지 않아 네비게이터가 X 로 닫는다. 레벨업은 영영 안 된다.

그래서 '확인창을 눌렀으니 다음은 성장' 이라는 순서에 기대지 않는다. 성장
버튼이 화면에 있으면 그것만으로 누를 이유가 된다.

게임 화면 없이 돈다. 두 조각을 알아보는 일은 실제 화면으로 따로 쟀고
(확인창 0.848 / 나머지 0.24~0.48, 성장 0.97~1.00 / 나머지 0.31~0.37),
여기서 보는 것은 **무엇을 먼저 보느냐** 다.
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
from ccc.quests.oven_equipment_draw import OvenEquipmentDraw
from ccc.vision import TemplateStore

from .conftest import DEVICE, TEMPLATE_DIR, FakeAdbClient

pytestmark = pytest.mark.no_frames

WIDTH, HEIGHT = 379, 674
ORANGE = (40, 163, 245)
BUTTON = (110, 578, 130, 34)
"""주황 버튼 자리. 확인창의 '레벨업' 도 '정리하기' 도 이 띠에 앉는다."""


def frame_with_button() -> np.ndarray:
    image = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    image[:] = (30, 30, 30)
    x, y, w, h = BUTTON
    cv2.rectangle(image, (x, y), (x + w, y + h), ORANGE, -1)
    return image


class Screen:
    def __init__(self, image: np.ndarray):
        self.image = image

    def grab(self) -> np.ndarray:
        return self.image


def build(image: np.ndarray) -> tuple[Context, FakeAdbClient]:
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
    ctx.sleep = lambda seconds: True  # type: ignore[method-assign]
    ctx.wait_until = lambda condition, timeout, interval=0.0, first_delay=0.0: bool(  # type: ignore[method-assign]
        condition(ctx.refresh())
    )
    return ctx, client


def button_area() -> NormRect:
    x, y, w, h = BUTTON
    return NormRect(x / WIDTH, y / HEIGHT, w / WIDTH, h / HEIGHT)


def tapped_button(client: FakeAdbClient) -> bool:
    area = button_area()
    for x, y in client.taps:
        nx, ny = x / (DEVICE.width - 1), y / (DEVICE.height - 1)
        if area.x <= nx <= area.x + area.w and area.y <= ny <= area.y + area.h:
            return True
    return False


def quest(monkeypatch, *, grow: bool) -> OvenEquipmentDraw:
    q = OvenEquipmentDraw()
    # 확인창은 못 알아본 상황을 본다 — 그래야 색으로 찾는 쪽과 겨룬다.
    monkeypatch.setattr(q, "_take_levelup_offer", lambda ctx: False)
    monkeypatch.setattr(q, "_grow_oven", lambda ctx, timeout=0.0: grow)
    return q


def test_성장_버튼이_보이면_주황_버튼보다_먼저_누른다(monkeypatch):
    ctx, client = build(frame_with_button())

    result = quest(monkeypatch, grow=True)._dismiss_results(ctx)

    assert result.success
    assert not tapped_button(client), f"주황 버튼을 눌렀습니다: {client.taps}"


def test_성장_버튼이_없으면_주황_버튼을_누른다(monkeypatch):
    """평소에는 그 자리의 주황 버튼이 눌러야 할 것 맞다."""
    ctx, client = build(frame_with_button())

    quest(monkeypatch, grow=False)._dismiss_results(ctx)

    assert tapped_button(client), f"누르지 않았습니다: {client.taps}"
