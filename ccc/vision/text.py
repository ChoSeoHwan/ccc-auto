"""반투명 패널 위 흰 글씨를 인식하기 위한 이진화 매칭.

퀘스트창은 반투명이라 뒤의 전투 배경이 계속 바뀌고, 완료 여부에 따라
배경색도 황금색/회색으로 달라진다. 원본 색으로 템플릿을 맞추면 이 변화에
그대로 흔들린다.

대신 글자만 남기고 이진화한 뒤 모양끼리 비교한다. 게임 UI 글자는 채도가
거의 없는 흰색이고 주변 패널보다 훨씬 밝아서, 저채도 + 고명도 조건만으로
깨끗하게 분리된다(실측: 황금 패널 본체 V≈205 / 글자 V≈255).
"""

from __future__ import annotations

import logging

import numpy as np

from ..geometry import NormRect
from .template import DEFAULT_THRESHOLD, Match, Template, _resized_for

log = logging.getLogger(__name__)

MIN_VALUE = 220
"""글자로 볼 최소 명도."""

MAX_SATURATION = 70
"""글자로 볼 최대 채도. 흰 글씨는 채도가 거의 0 이다."""


def text_mask(
    image: np.ndarray, min_value: int = MIN_VALUE, max_saturation: int = MAX_SATURATION
) -> np.ndarray:
    """흰 글씨만 255 로 남긴 1채널 마스크."""
    import cv2

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturation, value = hsv[:, :, 1], hsv[:, :, 2]
    return ((saturation <= max_saturation) & (value >= min_value)).astype(np.uint8) * 255


def find_text(
    frame: np.ndarray,
    template: Template,
    threshold: float = DEFAULT_THRESHOLD,
    search: NormRect | None = None,
    min_value: int = MIN_VALUE,
    max_saturation: int = MAX_SATURATION,
) -> Match | None:
    """글자 모양만 비교해 템플릿을 찾는다. 배경색 변화에 영향받지 않는다.

    화면이 템플릿을 뜰 때보다 작으면 템플릿을 줄이지 않고 **탐색 영역을 키워서**
    템플릿 원본 크기로 맞춘다. 글자는 획이 얇아서 축소하면 이진화 단계에서
    뭉개지는데, 실제 운영 해상도가 원본의 절반쯤이라 이 손실이 그대로 오탐으로
    이어진다. 탐색 영역은 보통 화면의 일부라 확대해도 비용이 크지 않다.
    """
    import cv2

    frame_h, frame_w = frame.shape[:2]
    if frame_h == 0 or frame_w == 0:
        return None

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

    needle, zoom = _match_scale(frame, template)
    if zoom != 1.0:
        haystack = cv2.resize(
            haystack,
            (max(1, round(haystack.shape[1] * zoom)), max(1, round(haystack.shape[0] * zoom))),
            interpolation=cv2.INTER_CUBIC,
        )

    if needle.shape[0] > haystack.shape[0] or needle.shape[1] > haystack.shape[1]:
        log.debug("텍스트 템플릿 '%s' 이 탐색 영역보다 큽니다.", template.name)
        return None

    haystack_mask = text_mask(haystack, min_value, max_saturation)
    needle_mask = text_mask(needle, min_value, max_saturation)
    if np.count_nonzero(needle_mask) < needle_mask.size * 0.02:
        log.warning(
            "텍스트 템플릿 '%s' 에서 글자를 거의 못 찾았습니다. 다시 캡처해 주세요.",
            template.name,
        )
        return None

    result = cv2.matchTemplate(haystack_mask, needle_mask, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(result)
    if score < threshold:
        return None

    needle_h, needle_w = needle_mask.shape[:2]
    return Match(
        name=template.name,
        score=float(score),
        rect=NormRect(
            (x0 + location[0] / zoom) / frame_w,
            (y0 + location[1] / zoom) / frame_h,
            needle_w / zoom / frame_w,
            needle_h / zoom / frame_h,
        ),
    )


def _match_scale(frame: np.ndarray, template: Template) -> tuple[np.ndarray, float]:
    """(비교에 쓸 템플릿, 탐색 영역을 키울 배율) 을 정한다.

    화면이 더 크거나 같으면 지금까지처럼 템플릿을 그 크기로 맞춘다. 화면이 더
    작을 때만 템플릿을 원본 그대로 두고 탐색 영역을 키운다.
    """
    if template.source.w <= 0:
        return template.image, 1.0

    frame_w = frame.shape[1]
    native_w = template.image.shape[1]
    target_w = max(4, round(template.source.w * frame_w))
    if target_w >= native_w:
        return _resized_for(frame, template), 1.0
    return template.image, native_w / target_w
