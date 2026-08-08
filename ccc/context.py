"""자동화 모듈에게 전달되는 실행 컨텍스트.

모듈은 절대 픽셀 좌표를 쓰지 않고 항상 0.0~1.0 정규화 좌표로 위치를
표현한다. 컨텍스트가 이를 디바이스 좌표로 바꿔 ADB 로 내보내므로,
블루스택 창 크기나 해상도가 바뀌어도 모듈 코드는 그대로 쓸 수 있다.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

import numpy as np

from .adb import AdbClient
from .anchors import AnchorSet
from .geometry import NormRect
from .notify import Notifier
from .vision import Match, TemplateStore, find, find_all, find_text
from .vision.template import DEFAULT_THRESHOLD

log = logging.getLogger(__name__)

FIRST_CHECK_DELAY = 0.1
"""버튼을 누른 뒤 첫 확인까지의 틈.

게임이 반응할 최소한만 주고 바로 본다. 화면이 이미 바뀌었으면 여기서 끝난다.
"""

FOLLOW_UP_INTERVAL = 0.3
"""첫 확인에서 아직이면 이 간격으로 다시 본다."""


class Context:
    def __init__(
        self,
        client: AdbClient,
        templates: TemplateStore,
        stop_event: threading.Event,
        anchors: AnchorSet | None = None,
        notifier: Notifier | None = None,
        options: dict[str, dict[str, Any]] | None = None,
        notify: Callable[[str], None] | None = None,
        frame_provider: Callable[[], np.ndarray] | None = None,
    ):
        self.adb = client
        self.templates = templates
        self.stop_event = stop_event
        self.anchors = anchors if anchors is not None else AnchorSet()
        self.notifier = notifier if notifier is not None else Notifier()
        self._options = options if options is not None else {}
        self._notify = notify
        self._frame_provider = frame_provider
        self._frame: np.ndarray | None = None
        self._module_key = ""
        self.state: dict[str, Any] = {}
        """모듈들이 tick 사이에 값을 남겨 둘 수 있는 공용 저장소."""

    # ------------------------------------------------------------------
    # 프레임
    # ------------------------------------------------------------------
    @property
    def frame(self) -> np.ndarray:
        if self._frame is None:
            raise RuntimeError("아직 프레임이 캡처되지 않았습니다.")
        return self._frame

    def set_frame(self, frame: np.ndarray) -> None:
        self._frame = frame

    def refresh(self) -> np.ndarray:
        """지금 화면을 다시 캡처한다.

        엔진은 tick 마다 프레임을 주지만, 버튼을 누른 직후의 화면을 그 자리에서
        확인해야 할 때가 있어 모듈이 직접 다시 찍을 수 있게 열어 둔다.
        """
        if self._frame_provider is not None:
            self.set_frame(self._frame_provider())
        return self.frame

    @property
    def frame_size(self) -> tuple[int, int]:
        """캡처된 프레임의 (가로, 세로) 픽셀."""
        height, width = self.frame.shape[:2]
        return width, height

    def crop(self, area: NormRect) -> np.ndarray:
        from .vision import crop as _crop

        return _crop(self.frame, area)

    # ------------------------------------------------------------------
    # 좌표 변환
    # ------------------------------------------------------------------
    def to_device(self, nx: float, ny: float) -> tuple[int, int]:
        """정규화 좌표를 디바이스 픽셀 좌표로."""
        device = self.adb.device
        x = int(round(min(max(nx, 0.0), 1.0) * (device.width - 1)))
        y = int(round(min(max(ny, 0.0), 1.0) * (device.height - 1)))
        return x, y

    # ------------------------------------------------------------------
    # 입력
    # ------------------------------------------------------------------
    def tap(self, nx: float, ny: float) -> None:
        x, y = self.to_device(nx, ny)
        log.debug("tap n(%.3f, %.3f) -> d(%d, %d)", nx, ny, x, y)
        self.adb.tap(x, y)

    def tap_rect(self, rect: NormRect) -> None:
        self.tap(*rect.center)

    def tap_match(self, match: Match) -> None:
        self.tap(*match.center)

    def swipe(
        self, nx1: float, ny1: float, nx2: float, ny2: float, duration_ms: int = 300
    ) -> None:
        x1, y1 = self.to_device(nx1, ny1)
        x2, y2 = self.to_device(nx2, ny2)
        self.adb.swipe(x1, y1, x2, y2, duration_ms)

    def long_press(self, nx: float, ny: float, duration_ms: int = 800) -> None:
        x, y = self.to_device(nx, ny)
        self.adb.long_press(x, y, duration_ms)

    def back(self) -> None:
        self.adb.back()

    # ------------------------------------------------------------------
    # 인식
    # ------------------------------------------------------------------
    def find(
        self,
        name: str,
        threshold: float = DEFAULT_THRESHOLD,
        search: NormRect | None = None,
    ) -> Match | None:
        return find(self.frame, self.templates.load(name), threshold, search)

    def find_all(
        self,
        name: str,
        threshold: float = DEFAULT_THRESHOLD,
        search: NormRect | None = None,
    ) -> list[Match]:
        return find_all(self.frame, self.templates.load(name), threshold, search)

    def find_text(
        self,
        name: str,
        threshold: float = 0.75,
        search: NormRect | None = None,
    ) -> Match | None:
        """반투명 배경 위 흰 글씨를 이진화해서 찾는다. 배경색 변화에 강하다."""
        return find_text(self.frame, self.templates.load(name), threshold, search)

    def exists(self, name: str, threshold: float = DEFAULT_THRESHOLD) -> bool:
        return self.find(name, threshold) is not None

    def tap_template(self, name: str, threshold: float = DEFAULT_THRESHOLD) -> bool:
        """템플릿을 찾으면 그 중심을 누르고 True. 못 찾으면 False."""
        match = self.find(name, threshold)
        if match is None:
            return False
        self.log(f"'{name}' 발견 (일치도 {match.score:.2f}) → 클릭")
        self.tap_match(match)
        return True

    # ------------------------------------------------------------------
    # 유틸
    # ------------------------------------------------------------------
    def sleep(self, seconds: float) -> bool:
        """정지 요청이 오면 즉시 깨는 대기. 계속 진행해도 되면 True."""
        return not self.stop_event.wait(seconds)

    def wait_until(
        self,
        condition: Callable[[np.ndarray], bool],
        timeout: float,
        interval: float = FOLLOW_UP_INTERVAL,
        first_delay: float = FIRST_CHECK_DELAY,
    ) -> bool:
        """조건이 설 때까지 화면을 다시 보며 기다린다. 서면 즉시 빠져나온다.

        게임이 반응할 최소한의 틈(``first_delay``)만 주고 바로 확인한다.
        아직이면 ``interval`` 마다 다시 본다. "연출이 끝날 때까지 5초" 처럼
        넉넉히 재우면 2초 만에 끝나도 3초를 버린다.

        폴링 간격은 캡처 비용에 눌린다. adb 캡처는 한 장에 0.58초라 간격을
        아무리 줄여도 그보다 자주 볼 수 없다. 화면 캡처(6.5ms)로 바꾸면
        간격이 그대로 반응 속도가 된다.
        """
        deadline = time.monotonic() + timeout
        if not self.sleep(first_delay):
            return False

        while True:
            if condition(self.refresh()):
                return True
            if time.monotonic() >= deadline or not self.sleep(interval):
                return False

    def wait_for_template(
        self,
        name: str,
        timeout: float,
        threshold: float = DEFAULT_THRESHOLD,
        search: NormRect | None = None,
    ) -> Match | None:
        """템플릿이 나타날 때까지 기다렸다가 찾은 것을 돌려준다."""
        found: list[Match] = []

        def appeared(_frame: np.ndarray) -> bool:
            match = self.find(name, threshold, search)
            if match is None:
                return False
            found.append(match)
            return True

        self.wait_until(appeared, timeout)
        return found[0] if found else None

    @property
    def stopping(self) -> bool:
        return self.stop_event.is_set()

    def log(self, message: str) -> None:
        prefix = f"[{self._module_key}] " if self._module_key else ""
        log.info("%s%s", prefix, message)
        if self._notify:
            self._notify(f"{prefix}{message}")

    def option(self, key: str, default: Any = None) -> Any:
        """현재 실행 중인 모듈의 사용자 설정값."""
        return self._options.get(self._module_key, {}).get(key, default)

    # 엔진이 모듈을 호출하기 직전에 세팅한다.
    def bind_module(self, key: str) -> None:
        self._module_key = key
