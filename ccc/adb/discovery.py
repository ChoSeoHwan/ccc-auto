"""adb 실행 파일 자동 탐색.

BlueStacks 는 자체 adb 바이너리를 번들로 갖고 있고, 설치 즉시 adb 서버를
띄워 둔다. 따라서 사용자가 별도로 platform-tools 를 설치하지 않아도
번들 adb 를 그대로 쓰는 것이 가장 확실하다.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_MACOS_CANDIDATES = [
    "/Applications/BlueStacks.app/Contents/MacOS/hd-adb",
    "/Applications/BlueStacks Air.app/Contents/MacOS/hd-adb",
    "~/Library/Android/sdk/platform-tools/adb",
    "/opt/homebrew/bin/adb",
    "/usr/local/bin/adb",
]

_WINDOWS_CANDIDATES = [
    r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe",
    r"C:\Program Files\BlueStacks_nxt\adb.exe",
    r"C:\Program Files\BlueStacks\HD-Adb.exe",
    r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe",
    r"%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe",
]

_LINUX_CANDIDATES = [
    "~/Android/Sdk/platform-tools/adb",
    "/usr/bin/adb",
    "/usr/local/bin/adb",
]


def _candidates() -> list[str]:
    if sys.platform == "darwin":
        return _MACOS_CANDIDATES
    if sys.platform.startswith("win"):
        return _WINDOWS_CANDIDATES
    return _LINUX_CANDIDATES


def _expand(raw: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw)))


def find_adb(preferred: str = "") -> str:
    """사용 가능한 adb 실행 파일 경로를 반환. 못 찾으면 FileNotFoundError.

    ``preferred`` 가 주어지면 그것을 최우선으로 검사한다 (설정 파일 값).
    """
    ordered: list[str] = []
    if preferred:
        ordered.append(preferred)
    ordered.extend(_candidates())

    for raw in ordered:
        path = _expand(raw)
        if path.is_file() and os.access(path, os.X_OK):
            log.info("adb 발견: %s", path)
            return str(path)

    # 마지막으로 PATH 확인
    found = shutil.which("adb")
    if found:
        log.info("adb 발견(PATH): %s", found)
        return found

    raise FileNotFoundError(
        "adb 실행 파일을 찾지 못했습니다. BlueStacks 설치 경로를 확인하거나 "
        "config.json 의 adb_path 에 직접 경로를 지정하세요."
    )


def list_devices(adb_path: str, timeout: float = 10.0) -> list[str]:
    """현재 adb 서버에 붙어 있는 디바이스 시리얼 목록."""
    try:
        out = subprocess.run(
            [adb_path, "devices"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("adb devices 실패: %s", exc)
        return []

    serials = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials
