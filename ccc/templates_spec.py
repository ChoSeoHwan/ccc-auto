"""필요한 템플릿이 무엇이고 어떻게 잘라야 하는지에 대한 선언.

게임 화면 이미지는 저작물이라 저장소에 넣지 않는다. 대신 각 퀘스트와 모듈이
"나는 이런 템플릿이 필요하고, 어느 화면에서 무엇을 잘라야 한다"를 선언하고,
첫 실행 때 캡처 마법사가 그 안내를 따라가며 사용자가 직접 뜨게 한다.

각자 자기 화면에서 뜨는 편이 정확하기도 하다. 해상도·언어·보유 아이템이
사람마다 다르기 때문이다.
"""

from __future__ import annotations

from dataclasses import dataclass


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

    tip: str = ""
    """놓치기 쉬운 주의사항."""

    def describe(self) -> str:
        lines = [f"[{self.label}]  ({self.name})", f"  화면: {self.where}", f"  대상: {self.what}"]
        if self.tip:
            lines.append(f"  주의: {self.tip}")
        return "\n".join(lines)


NUMBER_TIP = "숫자와 '퀘스트 1319' 같은 번호는 빼고 잡는다. 횟수가 달라져도 걸리게 하기 위해서다."

SIZE_TIP = (
    "너무 작게 자르면 창을 줄여 쓸 때 매칭이 무너진다. "
    "이름 줄이 짧으면 아래 줄까지 함께 감싸 넉넉히 잡는다."
)
