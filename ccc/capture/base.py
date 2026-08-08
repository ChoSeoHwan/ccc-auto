"""캡처 백엔드 공통 인터페이스."""

from __future__ import annotations

import abc

import numpy as np


class CaptureBackend(abc.ABC):
    """게임 화면 한 프레임을 BGR numpy 배열로 돌려주는 소스."""

    name: str = "base"

    @abc.abstractmethod
    def grab(self) -> np.ndarray:
        """현재 화면을 BGR (H, W, 3) uint8 배열로 반환."""

    def close(self) -> None:
        """리소스 정리. 필요 없으면 그대로 둔다."""
