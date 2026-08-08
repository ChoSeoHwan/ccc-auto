"""퀘스트 '쿠키 뽑기' BDD.

공통 스텝은 conftest 에 있고, 여기에는 이 퀘스트에만 해당하는 것만 둔다.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios

from ccc.anchors import QUEST_PANEL
from ccc.quests._gacha import DRAW_SEARCH, DRAW_THRESHOLD
from ccc.quests.cookie_draw import CookieDraw

from .conftest import template_area

scenarios("features/quest_cookie_draw.feature")


@pytest.fixture
def quest() -> CookieDraw:
    return CookieDraw()


@pytest.fixture
def tap_targets(anchors) -> dict:
    return {
        "퀘스트창": lambda: anchors.get(QUEST_PANEL),
        "10회 버튼": template_area(
            "gacha_screen", CookieDraw.draw_template, DRAW_SEARCH, DRAW_THRESHOLD
        ),
    }
