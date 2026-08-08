"""퀘스트: 쿠키 뽑기 N회 하기.

    퀘스트 1319 · 쿠키 뽑기 10회 하기 · 0/10

절차는 펫 뽑기와 같아서 ``_gacha.TenDrawQuest`` 에 모여 있다.
'10회' 는 쿠키 뽑기권 10장을 쓴다.
"""

from __future__ import annotations

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
            what="퀘스트 이름 글자 줄",
            tip=f"{NUMBER_TIP} {SIZE_TIP}",
        ),
        TemplateSpec(
            name="gacha_draw10",
            label="쿠키 뽑기 10회 버튼",
            where="쿠키 뽑기 화면 (퀘스트창을 누르면 이동)",
            what="가운데 주황색 '10회' 버튼 전체",
            tip="뽑기권이 10장 이상일 때 잡는다. 부족하면 버튼이 청록색 다이아 결제로 바뀌는데, "
                "그 상태를 잡으면 자동화가 다이아를 쓰게 된다.",
        ),
    ]
