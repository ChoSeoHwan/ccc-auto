"""설정 저장/로드.

프로젝트 루트의 ``config.json`` 에 저장한다. 화면 영역, ADB 주소,
모듈 on/off 상태 등 머신마다 달라지는 값만 담는다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .geometry import Rect

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

LOCAL_DIR = PROJECT_ROOT / "local"
"""이 컴퓨터에서만 쓰는 것들이 모여 있는 곳. 통째로 git 에서 제외한다.

게임 화면에서 뜬 이미지는 저작물이라 저장소에 넣지 않고, 각자 자기 화면에서
캡처해 여기에 쌓는다. 해상도·언어·보유 아이템이 사람마다 달라서 그 편이
정확하기도 하다.
"""

CONFIG_PATH = PROJECT_ROOT / "config.json"
TEMPLATE_DIR = LOCAL_DIR / "templates"
CAPTURE_DIR = LOCAL_DIR / "captures"
FIXTURE_DIR = LOCAL_DIR / "fixtures" / "frames"

DEFAULT_ADB_SERIAL = "127.0.0.1:5555"


@dataclass
class Config:
    # --- ADB ---
    adb_serial: str = DEFAULT_ADB_SERIAL
    """접속할 ADB 브리지 주소. BlueStacks 기본값은 127.0.0.1:5555."""

    adb_path: str = ""
    """adb 실행 파일 경로. 비워두면 자동 탐색."""

    # --- 화면 영역 ---
    region: Rect | None = None
    """드래그로 선택한 게임 화면 영역 (모니터 가상 좌표계, 논리 포인트 단위)."""

    monitor_index: int = 1
    """region 이 속한 모니터 번호 (mss 기준, 1 = 주 모니터)."""

    # --- 캡처 ---
    capture_backend: str = "screen"
    """'screen' = 화면 캡처(빠름, 영역 선택 필요) / 'adb' = adb screencap(느림, 영역 불필요)."""

    fps: float = 4.0
    """자동화 루프의 초당 프레임 수."""

    # --- 모듈 ---
    enabled_modules: list[str] = field(default_factory=list)
    module_options: dict[str, dict[str, Any]] = field(default_factory=dict)

    # --- 앵커 ---
    anchors: dict[str, dict[str, float]] = field(default_factory=dict)
    """기본값에서 사용자가 바꾼 앵커만 담긴다. ccc.anchors 참고."""

    notify: bool = True
    """알림이 필요한 상황에서 OS 알림을 띄울지."""

    # --- 안전장치 ---
    dry_run: bool = False
    """켜면 실제 입력을 보내지 않고 로그만 남긴다."""

    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "adb_serial": self.adb_serial,
            "adb_path": self.adb_path,
            "region": self.region.to_dict() if self.region else None,
            "monitor_index": self.monitor_index,
            "capture_backend": self.capture_backend,
            "fps": self.fps,
            "enabled_modules": self.enabled_modules,
            "module_options": self.module_options,
            "anchors": self.anchors,
            "notify": self.notify,
            "dry_run": self.dry_run,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        cfg = cls()
        cfg.adb_serial = data.get("adb_serial") or DEFAULT_ADB_SERIAL
        cfg.adb_path = data.get("adb_path", "")
        region = data.get("region")
        cfg.region = Rect.from_dict(region) if region else None
        cfg.monitor_index = int(data.get("monitor_index", 1))
        cfg.capture_backend = data.get("capture_backend", "screen")
        cfg.fps = float(data.get("fps", 4.0))
        cfg.enabled_modules = list(data.get("enabled_modules", []))
        cfg.module_options = dict(data.get("module_options", {}))
        cfg.anchors = dict(data.get("anchors", {}))
        cfg.notify = bool(data.get("notify", True))
        cfg.dry_run = bool(data.get("dry_run", False))
        return cfg

    # ------------------------------------------------------------------
    def save(self, path: Path = CONFIG_PATH) -> None:
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        log.debug("설정 저장: %s", path)

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        if not path.exists():
            log.info("설정 파일이 없어 기본값으로 시작합니다: %s", path)
            return cls()
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            log.warning("설정 파일을 읽지 못해 기본값을 씁니다 (%s): %s", path, exc)
            return cls()
