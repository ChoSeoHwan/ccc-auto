"""게임이 꺼지거나 다른 앱으로 넘어가면 다시 띄운다.

템플릿 없이 ADB 정보만으로 동작하므로, 설치 직후 바로 켜서 연결이
제대로 됐는지 확인하는 용도로도 쓸 수 있다.
"""

from __future__ import annotations

from ..context import Context
from .base import AutomationModule

GAME_PACKAGE = "com.devsisters.cc"


class KeepGameForeground(AutomationModule):
    name = "게임 유지"
    description = "게임이 종료되거나 백그라운드로 가면 다시 실행합니다."
    interval = 10.0
    priority = 10
    exclusive = True

    def check(self, ctx: Context) -> bool:
        package = ctx.option("package", GAME_PACKAGE)
        return ctx.adb.current_package() != package

    def run(self, ctx: Context) -> None:
        package = ctx.option("package", GAME_PACKAGE)
        ctx.log(f"게임이 앞에 없어 다시 실행합니다: {package}")
        ctx.adb.launch_app(package)
        ctx.sleep(5.0)
