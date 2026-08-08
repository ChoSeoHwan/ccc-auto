"""화면(모니터) 영역 캡처 백엔드.

드래그로 선택한 영역만 잘라 온다. mss 는 스레드마다 인스턴스가 필요해서
thread-local 로 관리한다.

macOS Retina 처럼 논리 좌표와 물리 픽셀이 다른 환경에서는 요청한 크기보다
큰 이미지가 돌아올 수 있다. 자동화 모듈은 모두 정규화 좌표를 쓰므로 실제
픽셀 크기가 몇이든 상관없다.
"""

from __future__ import annotations

import logging
import threading

import numpy as np

from ..geometry import Rect
from .base import CaptureBackend

log = logging.getLogger(__name__)


class ScreenCaptureError(RuntimeError):
    pass


def _new_mss():
    """mss 인스턴스 생성. 10.x 는 MSS, 그 이전은 mss() 를 쓴다."""
    try:
        import mss
    except ImportError as exc:  # pragma: no cover - 설치 안내용
        raise ScreenCaptureError(
            "mss 가 설치돼 있지 않습니다. pip install -r requirements.txt"
        ) from exc
    factory = getattr(mss, "MSS", None) or mss.mss
    return factory()


class ScreenCapture(CaptureBackend):
    name = "screen"

    def __init__(self, region: Rect):
        if not region.is_valid():
            raise ScreenCaptureError(f"선택 영역이 너무 작습니다: {region}")
        self.region = region
        self._local = threading.local()

    def _sct(self):
        sct = getattr(self._local, "sct", None)
        if sct is None:
            sct = _new_mss()
            self._local.sct = sct
        return sct

    def grab(self) -> np.ndarray:
        try:
            raw = self._sct().grab(self.region.to_mss())
        except Exception as exc:  # mss 는 자체 예외 계층을 쓴다
            raise ScreenCaptureError(
                f"화면 캡처에 실패했습니다: {exc}. macOS 라면 시스템 설정 > "
                "개인정보 보호 및 보안 > 화면 기록 에서 실행 중인 앱(터미널/PyCharm)에 "
                "권한을 주고 앱을 재시작하세요."
            ) from exc

        # mss 는 BGRA 를 준다. 알파를 떼고 BGR 로 맞춘다.
        frame = np.asarray(raw, dtype=np.uint8)
        return np.ascontiguousarray(frame[:, :, :3])


def list_monitors() -> list[Rect]:
    """연결된 모니터들의 사각형 목록 (mss 의 monitors[1:] 순서)."""
    try:
        sct = _new_mss()
    except ScreenCaptureError:
        return []
    with sct:
        return [
            Rect(m["left"], m["top"], m["width"], m["height"]) for m in sct.monitors[1:]
        ]
