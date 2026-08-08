"""adb screencap 기반 캡처 백엔드.

화면 기록 권한이 필요 없고 영역 선택도 필요 없다. 대신 프레임당
200~500ms 정도로 느려서 빠른 반응이 필요한 자동화에는 적합하지 않다.
화면 캡처가 막혔을 때의 폴백으로 쓴다.
"""

from __future__ import annotations

import logging

import numpy as np

from ..adb import AdbClient
from .base import CaptureBackend

log = logging.getLogger(__name__)


class AdbCapture(CaptureBackend):
    name = "adb"

    def __init__(self, client: AdbClient):
        self.client = client

    def grab(self) -> np.ndarray:
        import cv2

        png = self.client.screencap_png()
        buffer = np.frombuffer(png, dtype=np.uint8)
        frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError("adb screencap 결과를 디코드하지 못했습니다.")
        return frame
