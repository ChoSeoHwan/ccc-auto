"""퀘스트: 가방에서 상자 사용하기.

    퀘스트 1317 · 가방에서 상자 1개 사용하기 · 0/1

이름 템플릿은 두 줄("가방에서 상자 N개" + "사용하기")을 한 덩어리로 잡았다.
한 줄만 잡으면 템플릿이 작아져서, 창을 줄여 쓸 때(실제 운영 해상도는 원본의
절반 정도다) 매칭이 무너진다. 개수 숫자가 함께 들어가지만 전체 넓이에서
차지하는 몫이 작아 다른 개수에서도 걸린다.

수행 절차 (실측으로 확인한 순서)
    1. 퀘스트창을 누른다.                → 가방 UI 가 열린다
    2. 가방에서 단단한 보물상자를 누른다. → 상세 팝업이 뜬다
    3. 팝업의 '사용하기' 를 누른다.       → '보상 획득!' 팝업이 뜬다

3단계 뒤의 보상 팝업은 닫기(X) 버튼이 있어서 상태기가 알아서 치운다.
수량은 팝업 기본값(보유량 전체)을 그대로 쓴다.
"""

from __future__ import annotations

from .. import anchors as anchor_names
from ..context import Context
from ..geometry import NormRect
from ..quest.definition import QuestDefinition, StepResult
from ..quest.navigator import BattleScreenNavigator
from ..templates_spec import NUMBER_TIP, SIZE_TIP, TemplateSpec
from ..vision import TemplateError

BOX_TEMPLATE = "bag_treasure_box"
USE_TEMPLATE = "bag_use_button"

BAG_GRID = NormRect(0.02, 0.53, 0.96, 0.19)
"""가방의 아이템 칸이 놓이는 자리. 상자는 목록 위치가 바뀔 수 있어 여기서 찾는다."""

USE_SEARCH = NormRect(0.15, 0.35, 0.70, 0.15)
"""상세 팝업의 '사용하기' 버튼 자리. 실측 중심 (0.499, 0.444)."""

MATCH_THRESHOLD = 0.75

BAG_TIMEOUT = 6.0
"""퀘스트창을 누르고 가방이 열리기까지 기다릴 상한."""

POPUP_TIMEOUT = 5.0
"""상자를 누르고 상세 팝업이 뜨기까지 한 번에 기다릴 상한."""

USE_ATTEMPTS = 3
"""'사용하기' 버튼을 못 찾았을 때 다시 볼 횟수.

한 번 못 찾았다고 바로 접으면, 팝업이 늦게 뜨는 순간마다 퀘스트가 막힌다.
"""

USE_RETRY_INTERVAL = 1.0
"""다시 보기까지 쉴 시간."""

USE_TIMEOUT = 5.0
"""'사용하기' 를 누르고 결과 화면이 뜨기까지 기다릴 상한."""


class UseBoxFromBag(QuestDefinition):
    name = "가방에서 상자 사용하기"
    name_templates = ["quest_use_box"]

    template_group = "퀘스트 - 상자 아이템 사용"
    setup_order = 10
    template_specs = [
        TemplateSpec(
            name="quest_use_box",
            label="퀘스트 창",
            where="전투화면에 '가방에서 상자 N개 사용하기' 퀘스트가 회색으로 떠 있을 때",
            what="퀘스트 이름 두 줄을 함께",
            tips=(NUMBER_TIP, SIZE_TIP),
            default_area=NormRect(0.7593, 0.5354, 0.1907, 0.0339),
        ),
        TemplateSpec(
            name=BOX_TEMPLATE,
            label="가방 내 보물상자 아이콘",
            where="퀘스트창을 눌러 연 가방 UI",
            what="쓰려는 상자 아이콘 그림",
            tips=("칸 아래의 보유 개수 숫자는 빼고 그림만 잡는다. 개수가 줄면 안 맞는다.",),
            default_area=NormRect(0.0900, 0.5620, 0.1340, 0.0580),
        ),
        TemplateSpec(
            name=USE_TEMPLATE,
            label="보물상자 사용하기 버튼",
            where="가방에서 상자를 누르면 뜨는 상세 팝업",
            what="주황색 '사용하기' 버튼 전체",
            default_area=NormRect(0.2565, 0.4177, 0.4852, 0.0531),
        ),
    ]

    def execute(self, ctx: Context) -> StepResult:
        ctx.log("퀘스트창을 눌러 가방을 엽니다.")
        ctx.tap_rect(ctx.anchors.get(anchor_names.QUEST_PANEL))

        try:
            box = ctx.wait_for_template(BOX_TEMPLATE, BAG_TIMEOUT, MATCH_THRESHOLD, BAG_GRID)
            if box is None:
                return StepResult.blocked("가방에서 보물상자를 찾지 못했습니다")

            ctx.log(f"보물상자 선택 (일치도 {box.score:.2f})")
            ctx.tap_match(box)

            use = self._find_use_button(ctx)
        except TemplateError as exc:
            return StepResult.blocked(str(exc))

        if use is None:
            return StepResult.blocked(
                f"상세 팝업의 '사용하기' 버튼을 {USE_ATTEMPTS}번 확인했지만 찾지 못했습니다"
            )

        ctx.log(f"'사용하기' 클릭 (일치도 {use.score:.2f})")
        ctx.tap_match(use)

        # 보상 팝업이 뜨면(닫기 버튼이 생기면) 끝난 것이다. 상태기가 마저 치운다.
        navigator = BattleScreenNavigator(ctx.anchors.get(anchor_names.NAV_CLOSE))
        ctx.wait_until(navigator.has_close_button, USE_TIMEOUT)
        return StepResult.ok()

    # ------------------------------------------------------------------
    def _find_use_button(self, ctx: Context):
        """'사용하기' 버튼을 최대 ``USE_ATTEMPTS`` 번 확인한다.

        상세 팝업이 뜨는 데 걸리는 시간이 들쭉날쭉해서, 한 번의 상한만으로는
        늦게 뜨는 날에 그대로 막힌다. 못 찾으면 1초 쉬고 다시 본다.
        """
        for attempt in range(1, USE_ATTEMPTS + 1):
            match = ctx.wait_for_template(
                USE_TEMPLATE, POPUP_TIMEOUT, MATCH_THRESHOLD, USE_SEARCH
            )
            if match is not None:
                return match
            if attempt < USE_ATTEMPTS:
                ctx.log(
                    f"'사용하기' 버튼이 아직 안 보입니다 ({attempt}/{USE_ATTEMPTS}). "
                    f"{USE_RETRY_INTERVAL:.0f}초 뒤 다시 확인합니다."
                )
                if not ctx.sleep(USE_RETRY_INTERVAL):
                    return None
        return None
