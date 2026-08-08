"""``ccc/quests/`` 안의 퀘스트 정의를 모아 온다."""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil

from .definition import QuestDefinition

log = logging.getLogger(__name__)

_PACKAGE = "ccc.quests"


class QuestRegistry:
    """등록된 퀘스트 정의 목록과 로드 오류를 들고 있다."""

    def __init__(self) -> None:
        self.definitions: list[QuestDefinition] = []
        self.errors: dict[str, str] = {}

    def load(self, reload: bool = False) -> list[QuestDefinition]:
        self.definitions = []
        self.errors = {}

        try:
            package = importlib.import_module(_PACKAGE)
        except ImportError as exc:
            log.error("퀘스트 패키지를 못 읽었습니다: %s", exc)
            self.errors[_PACKAGE] = str(exc)
            return []

        for info in pkgutil.iter_modules(package.__path__):
            if info.name.startswith("_"):
                continue
            self._load_module(f"{_PACKAGE}.{info.name}", info.name, reload)

        self.definitions.sort(key=lambda d: d.label)
        log.info(
            "퀘스트 정의 %d개: %s",
            len(self.definitions),
            ", ".join(d.label for d in self.definitions) or "없음",
        )
        return self.definitions

    def _load_module(self, full_name: str, short_name: str, reload: bool) -> None:
        try:
            module = importlib.import_module(full_name)
            if reload:
                module = importlib.reload(module)
        except Exception as exc:
            log.exception("퀘스트 정의 로드 실패: %s", full_name)
            self.errors[short_name] = f"{type(exc).__name__}: {exc}"
            return

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if not _is_concrete_definition(obj, full_name):
                continue
            try:
                self.definitions.append(obj())
            except Exception as exc:
                log.exception("퀘스트 정의 생성 실패: %s", obj.__name__)
                self.errors[f"{short_name}.{obj.__name__}"] = f"{type(exc).__name__}: {exc}"


def _is_concrete_definition(obj: type, module_name: str) -> bool:
    return (
        issubclass(obj, QuestDefinition)
        and obj is not QuestDefinition
        and not inspect.isabstract(obj)
        and obj.__module__ == module_name
    )
