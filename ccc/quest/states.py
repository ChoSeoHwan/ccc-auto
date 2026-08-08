"""퀘스트 자동화 상태 정의."""

from __future__ import annotations

from enum import Enum


class MainState(Enum):
    """최상위 상태."""

    IDLE = "대기"
    CHECK = "퀘스트확인"
    PROGRESS = "퀘스트진행"
    COMPLETE = "퀘스트완료"


class ProgressStep(Enum):
    """'퀘스트진행' 안의 세부 단계."""

    IDENTIFY = "퀘스트판별"
    EXECUTE = "퀘스트수행"
    VERIFY = "완료여부확인"


class PanelState(Enum):
    """퀘스트창의 색 판정 결과."""

    GOLD = "완료"
    GRAY = "진행중"
    UNKNOWN = "판정불가"
