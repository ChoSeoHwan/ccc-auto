"""애플리케이션 서비스 계층.

화면(UI)과 실행 로직 사이의 경계다. UI 는 이 클래스의 메서드만 호출하고,
여기서는 tkinter 를 전혀 모른다. 덕분에 GUI 없이도(``main.py --check``,
테스트 코드) 같은 로직을 그대로 돌릴 수 있다.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Callable

import numpy as np

from .adb import AdbClient, AdbError, DeviceInfo
from .anchors import AnchorSet
from .capture import AdbCapture, CaptureBackend, ScreenCapture, list_monitors
from .config import TEMPLATE_DIR, Config
from .engine import Engine
from .geometry import NormRect, Rect
from .modules import discover, load_errors
from .modules.base import AutomationModule
from .notify import Notifier
from .quest.registry import QuestRegistry
from .templates_spec import TemplateSpec
from .vision import TemplateStore

if TYPE_CHECKING:  # 순환 임포트를 피하려고 타입 검사용으로만 가져온다
    from .modules.quest_runner import QuestAutomation

log = logging.getLogger(__name__)

BACKEND_SCREEN = "screen"
BACKEND_ADB = "adb"


class AppError(RuntimeError):
    """사용자에게 그대로 보여 줄 수 있는 오류."""


class AutomationApp:
    """연결 · 캡처 · 모듈 · 실행을 묶어 관리한다."""

    def __init__(self, config: Config):
        self.config = config
        self.templates = TemplateStore(TEMPLATE_DIR)
        self.anchors = AnchorSet(config.anchors)
        self.notifier = Notifier(config.notify)

        self.client: AdbClient | None = None
        self.engine: Engine | None = None
        self.modules: list[AutomationModule] = []
        self.module_errors: dict[str, str] = {}

        self.on_log: Callable[[str], None] | None = None
        self.on_engine_state: Callable[[str], None] | None = None

    # ------------------------------------------------------------------
    # 연결
    # ------------------------------------------------------------------
    @property
    def connected(self) -> bool:
        return self.client is not None

    @property
    def device(self) -> DeviceInfo | None:
        return self.client.device if self.client else None

    def connect(self, serial: str) -> DeviceInfo:
        serial = serial.strip()
        if not serial:
            raise AppError("ADB 브리지 주소를 입력하세요.")

        try:
            client = AdbClient(serial, self.config.adb_path, dry_run=self.config.dry_run)
            device = client.connect()
        except (AdbError, FileNotFoundError) as exc:
            raise AppError(str(exc)) from exc

        self.client = client
        self.engine = Engine(
            client,
            self.templates,
            anchors=self.anchors,
            notifier=self.notifier,
            on_log=self._log,
            on_state=self._engine_state,
        )
        self.config.adb_serial = serial
        return device

    def refresh_device(self) -> DeviceInfo:
        """회전이나 해상도 변경을 반영한다."""
        self._require_client()
        assert self.client is not None
        return self.client.refresh_device()

    # ------------------------------------------------------------------
    # 화면 영역 · 캡처
    # ------------------------------------------------------------------
    def set_region(self, rect: Rect, monitor_index: int) -> None:
        self.config.region = rect
        self.config.monitor_index = monitor_index
        self.config.capture_backend = BACKEND_SCREEN

    def region_warning(self) -> str:
        """영역 설정이 의심스러우면 사유를, 문제없으면 빈 문자열을 돌려준다."""
        rect = self.config.region
        if rect is None or self.config.capture_backend != BACKEND_SCREEN:
            return ""

        monitors = list_monitors()
        if monitors and not any(_contains(monitor, rect) for monitor in monitors):
            return "저장된 영역이 현재 모니터 배치를 벗어납니다. 영역을 다시 잡아 주세요."

        device = self.device
        if device and abs(rect.aspect - device.aspect) > 0.08:
            return f"영역 비율 {rect.aspect:.2f} 가 디바이스 비율 {device.aspect:.2f} 와 다릅니다."
        return ""

    def create_backend(self) -> CaptureBackend:
        self._require_client()
        assert self.client is not None
        if self.config.capture_backend == BACKEND_SCREEN:
            if self.config.region is None:
                raise AppError("화면 영역이 설정되지 않았습니다. '영역 재감지' 를 먼저 누르세요.")
            return ScreenCapture(self.config.region)
        return AdbCapture(self.client)

    def capture(self) -> np.ndarray:
        try:
            return self.create_backend().grab()
        except AppError:
            raise
        except Exception as exc:
            raise AppError(f"캡처에 실패했습니다: {exc}") from exc

    # ------------------------------------------------------------------
    # 앵커
    # ------------------------------------------------------------------
    def set_anchor(self, name: str, rect: NormRect) -> None:
        self.anchors.set(name, rect)
        self.config.anchors = self.anchors.to_dict()

    def reset_anchor(self, name: str) -> None:
        self.anchors.reset(name)
        self.config.anchors = self.anchors.to_dict()

    # ------------------------------------------------------------------
    # 모듈
    # ------------------------------------------------------------------
    def reload_modules(self) -> list[AutomationModule]:
        self.modules = discover(reload=True)
        self.module_errors = load_errors()
        return self.modules

    def is_module_enabled(self, module: AutomationModule) -> bool:
        if self.config.enabled_modules:
            return module.key in self.config.enabled_modules
        return module.enabled_by_default

    def set_enabled_modules(self, keys: list[str]) -> None:
        self.config.enabled_modules = keys

    def enabled_modules(self) -> list[AutomationModule]:
        return [m for m in self.modules if self.is_module_enabled(m)]

    # ------------------------------------------------------------------
    # 템플릿
    # ------------------------------------------------------------------
    def template_groups(self) -> list[tuple[str, list[TemplateSpec]]]:
        """캡처 마법사에 보여 줄 순서대로 (묶음 이름, 그 묶음의 템플릿들).

        모듈이 먼저(priority 순), 그 다음 퀘스트(setup_order 순)다. 같은 이름의
        템플릿을 두 곳에서 선언하면 먼저 나온 쪽만 남는다.
        """
        owners: list = sorted(self.modules, key=lambda m: (m.priority, m.label))
        owners += sorted(QuestRegistry().load(), key=lambda q: (q.setup_order, q.label))

        groups: list[tuple[str, list[TemplateSpec]]] = []
        seen: set[str] = set()
        for owner in owners:
            name = owner.template_group or owner.label
            specs = []
            for spec in owner.template_specs:
                if spec.name in seen:
                    continue
                seen.add(spec.name)
                specs.append(replace(spec, group=name))
            if specs:
                groups.append((name, specs))
        return groups

    def required_templates(self) -> list[TemplateSpec]:
        """켜져 있는 모듈과 등록된 퀘스트가 필요로 하는 템플릿 전부.

        게임 화면 이미지는 저장소에 없으므로 각자 자기 화면에서 떠야 한다.
        캡처 마법사가 이 목록을 따라간다.
        """
        return [spec for _, specs in self.template_groups() for spec in specs]

    def missing_templates(self) -> list[TemplateSpec]:
        have = set(self.templates.names())
        return [spec for spec in self.required_templates() if spec.name not in have]

    def quest_module(self) -> "QuestAutomation | None":
        # reload_modules() 가 모듈을 다시 임포트하면 클래스 객체가 새로 만들어진다.
        # 임포트 시점에 고정된 참조로 isinstance 를 하면 항상 False 가 되므로
        # 호출할 때마다 현재 클래스를 다시 가져온다.
        from .modules.quest_runner import QuestAutomation

        return next((m for m in self.modules if isinstance(m, QuestAutomation)), None)

    # ------------------------------------------------------------------
    # 실행
    # ------------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self.engine is not None and self.engine.running

    def start(self) -> None:
        self._require_client()
        assert self.engine is not None and self.client is not None

        selected = self.enabled_modules()
        if not selected:
            raise AppError("실행할 모듈을 하나 이상 켜 주세요.")

        backend = self.create_backend()
        self.client.dry_run = self.config.dry_run
        self.client.refresh_device()
        self.engine.start(
            backend, selected, fps=self.config.fps, options=self.config.module_options
        )

    def stop(self) -> None:
        if self.engine:
            self.engine.stop()

    # ------------------------------------------------------------------
    def save_config(self) -> None:
        self.config.anchors = self.anchors.to_dict()
        self.notifier.enabled = self.config.notify
        self.config.save()

    # ------------------------------------------------------------------
    def _require_client(self) -> None:
        if self.client is None:
            raise AppError("먼저 ADB 에 연결하세요.")

    def _log(self, message: str) -> None:
        if self.on_log:
            self.on_log(message)

    def _engine_state(self, state: str) -> None:
        if self.on_engine_state:
            self.on_engine_state(state)


def _contains(monitor: Rect, rect: Rect) -> bool:
    return (
        rect.x >= monitor.x
        and rect.y >= monitor.y
        and rect.right <= monitor.right
        and rect.bottom <= monitor.bottom
    )
