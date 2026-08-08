"""퀘스트 자동화 상태기.

    대기 ─(시작)→ 퀘스트확인 ─┬─ 골드 ─→ 퀘스트완료 ─(보상 수령)─┐
                              │                                   │
                              └─ 회색 ─→ 퀘스트진행               │
                                          판별 → 수행 → 완료확인  │
                                                                  │
                              ←───────────────────────────────────┘

한 번의 ``tick`` 은 한 걸음만 진행한다. 상태를 물고 다음 프레임에서 이어
가므로 엔진 루프를 오래 붙잡지 않고, 사용자가 언제든 대기로 되돌릴 수 있다.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from ..context import Context
from ..geometry import NormRect
from ..notify import Notifier
from .definition import QuestDefinition
from .diagnostics import save_snapshot
from .navigator import BattleScreenNavigator
from .panel import PanelReading, StablePanelReader
from .registry import QuestRegistry
from .states import MainState, PanelState, ProgressStep

log = logging.getLogger(__name__)

MAX_CONSECUTIVE_FAILURES = 3

MAX_CONSECUTIVE_RETRIES = 10
"""``StepResult.retry`` 로 돌아온 실패를 이만큼까지 봐 준다.

기다리면 풀릴 일(오븐 Auto 가 아직 안 보인다 같은)에는 사람을 부르지 않는다.
다 쓰면 멈추지 않고 '퀘스트확인' 으로 돌아가 처음부터 다시 본다.
"""

MIN_SCORE_MARGIN = 0.08
"""1등이 2등보다 이만큼은 앞서야 퀘스트를 확정한다.

실측: '펫 뽑기 10회 하기' 화면에서 펫 템플릿 1.00 / 쿠키 템플릿 0.82.
뒷부분이 같은 퀘스트끼리는 이 정도 차이로 갈린다.
"""

CLAIM_TIMEOUT = 4.0
"""보상을 누른 뒤 퀘스트창이 다음 것으로 바뀌기를 기다리는 제한 시간.

고정으로 재우면 빨리 바뀌어도 그만큼 손해다. 창이 더 이상 황금이 아니게
되면 바로 넘어간다.
"""

UNKNOWN_QUEST_RETRY = 2.0
"""등록되지 않은 퀘스트를 만났을 때 다시 확인하기까지 기다리는 시간.

퀘스트창을 잠깐 잘못 읽었거나, 마침 퀘스트가 바뀌는 중일 수 있다. 한 번
못 알아봤다고 바로 멈추면 그런 순간에도 자동화가 끊긴다.
"""

UNKNOWN_QUEST_TIMEOUT = 30.0
"""이만큼 계속 못 알아보면 한 라운드가 끝난 것으로 보고 퀘스트확인부터 다시 본다.

퀘스트창을 잘못 읽고 있었다면 확인 단계를 다시 밟는 것만으로 풀린다.
"""

MAX_UNKNOWN_ROUNDS = 3
"""위 라운드를 이만큼 되풀이해도 못 알아보면 그때는 알림 후 대기로 멈춘다.

세 번을 처음부터 다시 봤는데도 모르겠다면 화면을 잘못 읽는 게 아니라 정말
등록되지 않은 퀘스트다.
"""

MAX_UNKNOWN_READS = 20
"""퀘스트창을 이만큼 연속으로 못 읽으면 멈추고 알린다."""

UNKNOWN_TAP_INTERVAL = 4
"""판독 실패가 이만큼 쌓일 때마다 빈 곳을 한 번 탭한다.

