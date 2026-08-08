"""필요한 템플릿이 무엇이고 어떻게 잘라야 하는지에 대한 선언.

게임 화면 이미지는 저작물이라 저장소에 넣지 않는다. 대신 각 퀘스트와 모듈이
"나는 이런 템플릿이 필요하고, 어느 화면에서 무엇을 잘라야 한다"를 선언하고,
첫 실행 때 캡처 마법사가 그 안내를 따라가며 사용자가 직접 뜨게 한다.

각자 자기 화면에서 뜨는 편이 정확하기도 하다. 해상도·언어·보유 아이템이
사람마다 다르기 때문이다.

다만 **어디를 잘라야 하는지는 사람마다 같다**. 게임 UI 배치는 9:16 이면
해상도와 무관하게 같은 자리에 있기 때문이다. 그래서 각 선언에 실측해 둔
``default_area`` 를 붙여 두고, 마법사가 그 자리를 미리 잡아서 보여 준다.
사용자는 맞는지 보고 그대로 저장하거나 조금만 끌어 고치면 된다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import NormRect


@dataclass(frozen=True)
class TemplateSpec:
    """템플릿 하나를 뜨는 방법."""

    name: str
    """저장될 이름. 코드가 이 이름으로 불러 쓴다."""

    label: str
    """사람이 읽을 이름."""

    where: str
    """어느 화면에서 뜨는지."""

    what: str
    """그 화면에서 무엇을 드래그해야 하는지."""

    tips: tuple[str, ...] = ()
    """놓치기 쉬운 주의사항. 하나씩 따로 적는다 — 화면에 한 줄씩 나눠 띄운다."""

    default_area: NormRect | None = None
    """미리 잡아 둘 영역. 마법사가 이 자리를 기본 선택으로 띄운다.

    9:16 화면에서 실측한 값이다. 게임 UI 는 해상도가 달라도 같은 비율 자리에
    있으므로 대개 그대로 맞는다. 없으면 사용자가 처음부터 드래그한다.
    """

    def guide_lines(self) -> list[str]:
        """캡처 화면에 한 줄씩 띄울 안내."""
        return [f"화면 · {self.where}", f"대상 · {self.what}", *(f"주의 · {t}" for t in self.tips)]

    def describe(self) -> str:
        return "\n".join([f"[{self.label}]  ({self.name})", *self.guide_lines()])


NUMBER_TIP = "숫자와 퀘스트 번호는 빼고 잡는다 (횟수가 바뀌어도 걸리도록)."

SIZE_TIP = "너무 작게 자르지 않는다. 창을 줄이면 매칭이 무너진다."
