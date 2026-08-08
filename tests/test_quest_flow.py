"""퀘스트 자동화 상태 흐름 BDD 스텝 정의."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ccc.anchors import NAV_CLOSE, QUEST_PANEL, QUEST_PANEL_SAMPLE, SAFE_TAP
from ccc.geometry import NormRect
from ccc.notify import Notifier
from ccc.quest import (
    BattleScreenNavigator,
    QuestMachine,
    QuestPanelReader,
    QuestRegistry,
    StablePanelReader,
)

from .conftest import make_context

scenarios("features/quest_flow.feature")


class RecordingNotifier(Notifier):
    """실제로 알림을 띄우지 않고 문구만 모아 둔다."""

    def __init__(self) -> None:
        super().__init__(enabled=False)
        self.messages: list[str] = []

    def send(self, message: str, title: str = "") -> None:
        self.messages.append(message)


@pytest.fixture(autouse=True)
def no_snapshot(monkeypatch):
    """테스트가 captures/ 에 진단 이미지를 남기지 않게 한다."""
    monkeypatch.setattr("ccc.quest.machine.save_snapshot", lambda *a, **k: None)


# ----------------------------------------------------------------------
# 조건
# ----------------------------------------------------------------------
class FakeClock:
    """테스트가 시간을 직접 돌리기 위한 시계.

    '1분 동안 계속 못 알아보면 멈춘다' 같은 규칙을 실제로 1분 기다리며
    확인할 수는 없다.
    """

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@given(parsers.parse("화면이 순서대로 {names} 이다"), target_fixture="world")
def given_frames(names: str, no_sleep, anchors):
    frame_names = [part.strip().strip('"') for part in names.split(",")]
    # 상태기 테스트는 엔진처럼 매 tick 마다 바깥에서 프레임을 넣으므로 미리 소비하지 않는다.
    ctx, client, screen = make_context(frame_names, prime=False)
    notifier = RecordingNotifier()
    clock = FakeClock()
    machine = QuestMachine(
        StablePanelReader(
            QuestPanelReader(
                anchors.get(QUEST_PANEL_SAMPLE), panel_area=anchors.get(QUEST_PANEL)
            ),
            required=2,
        ),
        BattleScreenNavigator(anchors.get(NAV_CLOSE)),
        QuestRegistry(),
        anchors.get(QUEST_PANEL),
        anchors.get(SAFE_TAP),
        notifier,
        clock=clock,
    )
    return {
        "ctx": ctx,
        "client": client,
        "screen": screen,
        "machine": machine,
        "notifier": notifier,
        "anchors": anchors,
        "clock": clock,
    }


@given("상태기가 대기 상태이다")
def given_idle(world):
    world["machine"].to_idle()


@given("자동화를 시작한다")
def given_started(world):
    world["machine"].start()


@given("등록된 퀘스트가 없다")
def given_no_quests(world):
    world["machine"]._registry.definitions = []


# ----------------------------------------------------------------------
# 행동
# ----------------------------------------------------------------------
@when("한 걸음 진행하면")
def when_one_step(world):
    _step(world, 1)


@when(parsers.parse("{count:d} 걸음 진행하면"))
def when_steps(world, count: int):
    _step(world, count)


@when(parsers.parse("{seconds:d} 초가 흐르면"))
def when_time_passes(world, seconds: int):
    world["clock"].advance(seconds)


def _step(world, count: int) -> None:
    machine, ctx, screen = world["machine"], world["ctx"], world["screen"]
    for _ in range(count):
        ctx.set_frame(screen.grab())
        machine.tick(ctx)


# ----------------------------------------------------------------------
# 결과
# ----------------------------------------------------------------------
@then(parsers.parse('상태는 "{expected}" 이다'))
def then_state(world, expected: str):
    actual = world["machine"].state.value
    assert actual == expected, f"기대 {expected}, 실제 {actual}"


@then("아무것도 누르지 않는다")
def then_no_tap(world):
    assert not world["client"].taps, f"눌렀습니다: {world['client'].taps}"


@then("퀘스트창을 누른다")
def then_tapped_panel(world):
    _assert_tapped_in(world, world["anchors"].get(QUEST_PANEL), "퀘스트창")


@then("닫기 버튼을 누른다")
def then_tapped_close(world):
    _assert_tapped_in(world, world["anchors"].get(NAV_CLOSE), "닫기 버튼")


@then("빈 곳 탭 지점을 누른다")
def then_tapped_safe(world):
    _assert_tapped_in(world, world["anchors"].get(SAFE_TAP), "빈 곳 탭 지점")


@then("사용자에게 알린다")
def then_notified(world):
    assert world["notifier"].messages, "알림이 없습니다"


@then("사용자에게 알리지 않는다")
def then_not_notified(world):
    assert not world["notifier"].messages, f"알림이 갔습니다: {world['notifier'].messages}"


# ----------------------------------------------------------------------
def _assert_tapped_in(world, area: NormRect, label: str) -> None:
    device = world["client"].device
    for x, y in world["client"].taps:
        nx, ny = x / (device.width - 1), y / (device.height - 1)
        if area.x <= nx <= area.x + area.w and area.y <= ny <= area.y + area.h:
            return
    pytest.fail(f"{label} 를 누르지 않았습니다. 실제 탭: {world['client'].taps}")
