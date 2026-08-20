"""아레나 무한 도전 BDD 스텝 정의."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ccc.app import ARENA_MODULE_KEY, AutomationApp
from ccc.config import Config
from ccc.engine import Engine
from ccc.modules.arena_repeat import CHALLENGE_TEMPLATE, RESULT_TEMPLATE, ArenaRepeat
from ccc.ui.control_window import (
    ControlWindow,
    _button_states,
    _is_user_selectable_module,
)

scenarios("features/arena_repeat.feature")

pytestmark = pytest.mark.no_frames


class FakeContext:
    """템플릿 노출과 입력만 기록하는 아레나용 가짜 컨텍스트."""

    def __init__(self, visible: str | None = None):
        self.visible = visible
        self.taps = []
        self.keys: list[str] = []

    def find(self, template, threshold, search):
        return SimpleNamespace(score=0.96) if template == self.visible else None

    def find_text(self, template, threshold, search):
        return SimpleNamespace(score=0.94) if template == self.visible else None

    def log(self, message):
        pass

    def tap_match(self, match):
        self.taps.append(match)

    def back(self):
        self.keys.append("KEYCODE_BACK")

    def wait_until(self, condition, timeout):
        self.visible = None
        return condition(None)


class FakeModule:
    def __init__(self, key: str):
        self._key = key

    @property
    def key(self) -> str:
        return self._key


class FakeEngine:
    running = False

    def __init__(self):
        self.started = []

    def start(self, backend, modules, *, fps, options):
        self.started.append(modules)


class ThreadThatMustNotBeJoined:
    def __init__(self):
        self.joined = False

    def is_alive(self):
        return True

    def join(self, timeout=None):
        self.joined = True


class FakeSwitchApp:
    def __init__(self, mode: str):
        self.running = True
        self.run_mode = mode
        self.stop_requests = 0
        self.started: list[str] = []

    def request_stop(self):
        self.stop_requests += 1

    def start(self):
        self.started.append("general")

    def start_arena(self):
        self.started.append("arena")


class FakeStringVar:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


@pytest.fixture
def world() -> dict:
    return {}


@given(parsers.parse('아레나 화면에 "{state}" 가 보인다'))
def given_arena_screen(world, state: str):
    templates = {"도전하기": CHALLENGE_TEMPLATE, "결과": RESULT_TEMPLATE}
    ctx = FakeContext(templates[state])
    module = ArenaRepeat()
    module.setup(ctx)  # type: ignore[arg-type]
    world.update(ctx=ctx, module=module)


@given("도전하기를 눌러 아레나 자동화가 활성화되었다")
def given_active_arena(world):
    ctx = FakeContext(CHALLENGE_TEMPLATE)
    module = ArenaRepeat()
    module.setup(ctx)  # type: ignore[arg-type]
    assert module.check(ctx)  # type: ignore[arg-type]
    world.update(ctx=ctx, module=module)


@given("아레나 화면에 아무 템플릿도 보이지 않는다")
def given_no_arena_template(world):
    world["ctx"].visible = None


@given("일반 모듈과 아레나 모듈이 로드되어 있다")
def given_loaded_modules(world):
    app = AutomationApp(Config(enabled_modules=["quest", ARENA_MODULE_KEY]))
    quest = FakeModule("quest")
    arena = FakeModule(ARENA_MODULE_KEY)
    app.modules = [arena, quest]  # type: ignore[list-item]
    app.client = SimpleNamespace(dry_run=False, refresh_device=lambda: None)
    engine = FakeEngine()
    app.engine = engine  # type: ignore[assignment]
    app.create_backend = lambda: "screen"  # type: ignore[method-assign]
    world.update(app=app, engine=engine, quest=quest, arena=arena)


@given("자동화 엔진이 실행 중이다")
def given_running_engine(world):
    engine = Engine(None, None)  # type: ignore[arg-type]
    thread = ThreadThatMustNotBeJoined()
    engine._thread = thread  # type: ignore[assignment]
    engine._stop = threading.Event()
    world.update(engine=engine, thread=thread)


@given(parsers.parse('"{mode}" 자동화가 실행 중이다'))
def given_running_mode(world, mode: str):
    modes = {"일반": "general", "아레나": "arena"}
    app = FakeSwitchApp(modes[mode])
    window = object.__new__(ControlWindow)
    window.app = app
    window.status_var = FakeStringVar()
    window._pending_start_mode = None
    window._save = lambda: None
    window._log = lambda message: None
    world.update(app=app, window=window)


@given(parsers.parse('자동화 상태가 "{state}" 이고 실행 모드가 "{mode}" 이다'))
def given_button_context(world, state: str, mode: str):
    modes = {"없음": None, "일반": "general", "아레나": "arena"}
    world["button_context"] = (state == "실행", modes[mode])


@when("아레나 자동화를 한 걸음 진행하면")
def when_arena_step(world):
    module, ctx = world["module"], world["ctx"]
    assert module.check(ctx)
    module.run(ctx)


@when("아레나 화면을 확인하면")
def when_check_arena(world):
    world["claimed"] = world["module"].check(world["ctx"])


@when("일반 자동화를 시작하면")
def when_start_general(world):
    world["app"].start()


@when("아레나 자동화를 시작하면")
def when_start_arena(world):
    world["app"].start_arena()


@when("비동기 정지를 요청하면")
def when_request_stop(world):
    world["engine"].request_stop()


@when(parsers.parse('"{mode}" 시작 버튼을 누르면'))
def when_press_other_start(world, mode: str):
    modes = {"일반": "general", "아레나": "arena"}
    world["window"]._request_start_mode(modes[mode])


@when("현재 자동화가 종료되면")
def when_current_mode_stops(world):
    world["app"].running = False
    world["window"]._continue_pending_start()


@then("도전하기를 한 번 누른다")
def then_tap_challenge(world):
    assert len(world["ctx"].taps) == 1


@then("ESC는 누르지 않는다")
def then_no_escape(world):
    assert not world["ctx"].keys


@then("ESC를 한 번 누른다")
def then_escape(world):
    assert world["ctx"].keys == ["KEYCODE_BACK"]


@then("화면은 누르지 않는다")
def then_no_tap(world):
    assert not world["ctx"].taps


@then("아레나 모듈이 다른 모듈보다 계속 우선한다")
def then_arena_claims_frame(world):
    assert world["claimed"]


@then("일반 모듈만 실행한다")
def then_only_general(world):
    assert world["engine"].started == [[world["quest"]]]


@then("아레나 모듈만 실행한다")
def then_only_arena(world):
    assert world["engine"].started == [[world["arena"]]]


@then("체크 목록에는 일반 모듈만 보인다")
def then_only_general_selectable(world):
    selectable = [
        module
        for module in world["app"].modules
        if _is_user_selectable_module(module)
    ]
    assert selectable == [world["quest"]]


@then("정지 신호를 보내고 작업 스레드를 기다리지 않는다")
def then_non_blocking_stop(world):
    assert world["engine"]._stop.is_set()
    assert not world["thread"].joined


@then("현재 자동화에 정지만 요청한다")
def then_request_current_stop(world):
    assert world["app"].stop_requests == 1
    assert not world["app"].started


@then(parsers.parse('"{mode}" 자동화를 시작한다'))
def then_start_new_mode(world, mode: str):
    modes = {"일반": "general", "아레나": "arena"}
    assert world["app"].started == [modes[mode]]


@then(parsers.parse('버튼 상태는 "{expected}" 이다'))
def then_button_states(world, expected: str):
    assert _button_states(*world["button_context"]) == tuple(expected.split(","))
