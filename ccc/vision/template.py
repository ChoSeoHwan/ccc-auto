"""템플릿 이미지 매칭.

해상도가 바뀌어도 재사용할 수 있도록, 템플릿을 저장할 때 "캡처 당시
게임 화면 대비 몇 %  크기였는지" 를 같이 기록한다. 매칭할 때는 현재
프레임 크기에 맞춰 템플릿을 다시 확대/축소한다.

  templates/
    shop_close.png    # 잘라낸 이미지
    shop_close.json   # {"nx":..,"ny":..,"nw":..,"nh":..}
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..geometry import NormRect

log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.85


@dataclass(frozen=True)
class Template:
    name: str
    image: np.ndarray
    """BGR 원본 이미지."""
    source: NormRect
    """캡처 당시 게임 화면에서 차지하던 정규화 사각형."""

    @property
    def search_hint(self) -> NormRect:
        """원래 있던 자리 주변. 탐색 범위를 좁힐 때 쓴다."""
        pad_x, pad_y = self.source.w * 0.5, self.source.h * 0.5
        return NormRect(
            max(0.0, self.source.x - pad_x),
            max(0.0, self.source.y - pad_y),
            min(1.0, self.source.w + pad_x * 2),
            min(1.0, self.source.h + pad_y * 2),
        )


@dataclass(frozen=True)
class Match:
    name: str
    score: float
    rect: NormRect

    @property
    def center(self) -> tuple[float, float]:
        return self.rect.center


class TemplateError(RuntimeError):
    pass


class TemplateStore:
    """templates/ 디렉터리를 읽고 쓰는 저장소 (한 번 읽은 건 캐시)."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Template] = {}

    # ------------------------------------------------------------------
    def names(self) -> list[str]:
        return sorted(p.stem for p in self.directory.glob("*.png"))

    def save(self, name: str, image: np.ndarray, source: NormRect) -> Template:
        import cv2

        png_path = self.directory / f"{name}.png"
        meta_path = self.directory / f"{name}.json"
        if not cv2.imwrite(str(png_path), image):
            raise TemplateError(f"템플릿 저장 실패: {png_path}")
        meta_path.write_text(
            json.dumps(source.to_dict(), indent=2) + "\n", encoding="utf-8"
        )

        template = Template(name, image, source)
        self._cache[name] = template
        log.info("템플릿 저장: %s (%dx%d)", name, image.shape[1], image.shape[0])
        return template

    def load(self, name: str) -> Template:
        cached = self._cache.get(name)
        if cached is not None:
            return cached

        import cv2

        png_path = self.directory / f"{name}.png"
        if not png_path.exists():
            raise TemplateError(
                f"템플릿 '{name}' 이 없습니다. 컨트롤 창의 '템플릿 캡처' 로 먼저 만들어 주세요."
            )
        image = cv2.imread(str(png_path), cv2.IMREAD_COLOR)
        if image is None:
            raise TemplateError(f"템플릿 이미지를 읽지 못했습니다: {png_path}")

        meta_path = self.directory / f"{name}.json"
        if meta_path.exists():
            source = NormRect.from_dict(json.loads(meta_path.read_text(encoding="utf-8")))
        else:
            # 메타가 없으면 크기 보정 없이 원본 크기로 매칭한다.
            source = NormRect(0.0, 0.0, 0.0, 0.0)

        template = Template(name, image, source)
        self._cache[name] = template
        return template

    def reload(self) -> None:
        self._cache.clear()

    def delete(self, name: str) -> None:
        (self.directory / f"{name}.png").unlink(missing_ok=True)
        (self.directory / f"{name}.json").unlink(missing_ok=True)
        self._cache.pop(name, None)


# ----------------------------------------------------------------------
# 매칭
# ----------------------------------------------------------------------
def _resized_for(frame: np.ndarray, template: Template) -> np.ndarray:
    """현재 프레임 크기에 맞게 템플릿을 리사이즈."""
    import cv2

    if template.source.w <= 0 or template.source.h <= 0:
        return template.image

    frame_h, frame_w = frame.shape[:2]
    target_w = max(4, round(template.source.w * frame_w))
    target_h = max(4, round(template.source.h * frame_h))
    src_h, src_w = template.image.shape[:2]
    if (target_w, target_h) == (src_w, src_h):
        return template.image

    interp = cv2.INTER_AREA if target_w < src_w else cv2.INTER_LINEAR
    return cv2.resize(template.image, (target_w, target_h), interpolation=interp)


def find(
    frame: np.ndarray,
    template: Template,
    threshold: float = DEFAULT_THRESHOLD,
    search: NormRect | None = None,
) -> Match | None:
    """프레임에서 템플릿을 찾아 가장 잘 맞는 위치를 반환. 없으면 None.

    ``search`` 를 주면 그 영역 안에서만 찾는다 (빠르고 오탐이 준다).
    """
    matches = find_all(frame, template, threshold, search, limit=1)
    return matches[0] if matches else None


def find_all(
    frame: np.ndarray,
    template: Template,
    threshold: float = DEFAULT_THRESHOLD,
    search: NormRect | None = None,
    limit: int = 20,
) -> list[Match]:
    """임계값을 넘는 위치를 점수 높은 순으로 반환."""
    import cv2

    frame_h, frame_w = frame.shape[:2]
    if frame_h == 0 or frame_w == 0:
        return []

    if search is not None:
        area = search.scaled(frame_w, frame_h)
        x0 = max(0, min(area.x, frame_w - 1))
        y0 = max(0, min(area.y, frame_h - 1))
        x1 = max(x0 + 1, min(area.right, frame_w))
        y1 = max(y0 + 1, min(area.bottom, frame_h))
        haystack = frame[y0:y1, x0:x1]
    else:
        x0 = y0 = 0
        haystack = frame

    needle = _resized_for(frame, template)
    if needle.shape[0] > haystack.shape[0] or needle.shape[1] > haystack.shape[1]:
        log.debug("템플릿 '%s' 이 탐색 영역보다 큽니다.", template.name)
        return []

    result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(result >= threshold)
    if len(xs) == 0:
        return []

    needle_h, needle_w = needle.shape[:2]
    candidates = sorted(
        ((float(result[y, x]), int(x), int(y)) for x, y in zip(xs, ys)),
        reverse=True,
    )

    matches: list[Match] = []
    taken: list[tuple[int, int]] = []
    for score, x, y in candidates:
        # 같은 대상에 겹쳐 잡힌 것들은 하나로 합친다.
        if any(
            abs(x - tx) < needle_w * 0.5 and abs(y - ty) < needle_h * 0.5
            for tx, ty in taken
        ):
            continue
        taken.append((x, y))
        matches.append(
            Match(
                name=template.name,
                score=score,
                rect=NormRect(
                    (x0 + x) / frame_w,
                    (y0 + y) / frame_h,
                    needle_w / frame_w,
                    needle_h / frame_h,
                ),
            )
        )
        if len(matches) >= limit:
            break

    return matches
