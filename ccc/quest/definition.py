"""퀘스트 정의의 기반 클래스.

퀘스트 하나를 ``ccc/quests/`` 안의 파일 하나로 만든다. 파일을 추가하면
자동으로 등록되고, 지우면 사라진다.

    from ccc.context import Context
    from ccc.quest.definition import QuestDefinition, StepResult

    class 상자사용(QuestDefinition):
        name = "가방에서 상자 사용하기"
        name_templates = ["quest_use_box"]   # 퀘스트 이름 부분을 캡처한 템플릿

        def execute(self, ctx: Context) -> StepResult:
            if not ctx.tap_template("nav_bag"):
                return StepResult.blocked("가방 버튼을 못 찾았습니다")
            ...
            return StepResult.ok()
"""

from __future__ import annotations

import abc
from dataclasses import dataclass

from ..context import Context
from ..geometry import NormRect
from ..templates_spec import TemplateSpec
from ..vision import TemplateError, find_text


@dataclass(frozen=True)
class StepResult:
    """퀘스트 수행 결과."""

    success: bool
    reason: str = ""
    retryable: bool = False
    """화면만 바뀌면 저절로 풀릴 실패인지. ``retry`` 로 만든 결과만 True."""

    @classmethod
    def ok(cls, reason: str = "") -> "StepResult":
        return cls(True, reason)

    @classmethod
    def blocked(cls, reason: str) -> "StepResult":
        """더 이상 진행할 수 없을 때. 몇 번 되풀이되면 알림 후 대기로 멈춘다."""
        return cls(False, reason)

    @classmethod
    def retry(cls, reason: str) -> "StepResult":
        """지금은 못 하지만 화면이 바뀌면 될 수 있을 때.

        ``blocked`` 와 달리 사람을 부르지 않는다. 훨씬 넉넉한 횟수까지 봐 주고,
        그래도 안 되면 멈추는 대신 '퀘스트확인' 으로 돌아가 처음부터 다시 본다.
        연출이 지나가기를 기다리면 되는 일로 자동화를 세우지 않기 위해서다.
        """
        return cls(False, reason, retryable=True)


class QuestDefinition(abc.ABC):
    """퀘스트 한 종류의 판별 조건과 수행 절차."""

    name: str = ""
    """컨트롤 창과 알림에 표시할 이름."""

    name_templates: list[str] = []
    """퀘스트 이름을 판별할 템플릿. 가장 높은 점수를 그 퀘스트의 점수로 쓴다.

    숫자가 바뀌는 퀘스트("10회 하기" / "30회 하기")는 숫자를 뺀 부분만
    캡처해 두면 둘 다 걸린다.
    """

    match_threshold: float = 0.55
    """이름 템플릿 매칭 임계값. 이진화 후 비교라 원본 매칭보다 낮게 잡는다.

    실제 운영 해상도(474px 폭)에서 퀘스트 이름은 한 줄이 13px 남짓이다. 이만한
    글자를 이진화하면 획이 어느 픽셀에 걸리느냐가 캡처할 때와 조금만 달라져도
    점수가 크게 흔들린다. 잘 맞는 템플릿도 0.68 언저리에 머무는 일이 흔해서
    0.75 로는 등록된 퀘스트를 놓친다.

    실측 (474px 폭 프레임)
        등록된 퀘스트   1등 0.675 ~ 0.989   2등과의 여유 0.207 ~ 0.384
        미등록 퀘스트   1등 0.362 ~ 0.370   2등과의 여유 0.003 ~ 0.027
    두 무리 사이가 0.30 넘게 비어 있어 그 한가운데를 잡는다. 어느 쪽으로도
    0.12 이상 여유가 있고, 판별은 ``MIN_SCORE_MARGIN`` 이 한 번 더 거른다.
    """

    template_specs: list[TemplateSpec] = []
    """이 퀘스트가 필요로 하는 템플릿과 그 캡처 방법.

    게임 이미지는 저장소에 없으므로, 캡처 마법사가 이 선언을 읽어 사용자를
    안내한다. 여기 적지 않으면 마법사 목록에 나타나지 않는다.
    """

    template_group: str = ""
    """캡처 마법사에서 이 퀘스트의 템플릿을 묶어 보여 줄 이름. 비우면 ``label``."""

    setup_order: int = 100
    """캡처 마법사 목록에서의 순서. 작을수록 위. 같으면 ``label`` 가나다순."""

    # ------------------------------------------------------------------
    @property
    def key(self) -> str:
        return f"{type(self).__module__.rsplit('.', 1)[-1]}.{type(self).__name__}"

    @property
    def label(self) -> str:
        return self.name or type(self).__name__

    # ------------------------------------------------------------------
    def match_score(self, ctx: Context, search: NormRect) -> float:
        """현재 퀘스트창이 이 퀘스트와 얼마나 닮았는지 0.0~1.0 으로 돌려준다.

        상태기는 이 점수로 **가장 잘 맞는 퀘스트 하나**를 고른다. 예/아니오만
        돌려주면 "쿠키 뽑기 10회 하기" 와 "펫 뽑기 10회 하기" 처럼 뒷부분이
        같은 퀘스트끼리 서로를 가로챈다(실측 오탐 0.82).
        """
        return self.template_score(ctx, search)

    def template_score(self, ctx: Context, search: NormRect) -> float:
        best = 0.0
        for template_name in self.name_templates:
            try:
                template = ctx.templates.load(template_name)
            except TemplateError as exc:
                ctx.log(str(exc))
                continue
            match = find_text(ctx.frame, template, self.match_threshold, search)
            if match is not None:
                best = max(best, match.score)
        return best

    def matches(self, ctx: Context, search: NormRect) -> bool:
        """임계값을 넘는지만 본다. 후보가 하나뿐일 때의 간이 판정."""
        return self.match_score(ctx, search) >= self.match_threshold

    @abc.abstractmethod
    def execute(self, ctx: Context) -> StepResult:
        """퀘스트를 수행한다.

        수행 절차를 끝까지 마쳤으면 ``StepResult.ok()``, 중간에 막히면
        ``StepResult.blocked(사유)`` 를 돌려준다. 화면 복귀는 상태기가
        알아서 하므로 여기서 전투화면으로 돌아올 필요는 없다.
        """
