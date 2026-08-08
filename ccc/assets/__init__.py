"""저장소에 함께 들어 있는 인식용 조각.

원칙은 `local/` 이다 — 게임 화면 이미지는 저작물이라 저장소에 넣지 않고 각자
자기 화면에서 뜬다(AGENT.md 참고). 여기는 그 원칙의 좁은 예외다.

**왜 예외인가.** 오븐 레벨업 확인창처럼 몇 시간에 한 번 스쳐 가는 화면은
사용자가 그 순간을 붙잡아 캡처하기가 현실적으로 어렵다. 캡처 마법사에 항목을
띄워 봐야 영영 '필요' 로 남고, 그동안 자동화는 그 자리에서 계속 막힌다.
그래서 버튼 글자 부분만 잘라 여기에 둔다.

**넣을 것과 넣지 말 것.** 여기에는 *가끔만 나타나서 사용자가 뜰 수 없는*
버튼만 둔다. 평소에 늘 보이는 것(퀘스트 이름, Auto 버튼 등)은 사용자가 자기
해상도에서 직접 뜨는 편이 정확하므로 종전대로 `template_specs` 로 안내한다.

**배율.** 조각마다 실측한 정규화 크기를 함께 적어 둔다. 매칭할 때 지금 화면
크기에 맞춰 다시 스케일하므로, 이 값이 틀리면 아무리 같은 그림이어도 안 걸린다.
"""

from __future__ import annotations

from pathlib import Path

from ..geometry import NormRect
from ..vision.template import Template

ASSET_DIR = Path(__file__).resolve().parent

_SOURCES: dict[str, NormRect] = {
    # 창 스크린샷(538x930)에서 실측한 뒤 게임 좌표로 환산했다.
    # 게임 영역은 창 안에서 세로 31px 아래, 배율 1.0 이었다(두 지점 0.810/0.880 일치).
    # 저장된 그림은 83x31 인데 운영 화면(506폭)에서는 76x28 로 잡혔다 — 배율 0.92.
    "oven_levelup": NormRect(0.6146, 0.8653, 0.1502, 0.0312),
    # 오븐 성장 화면은 아직 스크린샷이 없어 위치를 재지 못했다. 같은 출처의
    # 조각이라 배율만 같게(0.92) 잡아 두었다 — 87x28 -> 80x26.
    # 위치를 모르므로 찾을 때는 화면 전체를 본다.
    "oven_grow": NormRect(0.0, 0.0, 0.1581, 0.0290),
}

_cache: dict[str, Template] = {}


def load(name: str) -> Template:
    """번들된 조각을 ``Template`` 으로 돌려준다. 없으면 ``FileNotFoundError``."""
    cached = _cache.get(name)
    if cached is not None:
        return cached

    import cv2

    path = ASSET_DIR / f"{name}.png"
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(f"번들 조각을 읽지 못했습니다: {path}")

    template = Template(name, image, _SOURCES[name])
    _cache[name] = template
    return template
