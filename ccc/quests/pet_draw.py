"""퀘스트: 펫 뽑기 N회 하기.

    퀘스트 1320 · 펫 뽑기 10회 하기 · 0/10

절차는 쿠키 뽑기와 같아서 ``_gacha.TenDrawQuest`` 에 모여 있다.
'10회' 는 펫 뽑기권 10장을 쓴다.

이름이 "쿠키 뽑기 10회 하기" 와 뒷부분이 완전히 같아 템플릿만으로는 서로를
가로챌 수 있다(실측 오탐 0.82). 상태기가 가장 높은 점수 하나만 고르고
2등과 충분히 벌어졌을 때만 확정하므로 갈린다(실측 여유 0.13~0.18).
"""

from __future__ import annotations

from ..geometry import NormRect
from ..templates_spec import NUMBER_TIP, SIZE_TIP, TemplateSpec
from ._gacha import TenDrawQuest


class PetDraw(TenDrawQuest):
    name = "펫 뽑기"
    name_templates = ["quest_pet_draw"]
    draw_template = "gacha_pet_draw10"

    template_group = "퀘스트 - 펫 뽑기"
    setup_order = 30
    template_specs = [
        TemplateSpec(
            name="quest_pet_draw",
            label="퀘스트 창",
            where="전투화면에 '펫 뽑기 N회 하기' 퀘스트가 회색으로 떠 있을 때",
            what="'펫 뽑기' 까지만. 'N회 하기' 는 자른다",
            tips=(
                NUMBER_TIP,
                SIZE_TIP,
                "쿠키 뽑기와 이름이 비슷하다. 뜬 뒤 '퀘스트 판별 점검' 으로 둘이 갈리는지 본다.",
            ),
            # 쿠키 뽑기 쪽 주석 참고. 'N회 하기' 가 둘의 공통 부분이라 반드시 뺀다.
            default_area=NormRect(0.7602, 0.5432, 0.0769, 0.0177),
        ),
        TemplateSpec(
            name="gacha_pet_draw10",
            label="펫 뽑기 10회 버튼",
            where="펫 뽑기 화면 (아래 '펫 뽑기' 탭)",
            what="가운데 주황색 '10회' 버튼 전체",
            tips=("펫 뽑기권이 10장 이상일 때 잡는다.",),
            default_area=NormRect(0.3500, 0.7802, 0.2963, 0.0646),
        ),
    ]
