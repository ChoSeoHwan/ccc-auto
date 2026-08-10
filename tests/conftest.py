"""테스트 공용 도구.

실제 게임 없이 검증하기 위해, 저장해 둔 화면(``fixtures/frames``)을 순서대로
흘려 주고 입력은 기록만 하는 가짜 환경을 만든다. ADB 만 가짜고 좌표 변환 ·
템플릿 매칭 · 상태 전이는 전부 실제 코드가 돈다.

픽스처는 실제 캡처를 절반(540x960)으로 줄인 것이다. 모든 인식이 비율
기반이라 원본 해상도와 동일하게 동작하며, 그 자체가 해상도 무관 동작의
증거이기도 하다.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pytest
from pytest_bdd import given, parsers, then, when

from ccc.adb.client import DeviceInfo
from ccc.anchors import QUEST_PANEL, AnchorSet
from ccc.config import FIXTURE_DIR, TEMPLATE_DIR
from ccc.context import Context
from ccc.geometry import NormRect
from ccc.notify import Notifier
from ccc.vision import TemplateStore, imread

FRAME_DIR = FIXTURE_DIR

DEVICE = DeviceInfo("test:5555", 1080, 1920, "TEST")
"""픽스처는 절반 크기지만 디바이스는 원본 해상도로 둔다.

