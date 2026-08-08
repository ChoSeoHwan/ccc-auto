"""화면 인식 BDD 스텝 정의."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then

from ccc.anchors import NAV_CLOSE, QUEST_PANEL
from ccc.modules.power_save import LABEL_TEMPLATE, MATCH_THRESHOLD, SEARCH_AREA
from ccc.quest.navigator import BattleScreenNavigator
from ccc.quest.panel import panel_visible
from ccc.vision import find_text

from .conftest import load_frame

scenarios("features/screen_detection.feature")


@pytest.fixture
def screen() -> dict:
    return {}


@given(parsers.parse('화면이 "{name}" 이다'), target_fixture="frame")
def given_frame(name: str):
    return load_frame(name)


@then(parsers.parse('퀘스트창 판정은 "{expected}" 이다'))
def then_panel_state(frame, anchors, expected: str):
    from ccc.quest.diagnostics import DetectionReport

    report = DetectionReport(frame, anchors)
    assert report.panel.state.value == expected, (
        f"기대 {expected}, 실제 {report.panel.state.value} ({report.panel.detail})"
    )


@then("전투화면으로 판정한다")
def then_is_battle(frame, anchors):
    navigator = BattleScreenNavigator(anchors.get(NAV_CLOSE))
    assert navigator.is_battle_screen(frame), (
        f"닫기 버튼 빨강 비율 {navigator.close_button_ratio(frame):.1%}"
    )


@then("전투화면이 아니라고 판정한다")
def then_is_not_battle(frame, anchors):
    navigator = BattleScreenNavigator(anchors.get(NAV_CLOSE))
    assert not navigator.is_battle_screen(frame), (
        f"닫기 버튼 빨강 비율 {navigator.close_button_ratio(frame):.1%}"
    )


@then("절전 모드로 판정한다")
def then_power_save(frame, templates):
    match = find_text(frame, templates.load(LABEL_TEMPLATE), MATCH_THRESHOLD, SEARCH_AREA)
    assert match is not None, "'더 절전 모드' 라벨을 찾지 못했습니다"


@then("퀘스트창이 보이지 않는다고 판정한다")
def then_panel_hidden(frame, anchors):
    from ccc.quest.panel import panel_text_ratio

    area = anchors.get(QUEST_PANEL)
    assert not panel_visible(frame, area), (
        f"글자 비율 {panel_text_ratio(frame, area):.1%} 로 보인다고 판정했습니다"
    )


@then(parsers.parse('"{template}" 글자를 퀘스트창에서 찾는다'))
def then_find_text_in_panel(frame, anchors, templates, template: str):
    match = find_text(frame, templates.load(template), 0.7, anchors.get(QUEST_PANEL))
    assert match is not None, f"'{template}' 을 찾지 못했습니다"
