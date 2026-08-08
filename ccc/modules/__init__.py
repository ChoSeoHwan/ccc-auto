"""모듈 자동 탐색.

``ccc/modules/`` 안의 모든 파이썬 파일을 읽어 ``AutomationModule`` 상속
클래스를 수집한다. 파일을 추가하면 자동 등록되고, 지우면 자동으로 사라진다.
밑줄(_)로 시작하는 파일과 ``base`` 는 건너뛴다.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil

from .base import AutomationModule

log = logging.getLogger(__name__)

__all__ = ["AutomationModule", "discover", "load_errors"]

_SKIP = {"base"}

_errors: dict[str, str] = {}


def discover(reload: bool = False) -> list[AutomationModule]:
    """등록된 모듈 인스턴스를 priority, 이름 순으로 반환."""
    _errors.clear()
    found: list[AutomationModule] = []

    for info in pkgutil.iter_modules(__path__):
        if info.name in _SKIP or info.name.startswith("_"):
            continue

        full_name = f"{__name__}.{info.name}"
        try:
            module = importlib.import_module(full_name)
            if reload:
                module = importlib.reload(module)
        except Exception as exc:  # 모듈 하나가 깨져도 나머지는 살린다
            log.exception("모듈 로드 실패: %s", full_name)
            _errors[info.name] = f"{type(exc).__name__}: {exc}"
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, AutomationModule)
                and obj is not AutomationModule
                and not inspect.isabstract(obj)
                and obj.__module__ == full_name
            ):
                try:
                    found.append(obj())
                except Exception as exc:
                    log.exception("모듈 생성 실패: %s", obj.__name__)
                    _errors[f"{info.name}.{obj.__name__}"] = f"{type(exc).__name__}: {exc}"

    found.sort(key=lambda m: (m.priority, m.label))
    log.info("모듈 %d개 로드됨: %s", len(found), ", ".join(m.label for m in found) or "없음")
    return found


def load_errors() -> dict[str, str]:
    """마지막 discover() 에서 발생한 로드 오류."""
    return dict(_errors)
