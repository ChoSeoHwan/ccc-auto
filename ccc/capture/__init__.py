from .adb_capture import AdbCapture
from .base import CaptureBackend
from .screen import ScreenCapture, ScreenCaptureError, list_monitors

__all__ = [
    "AdbCapture",
    "CaptureBackend",
    "ScreenCapture",
    "ScreenCaptureError",
    "list_monitors",
    "create_backend",
]


def create_backend(config, client) -> CaptureBackend:
    """설정에 맞는 캡처 백엔드를 만든다.

    'screen' 인데 영역이 아직 없으면 adb 캡처로 자동 폴백한다.
    """
    if config.capture_backend == "screen" and config.region is not None:
        return ScreenCapture(config.region)
    return AdbCapture(client)
