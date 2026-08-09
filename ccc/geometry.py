"""화면/디바이스 좌표를 다루는 기본 도형 타입."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    """왼쪽 위 모서리 기준 사각형."""

    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2

    @property
    def aspect(self) -> float:
        return self.w / self.h if self.h else 0.0

    def is_valid(self, min_size: int = 20) -> bool:
        return self.w >= min_size and self.h >= min_size

    def to_mss(self) -> dict[str, int]:
        return {"left": self.x, "top": self.y, "width": self.w, "height": self.h}

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, data: dict) -> "Rect":
        return cls(int(data["x"]), int(data["y"]), int(data["w"]), int(data["h"]))

    @classmethod
    def from_corners(cls, x1: int, y1: int, x2: int, y2: int) -> "Rect":
        left, right = sorted((int(x1), int(x2)))
        top, bottom = sorted((int(y1), int(y2)))
        return cls(left, top, right - left, bottom - top)


@dataclass(frozen=True)
class NormRect:
    """0.0~1.0 정규화 사각형.

    해상도/창 크기가 바뀌어도 그대로 쓸 수 있도록 자동화 모듈은 항상
    이 정규화 좌표로 위치를 표현한다.
    """

    x: float
    y: float
    w: float
    h: float

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.w / 2, self.y + self.h / 2

    def scaled(self, width: int, height: int) -> Rect:
        """정규화 좌표를 주어진 크기의 픽셀 사각형으로 변환."""
        return Rect(
            round(self.x * width),
            round(self.y * height),
            round(self.w * width),
            round(self.h * height),
        )

    def near(self, other: "NormRect", tolerance: float = 0.01) -> bool:
        """두 사각형의 중심이 사실상 같은 자리인지.

        같은 버튼을 다시 본 것인지, 다른 버튼으로 바뀐 것인지 가릴 때 쓴다.
        찾은 자리는 프레임마다 1~2px 씩 흔들리므로 딱 맞기를 요구하면 안 된다.
        """
        x1, y1 = self.center
        x2, y2 = other.center
        return abs(x1 - x2) <= tolerance and abs(y1 - y2) <= tolerance

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, data: dict) -> "NormRect":
        return cls(float(data["x"]), float(data["y"]), float(data["w"]), float(data["h"]))

    @classmethod
    def from_pixels(cls, rect: Rect, width: int, height: int) -> "NormRect":
        return cls(rect.x / width, rect.y / height, rect.w / width, rect.h / height)


FULL = NormRect(0.0, 0.0, 1.0, 1.0)
