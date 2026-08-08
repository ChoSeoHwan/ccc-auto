"""화면 앵커 — 게임 UI 요소가 있는 정규화 영역.

해상도와 무관하게 쓸 수 있도록 모두 0.0~1.0 값이다. 기본값은 1080x1920
디바이스 화면에서 실측한 것이고, 게임 업데이트로 배치가 바뀌면 컨트롤 창의
'영역 보정' 에서 다시 잡을 수 있다.
"""

from __future__ import annotations

from .geometry import NormRect

QUEST_PANEL = "quest_panel"
QUEST_PANEL_SAMPLE = "quest_panel_sample"
NAV_CLOSE = "nav_close"
SAFE_TAP = "safe_tap"

DEFAULTS: dict[str, NormRect] = {
    # 퀘스트창 전체가 들어오는 밴드. 화면 오른쪽 끝에 붙어 있고 글자 길이에
    # 따라 왼쪽으로 늘어나므로 넉넉하게 잡는다. 클릭 지점도 여기서 구한다.
    QUEST_PANEL: NormRect(0.55, 0.500, 0.45, 0.105),
    # 골드/회색 판정용 색 표본. 패널 본체 중 항상 채워지는 오른쪽 안쪽만 본다.
    QUEST_PANEL_SAMPLE: NormRect(0.88, 0.532, 0.10, 0.042),
    # 하단 네비게이션 중앙의 빨간 X 버튼 자리. 전투화면에서는 비어 있다.
    NAV_CLOSE: NormRect(0.44, 0.945, 0.12, 0.040),
    # X 버튼 없는 전체화면 연출(레벨업 등)을 넘길 때 누르는 지점.
    # 전투화면에서 눌러도 아무 일이 없어야 하므로 버튼이 없는 전장 한복판을 쓴다.
    SAFE_TAP: NormRect(0.44, 0.260, 0.12, 0.040),
}

LABELS: dict[str, str] = {
    QUEST_PANEL: "퀘스트창",
    QUEST_PANEL_SAMPLE: "퀘스트창 색 표본",
    NAV_CLOSE: "닫기(X) 버튼",
    SAFE_TAP: "빈 곳 탭 지점",
}


class AnchorSet:
    """설정에 저장된 앵커를 읽고 쓴다. 없으면 기본값으로 떨어진다."""

    def __init__(self, stored: dict[str, dict] | None = None):
        self._stored: dict[str, NormRect] = {}
        for name, raw in (stored or {}).items():
            try:
                self._stored[name] = NormRect.from_dict(raw)
            except (KeyError, TypeError, ValueError):
                continue

    def get(self, name: str) -> NormRect:
        if name in self._stored:
            return self._stored[name]
        if name in DEFAULTS:
            return DEFAULTS[name]
        raise KeyError(f"알 수 없는 앵커: {name}")

    def set(self, name: str, rect: NormRect) -> None:
        self._stored[name] = rect

    def reset(self, name: str) -> None:
        self._stored.pop(name, None)

    def is_customized(self, name: str) -> bool:
        return name in self._stored

    def to_dict(self) -> dict[str, dict]:
        return {name: rect.to_dict() for name, rect in self._stored.items()}

    @staticmethod
    def names() -> list[str]:
        return list(DEFAULTS)

    @staticmethod
    def label(name: str) -> str:
        return LABELS.get(name, name)
