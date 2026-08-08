"""퀘스트 자동화 모듈.

엔진과 퀘스트 상태기를 이어 주는 얇은 어댑터다. 실제 판단은 모두
``ccc/quest/`` 안에 있고, 여기서는 매 tick 마다 상태기를 한 걸음 돌린다.
"""

from __future__ import annotations

from .. import anchors as anchor_names
from ..context import Context
from ..quest import (
    BattleScreenNavigator,
    MainState,
    QuestMachine,
    QuestPanelReader,
    QuestRegistry,
    StablePanelReader,
)
from .base import AutomationModule


class QuestAutomation(AutomationModule):
    name = "퀘스트 자동화"
    description = "퀘스트창을 보고 보상 수령과 퀘스트 수행을 반복합니다."
    interval = 0.0
    priority = 50
    exclusive = True
    enabled_by_default = True

    def __init__(self) -> None:
        self.machine: QuestMachine | None = None
        self.registry = QuestRegistry()
        self._status = MainState.IDLE.value

    # ------------------------------------------------------------------
    @property
    def status(self) -> str:
        return self.machine.status_text if self.machine else self._status

    def request_idle(self, reason: str = "사용자 요청") -> None:
        """컨트롤 창의 '대기로 전환' 버튼이 호출한다."""
        if self.machine:
            self.machine.to_idle(reason)

    def request_start(self) -> None:
        if self.machine:
            self.machine.start()

    # ------------------------------------------------------------------
    def setup(self, ctx: Context) -> None:
        self.registry.load(reload=True)
        for name, error in self.registry.errors.items():
            ctx.log(f"⚠ 퀘스트 정의 로드 실패 {name}: {error}")
        ctx.log(
            f"퀘스트 정의 {len(self.registry.definitions)}개: "
            + (", ".join(d.label for d in self.registry.definitions) or "없음")
        )

        panel_area = ctx.anchors.get(anchor_names.QUEST_PANEL)
        reader = StablePanelReader(
            QuestPanelReader(
                ctx.anchors.get(anchor_names.QUEST_PANEL_SAMPLE),
                panel_area=panel_area,
            ),
            required=ctx.option("stable_frames", 2),
        )
        navigator = BattleScreenNavigator(
            ctx.anchors.get(anchor_names.NAV_CLOSE),
            max_clicks=ctx.option("max_close_clicks", 6),
        )
        self.machine = QuestMachine(
            reader,
            navigator,
            self.registry,
            panel_area,
            ctx.anchors.get(anchor_names.SAFE_TAP),
            ctx.notifier,
            max_failures=ctx.option("max_failures", 3),
            max_retries=ctx.option("max_retries", 10),
            max_unknown_reads=ctx.option("max_unknown_reads", 20),
            unknown_quest_retry=ctx.option("unknown_quest_retry", 2.0),
            unknown_quest_timeout=ctx.option("unknown_quest_timeout", 60.0),
            on_change=self._remember_status,
        )
        self.machine.start()

    def check(self, ctx: Context) -> bool:
        return self.machine is not None and self.machine.state is not MainState.IDLE

    def run(self, ctx: Context) -> None:
        assert self.machine is not None
        self.machine.tick(ctx)

    def teardown(self, ctx: Context) -> None:
        if self.machine:
            self.machine.to_idle("자동화 정지")

    # ------------------------------------------------------------------
    def _remember_status(self, status: str) -> None:
        self._status = status
