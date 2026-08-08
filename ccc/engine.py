"""자동화 실행 엔진.

백그라운드 스레드에서 다음을 반복한다.

    1. 게임 화면 한 프레임 캡처
    2. 켜져 있는 모듈을 priority 순으로 훑으며 check() 확인
    3. 조건이 맞으면 run() 실행

UI 스레드를 막지 않으며, 상태 변화와 로그는 콜백으로 알려 준다.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from .adb import AdbClient, AdbError
from .anchors import AnchorSet
from .capture import CaptureBackend
from .context import Context
from .notify import Notifier
from .modules.base import AutomationModule
from .vision import TemplateStore

log = logging.getLogger(__name__)

_MAX_CONSECUTIVE_ERRORS = 5


class Engine:
    def __init__(
        self,
        client: AdbClient,
        templates: TemplateStore,
        anchors: AnchorSet | None = None,
        notifier: Notifier | None = None,
        on_log: Callable[[str], None] | None = None,
        on_state: Callable[[str], None] | None = None,
    ):
        self.client = client
        self.templates = templates
        self.anchors = anchors if anchors is not None else AnchorSet()
        self.notifier = notifier if notifier is not None else Notifier()
        self.on_log = on_log
        self.on_state = on_state

        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._backend: CaptureBackend | None = None
        self._modules: list[AutomationModule] = []
        self._fps = 4.0
        self._options: dict[str, dict] = {}

    # ------------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        backend: CaptureBackend,
        modules: list[AutomationModule],
        fps: float = 4.0,
        options: dict[str, dict] | None = None,
    ) -> None:
        if self.running:
            self._emit("이미 실행 중입니다.")
            return
        if not modules:
            self._emit("켜져 있는 모듈이 없습니다. 먼저 모듈을 선택하세요.")
            return

        self._backend = backend
        self._modules = modules
        self._fps = max(0.2, fps)
        self._options = options or {}
        self._stop.clear()

        self._thread = threading.Thread(target=self._loop, name="ccc-engine", daemon=True)
        self._thread.start()
        self._set_state("running")
        self._emit(
            f"자동화 시작 (모듈 {len(modules)}개, {self._fps:g}fps, "
            f"캡처={backend.name})"
        )

    def stop(self, timeout: float = 5.0) -> None:
        if not self.running:
            return
        self._emit("정지 요청...")
        self._stop.set()
        assert self._thread is not None
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            self._emit("스레드가 제때 끝나지 않았습니다 (진행 중인 adb 명령 대기 중).")
        self._thread = None
        self._set_state("stopped")
        self._emit("자동화 정지됨.")

    # ------------------------------------------------------------------
    def _loop(self) -> None:
        assert self._backend is not None
        backend = self._backend
        ctx = Context(
            self.client,
            self.templates,
            self._stop,
            anchors=self.anchors,
            notifier=self.notifier,
            options=self._options,
            notify=self.on_log,
            frame_provider=backend.grab,
        )

        for module in self._modules:
            try:
                ctx.bind_module(module.key)
                module.setup(ctx)
            except Exception as exc:
                log.exception("setup 실패: %s", module.label)
                self._emit(f"[{module.label}] 준비 실패: {exc}")

        last_run: dict[str, float] = {}
        errors = 0
        adb_errors = 0
        interval = 1.0 / self._fps

        while not self._stop.is_set():
            tick_start = time.monotonic()
            adb_failed = False

            try:
                ctx.set_frame(backend.grab())
                errors = 0
            except Exception as exc:
                errors += 1
                log.exception("캡처 실패")
                self._emit(f"캡처 실패({errors}/{_MAX_CONSECUTIVE_ERRORS}): {exc}")
                if errors >= _MAX_CONSECUTIVE_ERRORS:
                    self._emit("캡처가 계속 실패해 자동화를 멈춥니다.")
                    break
                if self._stop.wait(1.0):
                    break
                continue

            for module in self._modules:
                if self._stop.is_set():
                    break

                now = time.monotonic()
                if now - last_run.get(module.key, 0.0) < module.interval:
                    continue

                ctx.bind_module(module.key)
                try:
                    if not module.check(ctx):
                        continue
                    module.run(ctx)
                    last_run[module.key] = time.monotonic()
                except AdbError as exc:
                    adb_errors += 1
                    adb_failed = True
                    self._emit(
                        f"[{module.label}] ADB 오류"
                        f"({adb_errors}/{_MAX_CONSECUTIVE_ERRORS}): {exc}"
                    )
                    last_run[module.key] = time.monotonic()
                    break  # adb 가 죽은 상태에서 남은 모듈을 돌려 봐야 같은 오류만 쌓인다
                except Exception as exc:
                    log.exception("모듈 실행 실패: %s", module.label)
                    self._emit(f"[{module.label}] 오류: {exc}")
                    last_run[module.key] = time.monotonic()
                else:
                    if module.exclusive:
                        break

            if adb_failed:
                if adb_errors >= _MAX_CONSECUTIVE_ERRORS:
                    self._emit(
                        "ADB 명령이 계속 실패해 자동화를 멈춥니다. "
                        "BlueStacks 가 켜져 있는지, 설정 > 고급에서 ADB 가 켜져 있는지 확인하세요."
                    )
                    break
                # 화면 캡처는 adb 를 거치지 않으므로 연결이 끊겨도 루프는 계속 돈다.
                # 재연결을 한 번 시도하고 잠시 쉰 뒤 다시 본다.
                try:
                    self.client.refresh_device()
                    self._emit("ADB 재연결 성공.")
                    adb_errors = 0
                except AdbError as exc:
                    self._emit(f"ADB 재연결 실패: {exc}")
                if self._stop.wait(1.0):
                    break
                continue

            adb_errors = 0

            elapsed = time.monotonic() - tick_start
            if self._stop.wait(max(0.0, interval - elapsed)):
                break

        for module in self._modules:
            try:
                ctx.bind_module(module.key)
                module.teardown(ctx)
            except Exception:
                log.exception("teardown 실패: %s", module.label)

        self._set_state("stopped")

    # ------------------------------------------------------------------
    def _emit(self, message: str) -> None:
        log.info(message)
        if self.on_log:
            self.on_log(message)

    def _set_state(self, state: str) -> None:
        if self.on_state:
            self.on_state(state)
