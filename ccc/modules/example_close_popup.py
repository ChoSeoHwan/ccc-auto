"""새 모듈을 만들 때 복사해서 쓰는 예시.

동작: 'popup_close' 템플릿(닫기 X 버튼)이 화면에 보이면 눌러서 팝업을 닫는다.

쓰는 법
    1. 컨트롤 창에서 '템플릿 캡처' 를 눌러 닫기 버튼을 잘라 내고
       이름을 popup_close 로 저장한다.
    2. 컨트롤 창에서 이 모듈을 켠다.

새 자동화를 만들 때는 이 파일을 복사해 이름만 바꾸면 된다. 이 디렉터리에
파일을 두면 자동으로 목록에 올라오고, 지우면 사라진다.
"""

from __future__ import annotations

from ..context import Context
from ..vision import TemplateError
from .base import AutomationModule


class ClosePopup(AutomationModule):
    name = "팝업 닫기"
    description = "'popup_close' 템플릿이 보이면 눌러 팝업을 닫습니다."
    interval = 1.0
    priority = 20        # 팝업은 다른 동작보다 먼저 치운다
    exclusive = True

    def setup(self, ctx: Context) -> None:
        self._warned = False

    def check(self, ctx: Context) -> bool:
        try:
            return ctx.exists("popup_close", threshold=ctx.option("threshold", 0.85))
        except TemplateError as exc:
            if not self._warned:
                ctx.log(str(exc))
                self._warned = True
            return False

    def run(self, ctx: Context) -> None:
        ctx.tap_template("popup_close", threshold=ctx.option("threshold", 0.85))
        ctx.sleep(0.5)
