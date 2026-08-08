"""퀘스트 '가방에서 상자 사용하기' BDD.

공통 스텝은 conftest 에 있고, 여기에는 이 퀘스트에만 해당하는 것만 둔다.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios

from ccc.anchors import QUEST_PANEL
from ccc.quests.use_box_from_bag import (
    BAG_GRID,
    BOX_TEMPLATE,
    MATCH_THRESHOLD,
    USE_SEARCH,
    USE_TEMPLATE,
    UseBoxFromBag,
)

from .conftest import template_area

scenarios("features/quest_use_box.feature")


@pytest.fixture
def quest() -> UseBoxFromBag:
    return UseBoxFromBag()


@pytest.fixture
def tap_targets(anchors) -> dict:
    return {
        "퀘스트창": lambda: anchors.get(QUEST_PANEL),
        "보물상자": template_area("bag_open", BOX_TEMPLATE, BAG_GRID, MATCH_THRESHOLD),
        "사용하기 버튼": template_area(
            "bag_item_detail", USE_TEMPLATE, USE_SEARCH, MATCH_THRESHOLD
        ),
    }