레벨업 연출처럼 X 버튼 없이 '화면을 탭하세요' 로 넘기는 전체화면 연출이
퀘스트창을 가리면, 전투화면으로 인식되면서도 퀘스트창은 계속 안 보인다.
버튼이 없는 지점을 눌러 연출을 넘긴다. 전투화면에서 눌려도 아무 일이
없는 자리라 헛탭의 부작용이 없다.
"""


class QuestMachine:
    def __init__(
        self,
        panel_reader: StablePanelReader,
        navigator: BattleScreenNavigator,
        registry: QuestRegistry,
        panel_area: NormRect,
        safe_tap_area: NormRect,
        notifier: Notifier,
        max_failures: int = MAX_CONSECUTIVE_FAILURES,
        max_retries: int = MAX_CONSECUTIVE_RETRIES,
        max_unknown_reads: int = MAX_UNKNOWN_READS,
        unknown_tap_interval: int = UNKNOWN_TAP_INTERVAL,
        unknown_quest_retry: float = UNKNOWN_QUEST_RETRY,
        unknown_quest_timeout: float = UNKNOWN_QUEST_TIMEOUT,
        max_unknown_rounds: int = MAX_UNKNOWN_ROUNDS,
        on_change: Callable[[str], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._panel_reader = panel_reader
        self._navigator = navigator
        self._registry = registry
        self._panel_area = panel_area
        self._safe_tap_area = safe_tap_area
        self._notifier = notifier
        self._max_failures = max_failures
        self._max_retries = max_retries
        self._max_unknown_reads = max_unknown_reads
        self._unknown_tap_interval = max(1, unknown_tap_interval)
        self._unknown_quest_retry = unknown_quest_retry
        self._unknown_quest_timeout = unknown_quest_timeout
        self._max_unknown_rounds = max(1, max_unknown_rounds)
        self._on_change = on_change
        self._clock = clock

        self.state = MainState.IDLE
        self.step = ProgressStep.IDENTIFY
        self.current_quest: QuestDefinition | None = None
        self._failures = 0
        self._retries = 0
        self._unknown_reads = 0
        self._unknown_quest_since: float | None = None
        self._unknown_rounds = 0
        self._idle_requested = False
        self._last_notice = ""

    # ------------------------------------------------------------------
    # 외부 조작
    # ------------------------------------------------------------------
    @property
    def status_text(self) -> str:
        if self.state is MainState.PROGRESS:
            quest = self.current_quest.label if self.current_quest else "미판별"
            return f"{self.state.value} · {self.step.value} · {quest}"
        return self.state.value

    def start(self) -> None:
        """대기 상태에서 자동화를 시작한다."""
        self._idle_requested = False
        self._failures = 0
        self._retries = 0
        self._unknown_reads = 0
        self._unknown_quest_since = None
        self._unknown_rounds = 0
        self.current_quest = None
        self._panel_reader.reset()
        self._enter(MainState.CHECK)

    def to_idle(self, reason: str = "") -> None:
        # 이 메서드는 UI 스레드가 부른다. 그때 엔진 스레드는 quest.execute 안에서
        # 버튼이 나타나기를 기다리는 중일 수 있고, 그게 끝나면 제 걸음을 마무리하며
        # CHECK 로 되돌린다. 그러면 대기를 눌러도 자동화가 계속 돈다.
        # 요청을 깃발로 남겨 두어, 진행 중이던 걸음이 상태를 되돌리지 못하게 한다.
        self._idle_requested = True
        self._retries = 0
        self._unknown_reads = 0
        self._unknown_quest_since = None
        self._unknown_rounds = 0
        self.current_quest = None
        self._panel_reader.reset()
        self._enter(MainState.IDLE, reason)

    # ------------------------------------------------------------------
    # 한 걸음
    # ------------------------------------------------------------------
    def tick(self, ctx: Context) -> None:
        if self.state is MainState.IDLE:
            return
        handler = {
            MainState.CHECK: self._on_check,
            MainState.PROGRESS: self._on_progress,
            MainState.COMPLETE: self._on_complete,
        }[self.state]
        handler(ctx)

    # ------------------------------------------------------------------
    # 상태별 처리
    # ------------------------------------------------------------------
    def _on_check(self, ctx: Context) -> None:
        if not self._ensure_battle_screen(ctx):
            return

        reading = self._panel_reader.read(ctx.frame)
        if reading.state is PanelState.GOLD:
            self._unknown_reads = 0
            self._quest_recognized()
            ctx.log(f"퀘스트 완료 상태 감지 ({reading.detail})")
            self._enter(MainState.COMPLETE)
        elif reading.state is PanelState.GRAY:
            self._unknown_reads = 0
            ctx.log(f"퀘스트 진행 필요 ({reading.detail})")
            self.step = ProgressStep.IDENTIFY
            self._enter(MainState.PROGRESS)
        else:
            self._on_unknown_reading(ctx, reading)

    def _on_progress(self, ctx: Context) -> None:
        if self.step is ProgressStep.IDENTIFY:
            self._identify(ctx)
        elif self.step is ProgressStep.EXECUTE:
            self._execute(ctx)
        else:
            self._verify(ctx)

    def _on_complete(self, ctx: Context) -> None:
        if not self._ensure_battle_screen(ctx):
            return

        ctx.log("퀘스트 보상을 수령합니다.")
        ctx.tap_rect(self._panel_area)
        # 수령하면 창이 다음 퀘스트로 바뀐다. 바뀌는 것을 보고 넘어간다.
        ctx.wait_until(self._is_not_gold, CLAIM_TIMEOUT)

        self._failures = 0
        self.current_quest = None
        self._panel_reader.reset()
        self._enter(MainState.CHECK)

    def _is_not_gold(self, frame) -> bool:
        """퀘스트창이 더 이상 완료 상태가 아닌지. 보상 수령이 반영됐다는 신호다."""
        return self._panel_reader.reader.read(frame).state is not PanelState.GOLD

    # ------------------------------------------------------------------
    # 퀘스트진행 세부 단계
    # ------------------------------------------------------------------
    def _identify(self, ctx: Context) -> None:
        matched = self._find_definition(ctx)
        if matched is None:
            self._on_unknown_quest(ctx)
            return

        self._quest_recognized()
        if matched is not self.current_quest:
            self._failures = 0  # 퀘스트가 바뀌면 실패 카운터를 리셋한다
            self._retries = 0
        self.current_quest = matched
        ctx.log(f"퀘스트 판별: {matched.label}")
        self.step = ProgressStep.EXECUTE
        self._announce()

    def _on_unknown_quest(self, ctx: Context) -> None:
        """알아보지 못한 퀘스트.

        2초마다 다시 본다. 30초를 채우면 한 라운드가 끝난 것으로 보고 시계를
        0 으로 돌린 뒤 퀘스트확인부터 다시 밟는다. 퀘스트창을 잘못 읽고 있었던
        거라면 확인 단계를 다시 거치는 것만으로 풀린다. 그렇게 세 라운드를
        되풀이해도 모르겠다면 그때는 정말 등록되지 않은 퀘스트다.
        """
        now = self._clock()
        if self._unknown_quest_since is None:
            self._unknown_quest_since = now

        elapsed = now - self._unknown_quest_since
        if elapsed >= self._unknown_quest_timeout:
            self._unknown_rounds += 1
            if self._unknown_rounds >= self._max_unknown_rounds:
                saved = save_snapshot(ctx.frame, self._panel_area, "unknown-quest")
                hint = f" 화면을 저장했습니다: {saved}" if saved else ""
                self._abort(
                    ctx,
                    f"{self._unknown_quest_timeout:.0f}초씩 {self._unknown_rounds}번을 "
                    f"다시 봤지만 퀘스트를 알아보지 못했습니다. 지시문을 추가해 주세요.{hint}",
                )
                return

            ctx.log(
                f"{self._unknown_quest_timeout:.0f}초 동안 알아보지 못했습니다 "
                f"({self._unknown_rounds}/{self._max_unknown_rounds}). "
                "퀘스트확인부터 다시 봅니다."
            )
            self._unknown_quest_since = None
            self._panel_reader.reset()
            self._enter(MainState.CHECK)
            return

        ctx.log(
            f"등록되지 않은 퀘스트입니다. {self._unknown_quest_retry:.0f}초 뒤 다시 확인합니다 "
            f"({elapsed:.0f}/{self._unknown_quest_timeout:.0f}초, "
            f"{self._unknown_rounds + 1}/{self._max_unknown_rounds}회차)"
        )
        if not ctx.sleep(self._unknown_quest_retry):
            return
        self._panel_reader.reset()
        self._enter(MainState.CHECK)

    def _execute(self, ctx: Context) -> None:
        quest = self.current_quest
        if quest is None:
            self.step = ProgressStep.IDENTIFY
            return

        ctx.log(f"퀘스트 수행 시작: {quest.label}")
        result = quest.execute(ctx)
        if result.success:
            self._failures = 0
            self._retries = 0
            self.step = ProgressStep.VERIFY
            self._announce()
            return

        if result.retryable:
            self._on_retryable(ctx, quest, result.reason)
            return

        self._failures += 1
        ctx.log(f"진행 불가 ({self._failures}/{self._max_failures}): {result.reason}")
        if self._failures >= self._max_failures:
            # 막힌 화면을 남긴다. 드물게만 나오는 팝업은 사람이 다시 만들어
            # 내기 어려워서, 막히는 그 순간을 붙잡아 두지 않으면 고칠 수 없다.
            saved = save_snapshot(ctx.frame, self._panel_area, "quest-blocked")
            hint = f" 화면을 저장했습니다: {saved}" if saved else ""
            self._abort(
                ctx,
                f"'{quest.label}' 을(를) {self._max_failures}번 연속 진행하지 못했습니다: "
                f"{result.reason}.{hint}",
            )
            return
        self._panel_reader.reset()
        self._enter(MainState.CHECK)

    def _on_retryable(self, ctx: Context, quest: QuestDefinition, reason: str) -> None:
        """기다리면 풀릴 실패. 사람을 부르지 않고 처음부터 다시 본다."""
        self._retries += 1
        ctx.log(f"아직 못 합니다 ({self._retries}/{self._max_retries}): {reason}")
        if self._retries >= self._max_retries:
            ctx.log(
                f"'{quest.label}' 을(를) {self._max_retries}번 시도했습니다. "
                "퀘스트확인부터 다시 봅니다."
            )
            self._retries = 0
            self.current_quest = None
        self._panel_reader.reset()
        self._enter(MainState.CHECK)

    def _verify(self, ctx: Context) -> None:
        if not self._ensure_battle_screen(ctx):
            return

        reading = self._panel_reader.read(ctx.frame)
        if reading.state is PanelState.GOLD:
            self._unknown_reads = 0
            self._quest_recognized()
            ctx.log(f"퀘스트 완료 확인 ({reading.detail})")
            self._enter(MainState.COMPLETE)
        elif reading.state is PanelState.GRAY:
            self._unknown_reads = 0
            ctx.log(f"아직 완료되지 않았습니다 ({reading.detail}). 다시 확인합니다.")
            self._panel_reader.reset()
            self._enter(MainState.CHECK)
        else:
            self._on_unknown_reading(ctx, reading)

    # ------------------------------------------------------------------
    # 공통
    # ------------------------------------------------------------------
    def _quest_recognized(self) -> None:
        """퀘스트를 알아봤다. 못 알아본 시간을 다시 0 부터 센다.

        판별에 성공했을 때뿐 아니라 완료(황금)를 읽었을 때도 부른다. 그러지
        않으면 중간에 보상을 받고 넘어가도 예전에 못 알아본 시각이 그대로
        남아, 다음에 모르는 퀘스트가 한 번만 나와도 곧바로 상한을 넘긴다.
        """
        self._unknown_quest_since = None
        self._unknown_rounds = 0

    def _on_unknown_reading(self, ctx: Context, reading: PanelReading) -> None:
        """퀘스트창을 못 읽었을 때.

        잠깐이면 그냥 넘긴다. 계속되면 전체화면 연출이 가리고 있을 수 있으니
        빈 곳을 눌러 넘겨 보고, 그래도 안 되면 사용자에게 알리고 멈춘다.
        """
        self._unknown_reads += 1
        if self._unknown_reads < self._max_unknown_reads:
            if self._unknown_reads % self._unknown_tap_interval == 0:
                self._tap_through_overlay(ctx, reading)
            return
        saved = save_snapshot(ctx.frame, self._panel_area, "unreadable-panel")
        hint = f" 화면을 저장했습니다: {saved}" if saved else ""
        self._abort(
            ctx,
            "퀘스트창을 계속 읽지 못했습니다. 영역 보정이 필요하거나 "
            f"빈 곳 탭으로 넘어가지 않는 화면일 수 있습니다.{hint}",
        )

    def _tap_through_overlay(self, ctx: Context, reading: PanelReading) -> None:
        ctx.log(
            f"퀘스트창이 가려진 듯해 빈 곳을 눌러 넘깁니다 "
            f"({self._unknown_reads}/{self._max_unknown_reads}, {reading.detail})"
        )
        ctx.tap_rect(self._safe_tap_area)
        if ctx.sleep(1.0):
            ctx.refresh()
        self._panel_reader.reset()

    def _ensure_battle_screen(self, ctx: Context) -> bool:
        result = self._navigator.return_to_battle(ctx)
        if result.reached:
            return True
        if ctx.stopping:
            return False
        self._abort(ctx, f"전투화면으로 돌아가지 못했습니다: {result.reason}")
        return False

    def _find_definition(self, ctx: Context) -> QuestDefinition | None:
        """가장 잘 맞는 퀘스트 하나를 고른다.

        먼저 임계값을 넘는 것을 채택하면, 뒷부분이 같은 퀘스트끼리
        ("쿠키 뽑기 10회 하기" / "펫 뽑기 10회 하기") 서로를 가로챈다.
        전부 점수를 매겨 1등을 고르고, 2등과 충분히 벌어졌을 때만 확정한다.
        """
        scored = self._score_all(ctx)
        if not scored:
            return None

        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best = scored[0]
        if len(scored) > 1:
            runner_up_score, runner_up = scored[1]
            if best_score - runner_up_score < MIN_SCORE_MARGIN:
                ctx.log(
                    f"판별이 모호합니다: {best.label} {best_score:.2f} vs "
                    f"{runner_up.label} {runner_up_score:.2f}"
                )
                return None

        log.debug("퀘스트 판별 점수: %s", [(d.label, round(s, 3)) for s, d in scored])
        return best

    def _score_all(self, ctx: Context) -> list[tuple[float, QuestDefinition]]:
        scored: list[tuple[float, QuestDefinition]] = []
        for definition in self._registry.definitions:
            try:
                score = definition.match_score(ctx, self._panel_area)
            except Exception:
                log.exception("퀘스트 판별 중 오류: %s", definition.label)
                continue
            if score > 0:
                scored.append((score, definition))
        return scored

    def _abort(self, ctx: Context, reason: str) -> None:
        ctx.log(f"⚠ {reason}")
        self._notifier.send(reason)
        self.to_idle(reason)

    def _enter(self, state: MainState, reason: str = "") -> None:
        if self._idle_requested and state is not MainState.IDLE:
            # 대기 요청이 들어온 뒤에는 진행 중이던 걸음이 상태를 되돌리지 못한다.
            return
        if state is not self.state:
            log.info("상태 전이: %s → %s%s", self.state.value, state.value,
                     f" ({reason})" if reason else "")
        self.state = state
        self._announce()

    def _announce(self) -> None:
        text = self.status_text
        if text != self._last_notice:
            self._last_notice = text
            if self._on_change:
                self._on_change(text)
