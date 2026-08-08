"""사용자 알림.

컨트롤 창 로그만으로는 자리를 비웠을 때 놓치므로, OS 알림 센터와 소리를
함께 쓴다. 알림 실패가 자동화를 멈추면 안 되므로 모든 실패는 삼킨다.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

log = logging.getLogger(__name__)

_TITLE = "쿠키런 크럼블 자동화"


class Notifier:
    """OS 알림 + 콜백 로그."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def send(self, message: str, title: str = _TITLE) -> None:
        if not self.enabled:
            return
        try:
            self._dispatch(message, title)
        except Exception:
            log.debug("OS 알림 전송 실패 (무시)", exc_info=True)

    # ------------------------------------------------------------------
    def _dispatch(self, message: str, title: str) -> None:
        if sys.platform == "darwin":
            self._macos(message, title)
        elif sys.platform.startswith("win"):
            self._windows(message, title)
        else:
            self._linux(message, title)

    def _macos(self, message: str, title: str) -> None:
        script = (
            f'display notification {_applescript_str(message)} '
            f'with title {_applescript_str(title)} sound name "Glass"'
        )
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10, check=False)

    def _windows(self, message: str, title: str) -> None:
        script = (
            "[reflection.assembly]::LoadWithPartialName('System.Windows.Forms')>$null;"
            "$n=New-Object System.Windows.Forms.NotifyIcon;"
            "$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;"
            f"$n.ShowBalloonTip(5000,'{_ps_str(title)}','{_ps_str(message)}',"
            "[System.Windows.Forms.ToolTipIcon]::Info)"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            timeout=15,
            check=False,
        )

    def _linux(self, message: str, title: str) -> None:
        if shutil.which("notify-send"):
            subprocess.run(
                ["notify-send", title, message], capture_output=True, timeout=10, check=False
            )


def _applescript_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _ps_str(value: str) -> str:
    return value.replace("'", "''")
