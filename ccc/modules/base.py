"""자동화 모듈의 기반 클래스.

새 자동화를 추가하려면 이 디렉터리(``ccc/modules/``)에 파이썬 파일을 하나
만들고 ``AutomationModule`` 을 상속한 클래스를 정의하면 끝이다. 프로그램이
시작할 때 자동으로 찾아 컨트롤 창 목록에 올린다. 파일을 지우면 그대로
사라진다.

    from ccc.modules.base import AutomationModule

    class 상자열기(AutomationModule):
        name = "상자 열기"
        interval = 2.0

        def check(self, ctx):
            return ctx.exists("box_button")

        def run(self, ctx):
            ctx.tap_template("box_button")
"""

from __future__ import annotations

import abc

from ..context import Context
from ..templates_spec import TemplateSpec


class AutomationModule(abc.ABC):
    """한 가지 자동화 동작을 담당하는 단위."""

    name: str = ""
    """컨트롤 창에 표시할 이름. 비우면 클래스명을 쓴다."""

    description: str = ""
    """무엇을 하는 모듈인지 한 줄 설명."""

    interval: float = 1.0
    """이 모듈을 다시 시도하기까지의 최소 간격(초)."""

    priority: int = 100
    """작을수록 먼저 검사한다. 팝업 닫기처럼 항상 우선인 건 낮게 준다."""

    exclusive: bool = True
    """True 면 이 모듈이 동작한 tick 에서 뒤 모듈은 건너뛴다."""

    enabled_by_default: bool = False
    """설정 파일이 없을 때 기본으로 켜 둘지."""

    template_specs: list[TemplateSpec] = []
    """이 모듈이 필요로 하는 템플릿과 그 캡처 방법. 캡처 마법사가 읽는다."""

    # ------------------------------------------------------------------
    @property
    def key(self) -> str:
        """설정 파일에 저장될 고유 식별자."""
        return f"{type(self).__module__.rsplit('.', 1)[-1]}.{type(self).__name__}"

    @property
    def label(self) -> str:
        return self.name or type(self).__name__

    # ------------------------------------------------------------------
    def setup(self, ctx: Context) -> None:
        """자동화 시작 시 한 번 호출. 템플릿 미리 로드 등에 쓴다."""

    @abc.abstractmethod
    def check(self, ctx: Context) -> bool:
        """지금 이 모듈이 동작해야 하는 상황인지 판단한다.

        여기서는 화면만 보고 판단하고, 입력은 보내지 않는다.
        """

    @abc.abstractmethod
    def run(self, ctx: Context) -> None:
        """실제 동작을 수행한다. ``check`` 가 True 일 때만 호출된다."""

    def teardown(self, ctx: Context) -> None:
        """자동화 정지 시 한 번 호출."""
