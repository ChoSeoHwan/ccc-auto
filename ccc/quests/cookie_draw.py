"""퀘스트: 쿠키 뽑기 N회 하기.

    퀘스트 1319 · 쿠키 뽑기 10회 하기 · 0/10

절차는 펫 뽑기와 같아서 ``_gacha.TenDrawQuest`` 에 모여 있다.
'10회' 는 쿠키 뽑기권 10장을 쓴다.
"""

from __future__ import annotations

from ..geometry import NormRect
from ..templates_spec import NUMBER_TIP, SIZE_TIP, TemplateSpec
from ._gacha import TenDrawQuest


class CookieDraw(TenDrawQuest):
    name = "쿠키 뽑기"
    name_templates = ["quest_cookie_draw"]
    draw_template = "gacha_draw10"

    template_specs = [
        TemplateSpec(
            name="quest_cookie_draw",
            label="퀘스트 이름 · 쿠키 뽑기",
            where="전투화면에 '쿠키 뽑기 N회 하기' 퀘스트가 회색으로 떠 있을 때",
            what="'쿠키 뽑기' 까지만. 'N회 하기' 는 자른다",
            tips=(NUMBER_TIP, SIZE_TIP),
            # '10회 하기' 를 빼면 펫 뽑기와의 여유가 0.109 -> 0.254 로 벌어진다.
            # 뒷부분이 둘이 완전히 같아서, 넣어 두면 펫 템플릿도 같이 높은 점수를 받는다.
            default_area=NormRect(0.7611, 0.5432, 0.0935, 0.0177),
        ),
        TemplateSpec(
            name="gacha_draw10",
            label="쿠키 뽑기 10회 버튼",
            where="쿠키 뽑기 화면 (퀘스트창을 누르면 이동)",
            what="가운데 주황색 '10회' 버튼 전체",
            tips=(
                "뽑기권이 10장 이상일 때 잡는다.",
                "부족하면 버튼이 청록색 다이아 결제로 바뀐다. 그걸 잡으면 다이아를 쓰게 된다.",
            ),
            default_area=NormRect(0.3500, 0.7802, 0.2963, 0.0599),
        ),
    ]