정규화 좌표가 프레임 크기와 무관하게 디바이스 좌표로 옮겨지는지도 같이
검증하기 위해서다.
"""


SETUP_HINT = (
    f"테스트용 게임 화면이 없습니다 ({FRAME_DIR}).\n"
    "게임 화면 이미지는 저작물이라 저장소에 넣지 않습니다. "
    "직접 채우려면 'python3 tools/dev.py shot' 으로 화면을 찍어 그 폴더에 두세요."
)


def has_frames() -> bool:
    return FRAME_DIR.is_dir() and any(FRAME_DIR.glob("*.png"))


def pytest_collection_modifyitems(config, items):
    """픽스처가 없으면 화면이 필요한 테스트를 건너뛴다.

    저장소를 갓 받은 사람도 `pytest` 가 빨간불 없이 돌아야 한다.
    ``no_frames`` 를 단 테스트는 스스로 화면을 만들어 쓰므로 그대로 돌린다.
    """
    if has_frames():
        return
    skip = pytest.mark.skip(reason=SETUP_HINT)
    for item in items:
        if item.get_closest_marker("no_frames") is None:
            item.add_marker(skip)


def load_frame(name: str) -> np.ndarray:
    path = FRAME_DIR / f"{name}.png"
    frame = imread(path)
    if frame is None:
        raise FileNotFoundError(f"픽스처 화면이 없습니다: {path}\n{SETUP_HINT}")
    return frame


class FakeAdbClient:
    """입력을 실제로 보내지 않고 기록만 하는 ADB 클라이언트."""

    def __init__(self) -> None:
        self.device = DEVICE
        self.dry_run = False
        self.taps: list[tuple[int, int]] = []
        self.swipes: list[tuple[int, int, int, int, int]] = []
        self.keys: list[str] = []
        self.launched: list[str] = []
        self.package = "com.devsisters.cc"

    def tap(self, x: int, y: int) -> None:
        self.taps.append((x, y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self.swipes.append((x1, y1, x2, y2, duration_ms))

    def long_press(self, x: int, y: int, duration_ms: int = 800) -> None:
        self.swipe(x, y, x, y, duration_ms)

    def keyevent(self, key: str) -> None:
        self.keys.append(str(key))

    def back(self) -> None:
        self.keyevent("KEYCODE_BACK")

    def current_package(self) -> str:
        return self.package

    def launch_app(self, package: str) -> None:
        self.launched.append(package)
        self.package = package

    def refresh_device(self) -> DeviceInfo:
        return self.device


class ScriptedScreen:
    """정해진 순서대로 화면을 흘려 주는 가짜 화면.

    ``refresh()`` 가 불릴 때마다 다음 화면으로 넘어가고, 목록이 끝나면
    마지막 화면을 계속 돌려준다.
    """

    def __init__(self, frame_names: list[str]):
        if not frame_names:
            raise ValueError("화면을 하나 이상 지정하세요.")
        self.names = list(frame_names)
        self.index = 0
        self.grabs = 0

    def grab(self) -> np.ndarray:
        self.grabs += 1
        frame = load_frame(self.names[min(self.index, len(self.names) - 1)])
        self.index += 1
        return frame

    @property
    def current_name(self) -> str:
        return self.names[min(self.index, len(self.names) - 1)]


def make_context(
    frame_names: list[str], prime: bool = True
) -> tuple[Context, FakeAdbClient, ScriptedScreen]:
    """가짜 ADB + 정해진 화면 순서로 실행 컨텍스트를 만든다.

    ``prime`` 은 첫 화면을 미리 컨텍스트에 넣을지 정한다. 퀘스트 수행처럼
    스스로 ``refresh()`` 를 부르는 쪽은 True 로 두고, 엔진처럼 매 tick 마다
    바깥에서 프레임을 넣어 주는 쪽은 False 로 둔다.
    """
    client = FakeAdbClient()
    screen = ScriptedScreen(frame_names)
    ctx = Context(
        client,  # type: ignore[arg-type]
        TemplateStore(TEMPLATE_DIR),
        threading.Event(),
        anchors=AnchorSet(),
        notifier=Notifier(enabled=False),
        frame_provider=screen.grab,
    )
    if prime:
        ctx.set_frame(screen.grab())
    return ctx, client, screen


# ----------------------------------------------------------------------
# pytest 픽스처
# ----------------------------------------------------------------------
@pytest.fixture
def anchors() -> AnchorSet:
    return AnchorSet()


@pytest.fixture
def templates() -> TemplateStore:
    return TemplateStore(TEMPLATE_DIR)


_FAST_WAIT_POLLS = 10
"""가짜 대기가 조건을 몇 번까지 다시 볼지. 정해진 화면 순서를 소화할 만큼."""


@pytest.fixture
def no_sleep(monkeypatch):
    """대기를 건너뛴다. 테스트가 실제 시간을 기다릴 이유가 없다.

    ``sleep`` 만 무력화하면 ``wait_until`` 이 실제 시계로 제한 시간을 다 태운다.
    조건은 그대로 확인하되 시간만 건너뛰도록 함께 갈아끼운다.
    """

    def fast_wait_until(self, condition, timeout, interval=0.0, first_delay=0.0):
        return any(condition(self.refresh()) for _ in range(_FAST_WAIT_POLLS))

    monkeypatch.setattr(Context, "sleep", lambda self, seconds: True)
    monkeypatch.setattr(Context, "wait_until", fast_wait_until)


# ----------------------------------------------------------------------
# 퀘스트 공용 스텝
#
# 퀘스트마다 절차는 다르지만 "화면을 순서대로 흘리고, 수행하고, 어디를 몇 번
# 눌렀는지 본다" 는 뼈대는 같다. 그 부분만 여기 모아 두고, 어느 버튼을 눌러야
# 하는지 같은 퀘스트별 내용은 각 테스트 모듈이 tap_targets 로 알려 준다.
# ----------------------------------------------------------------------
@given(parsers.parse('화면이 "{name}" 이다'), target_fixture="frame")
def given_single_frame(name: str):
    return load_frame(name)


@given(parsers.parse("화면이 순서대로 {names} 이다"), target_fixture="world")
def given_frame_sequence(names: str, no_sleep):
    frame_names = [part.strip().strip('"') for part in names.split(",")]
    ctx, client, screen = make_context(frame_names)
    return {"ctx": ctx, "client": client, "screen": screen}


@when("퀘스트를 수행하면")
def when_execute(world, quest):
    world["result"] = quest.execute(world["ctx"])


@then(parsers.re(r'"(?P<label>[^"]+)" 퀘스트로 판별한다'))
def then_identified(frame, anchors, label: str, quest):
    ctx, _client, _screen = make_context(["battle_gold"])
    ctx.set_frame(frame)
    assert quest.label == label, f"이름이 다릅니다: {quest.label}"
    assert quest.matches(ctx, anchors.get(QUEST_PANEL)), "판별에 실패했습니다"


@then(parsers.re(r'"(?P<label>[^"]+)" 퀘스트로 판별하지 않는다'))
def then_not_identified(frame, anchors, label: str, quest):
    ctx, _client, _screen = make_context(["battle_gold"])
    ctx.set_frame(frame)
    assert not quest.matches(ctx, anchors.get(QUEST_PANEL)), "엉뚱하게 판별했습니다"


@then("수행에 성공한다")
def then_success(world):
    result = world["result"]
    assert result.success, f"진행 불가로 끝났습니다: {result.reason}"


# 앞말 받침에 따라 조사가 '가' 와 '이' 로 갈리므로 둘 다 받는다.
@then(parsers.re(r'진행 불가가 되고 사유에 "(?P<needle>[^"]+)" (?:가|이) 들어 있다'))
def then_blocked_with(world, needle: str):
    result = world["result"]
    assert not result.success, "성공으로 끝났습니다"
    assert not result.retryable, f"재시도로 끝났습니다: {result.reason}"
    assert needle in result.reason, f"사유: {result.reason}"


@then(parsers.re(r'재시도가 되고 사유에 "(?P<needle>[^"]+)" (?:가|이) 들어 있다'))
def then_retry_with(world, needle: str):
    """기다리면 풀릴 실패. 사람을 부르지 않고 처음부터 다시 본다."""
    result = world["result"]
    assert not result.success, "성공으로 끝났습니다"
    assert result.retryable, f"진행 불가로 끝났습니다: {result.reason}"
    assert needle in result.reason, f"사유: {result.reason}"


@then(parsers.parse("{count:d}번 누른다"))
def then_tap_count(world, count: int):
    taps = world["client"].taps
    assert len(taps) == count, f"기대 {count}회, 실제 {len(taps)}회 {taps}"


@then(parsers.re(r"(?P<index>\d+)번째로 누른 곳은 (?P<target>.+?)이다"))
def then_tap_target(world, tap_targets, index: str, target: str):
    """N번째 탭이 지정한 대상 위에 떨어졌는지 본다.

    대상 이름과 실제 영역의 대응은 각 테스트 모듈의 ``tap_targets`` 가 준다.
    """
    name = target.strip()
    resolver = tap_targets.get(name)
    assert resolver is not None, f"'{name}' 의 위치를 모릅니다. tap_targets 에 추가하세요."

    area = resolver()
    x, y = tap_normalized(world, int(index))
    assert inside(area, x, y), f"{index}번째 탭 ({x:.3f}, {y:.3f}) 이 '{name}' 영역 밖입니다"


def tap_normalized(world, index: int) -> tuple[float, float]:
    """N번째 탭을 정규화 좌표로 되돌린다."""
    taps = world["client"].taps
    assert len(taps) >= index, f"{index}번째 탭이 없습니다 (총 {len(taps)}회)"
    device = world["client"].device
    x, y = taps[index - 1]
    return x / (device.width - 1), y / (device.height - 1)


def inside(area: NormRect, x: float, y: float) -> bool:
    return area.x <= x <= area.x + area.w and area.y <= y <= area.y + area.h


def template_area(frame_name: str, template_name: str, search: NormRect, threshold: float = 0.75):
    """픽스처 화면에서 템플릿을 찾아 그 영역을 돌려주는 함수를 만든다."""

    def resolve() -> NormRect:
        from ccc.vision import find

        store = TemplateStore(TEMPLATE_DIR)
        match = find(load_frame(frame_name), store.load(template_name), threshold, search)
        assert match is not None, f"'{template_name}' 을 {frame_name} 에서 찾지 못했습니다"
        return match.rect

    return resolve


def color_button_area(frame_name: str, color, band: NormRect):
    """픽스처 화면에서 색으로 버튼을 찾아 그 영역을 돌려주는 함수를 만든다."""

    def resolve() -> NormRect:
        from ccc.vision import find_color_button

        rect = find_color_button(load_frame(frame_name), color, band)
        assert rect is not None, f"{frame_name} 에서 색 버튼을 찾지 못했습니다"
        return rect

    return resolve
