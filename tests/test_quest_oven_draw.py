"""퀘스트 '오븐에서 장비 뽑기' BDD.

공통 스텝은 conftest 에 있고, 여기에는 이 퀘스트에만 해당하는 것만 둔다.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios, then

from ccc.geometry import NormRect
from ccc.quests.oven_equipment_draw import (
    AUTO_SEARCH,
    AUTO_TEMPLATE,
    BUTTON_BAND,
    OvenEquipmentDraw,
)
from ccc.vision import BUTTON_ORANGE

from .conftest import color_button_area, inside, tap_normalized, template_area

scenarios("features/quest_oven_draw.feature")

EQUIP_SELL_ZONE = NormRect(0.50, 0.65, 0.42, 0.07)
"""장비 비교 팝업의 '장착 / 판매' 버튼이 놓인 자리. 여기는 절대 누르면 안 된다."""


@pytest.fixture
def quest() -> OvenEquipmentDraw:
    return OvenEquipmentDraw()


@pytest.fixture
def tap_targets(anchors) -> dict:
    return {
        "Auto 버튼": template_area("battle_gray_oven", AUTO_TEMPLATE, AUTO_SEARCH, 0.80),
        "시작 버튼": color_button_area("auto_open_popup", BUTTON_ORANGE, BUTTON_BAND),
        "정리 하기 버튼": color_button_area("equipment_full_list", BUTTON_ORANGE, BUTTON_BAND),
        "정리하기 확인 버튼": color_button_area(
            "equipment_full_confirm", BUTTON_ORANGE, BUTTON_BAND
        ),
        "빈 곳 탭 지점": lambda: anchors.get("safe_tap"),
    }


@then("장착 버튼과 판매 버튼을 누르지 않는다")
def then_never_equip_or_sell(world):
    for index in range(1, len(world["client"].taps) + 1):
        x, y = tap_normalized(world, index)
        assert not inside(EQUIP_SELL_ZONE, x, y), (
            f"{index}번째 탭 ({x:.3f}, {y:.3f}) 이 장착/판매 버튼 위입니다"
        )
