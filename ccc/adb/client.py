"""BlueStacks(안드로이드)와 통신하는 ADB 클라이언트.

입력은 전부 여기를 통해 나간다. 실제 마우스 커서를 건드리지 않으므로
자동화가 도는 동안에도 PC 를 그대로 쓸 수 있다.
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
from dataclasses import dataclass

from .discovery import find_adb, list_devices

log = logging.getLogger(__name__)

_CUR_RE = re.compile(r"cur=(\d+)x(\d+)")
_WM_SIZE_RE = re.compile(r"(?:Override|Physical) size:\s*(\d+)x(\d+)")
_FOCUS_RE = re.compile(r"mCurrentFocus=.*?\s([\w.]+)/([\w.]+)")


class AdbError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeviceInfo:
    serial: str
    width: int
    height: int
    model: str = ""

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 0.0


class AdbClient:
    """adb 명령을 감싼 얇은 래퍼.

    UI 스레드와 자동화 스레드가 같이 쓰므로 명령 실행은 락으로 직렬화한다.
    """

    def __init__(self, serial: str, adb_path: str = "", dry_run: bool = False):
        self.serial = serial
        self.adb_path = find_adb(adb_path)
        self.dry_run = dry_run
        self._lock = threading.Lock()
        self._device: DeviceInfo | None = None

    # ------------------------------------------------------------------
    # 저수준 실행
    # ------------------------------------------------------------------
    def _run(self, args: list[str], timeout: float = 15.0, binary: bool = False):
        cmd = [self.adb_path, "-s", self.serial, *args]
        with self._lock:
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise AdbError(f"adb 명령 시간 초과: {' '.join(args)}") from exc
            except OSError as exc:
                raise AdbError(f"adb 실행 실패: {exc}") from exc

        if proc.returncode != 0:
            msg = proc.stderr.decode("utf-8", "replace").strip()
            raise AdbError(f"adb {' '.join(args)} 실패: {msg}")

        return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")

    def shell(self, command: str, timeout: float = 15.0) -> str:
        return self._run(["shell", command], timeout=timeout)

    # ------------------------------------------------------------------
    # 연결
    # ------------------------------------------------------------------
    def connect(self) -> DeviceInfo:
        """브리지에 접속하고 디바이스 정보를 읽어 온다."""
        available = list_devices(self.adb_path)
        if ":" in self.serial and self.serial not in available:
            try:
                subprocess.run(
                    [self.adb_path, "connect", self.serial],
                    capture_output=True,
                    timeout=15.0,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                log.warning("adb connect 실패(무시하고 진행): %s", exc)
            available = list_devices(self.adb_path)

        if self.serial not in available:
            raise AdbError(
                f"디바이스 '{self.serial}' 에 연결하지 못했습니다. "
                f"현재 연결된 디바이스: {available or '없음'}. "
                "BlueStacks 가 실행 중인지, 설정 > 고급에서 ADB 가 켜져 있는지 확인하세요."
            )

        width, height = self.display_size()
        model = self.shell("getprop ro.product.model").strip()
        self._device = DeviceInfo(self.serial, width, height, model)
        log.info("디바이스 연결됨: %s (%dx%d, %s)", self.serial, width, height, model or "?")
        return self._device

    @property
    def device(self) -> DeviceInfo:
        if self._device is None:
            return self.connect()
        return self._device

    def refresh_device(self) -> DeviceInfo:
        """회전 등으로 해상도가 바뀌었을 수 있으니 다시 읽는다."""
        self._device = None
        return self.connect()

    # ------------------------------------------------------------------
    # 디바이스 정보
    # ------------------------------------------------------------------
    def display_size(self) -> tuple[int, int]:
        """현재 회전 상태가 반영된 화면 크기 (가로, 세로)."""
        try:
            dump = self.shell("dumpsys window displays")
            match = _CUR_RE.search(dump)
            if match:
                return int(match.group(1)), int(match.group(2))
        except AdbError as exc:
            log.debug("dumpsys window displays 실패, wm size 로 폴백: %s", exc)

        out = self.shell("wm size")
        matches = _WM_SIZE_RE.findall(out)
        if not matches:
            raise AdbError(f"화면 크기를 알아내지 못했습니다: {out!r}")
        width, height = matches[-1]  # Override 가 있으면 그쪽이 우선
        return int(width), int(height)

    def current_package(self) -> str:
        """현재 포커스를 가진 앱의 패키지명."""
        try:
            dump = self.shell("dumpsys window")
        except AdbError:
            return ""
        match = _FOCUS_RE.search(dump)
        return match.group(1) if match else ""

    # ------------------------------------------------------------------
    # 입력
    # ------------------------------------------------------------------
    def tap(self, x: int, y: int) -> None:
        if self.dry_run:
            log.info("[dry-run] tap (%d, %d)", x, y)
            return
        self.shell(f"input tap {int(x)} {int(y)}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        if self.dry_run:
            log.info("[dry-run] swipe (%d,%d)->(%d,%d) %dms", x1, y1, x2, y2, duration_ms)
            return
        self.shell(
            f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}",
            timeout=max(15.0, duration_ms / 1000 + 10),
        )

    def long_press(self, x: int, y: int, duration_ms: int = 800) -> None:
        self.swipe(x, y, x, y, duration_ms)

    def keyevent(self, key: str | int) -> None:
        if self.dry_run:
            log.info("[dry-run] keyevent %s", key)
            return
        self.shell(f"input keyevent {key}")

    def text(self, value: str) -> None:
        if self.dry_run:
            log.info("[dry-run] text %r", value)
            return
        escaped = value.replace(" ", "%s").replace("'", r"\'")
        self.shell(f"input text '{escaped}'")

    def back(self) -> None:
        self.keyevent("KEYCODE_BACK")

    # ------------------------------------------------------------------
    # 캡처
    # ------------------------------------------------------------------
    def screencap_png(self) -> bytes:
        """디바이스 화면을 PNG 바이트로 캡처 (화면 캡처보다 느리지만 권한 불필요)."""
        return self._run(["exec-out", "screencap", "-p"], timeout=30.0, binary=True)

    # ------------------------------------------------------------------
    # 앱 제어
    # ------------------------------------------------------------------
    def launch_app(self, package: str) -> None:
        self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")

    def is_app_running(self, package: str) -> bool:
        return bool(self.shell(f"pidof {package}").strip())
