"""빈 곳 탭은 X 가 없을 때만 한다.

X 있는 팝업은 빈 곳을 눌러도 닫히지 않는다. 그래서 상태기는 X 가 보이면
빈 곳을 누르지 않고 전투화면 복귀에 맡긴다 — 그쪽이 X 를 누른다.

문제는 **언제 보는가** 였다. 걸음 첫머리에 찍은 프레임에는 아직 팝업이 안
올라와 있고, 1~2초 뒤에야 X 가 나타난다. 그 오래된 프레임만 믿고 누르면
X 가 버젓이 있는 화면을 빈 곳 탭으로 두드리게 된다. 실제 기록(09:31:51)이
그랬다. 그래서 누르기 직전에 화면을 다시 본다.

게임 화면 없이 돈다. 흰 글씨도 빨간 X 도 색으로만 판별하므로 칠해서 만든다.
"""

from __future__ import annotations

import threading

import numpy as np
import pytest

from ccc.anchors import NAV_CLOSE, QUEST_PANEL, QUEST_PANEL_SAMPLE, SAFE_TAP, AnchorSet
from ccc.context import Context
from ccc.geometry import NormRect
from ccc.notify import Notifier
from ccc.quest import (
    BattleScreenNavigator,
    QuestMachine,
    QuestPanelReader,
    QuestRegistry,
    StablePanelReader,
)
from ccc.vision import TemplateStore

from .conftest import DEVICE, TEMPLATE_DIR, FakeAdbClient

pytestmark = pytest.mark.no_frames

WIDTH, HEIGHT = 506, 898
RED = (40, 40, 220)
"""X 버튼 색 (BGR). 판별기가 보는 빨강 범위 한가운데다."""


def frame(*, close_button: bool) -> np.ndarray:
    """퀘스트창은 읽을 수 없고, X 만 있고 없고가 다른 화면.

    바탕은 어두운 회색이다. 흰 글씨가 없으니 퀘스트창은 '없음' 으로 읽히고,
    색 표본도 어느 쪽으로도 기울지 않아 판정불가가 된다 — 빈 곳 탭 규칙이
    걸리는 바로 그 상황이다.
    """
    image = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    image[:] = (30, 30, 30)
    if close_button:
        _fill(image, AnchorSet().get(NAV_CLOSE), RED)
    return image


def _fill(image: np.ndarray, area: NormRect, color: tuple[int, int, int]) -> None:
    box = area.scaled(WIDTH, HEIGHT)
    image[box.y : box.bottom, box.x : box.right] = color


class ScriptedFrames:
    """정해진 순서대로 화면을 흘려 준다. 끝나면 마지막 화면을 되풀이한다."""

    def __init__(self, frames: list[np.ndarray]):
        self.frames = frames
        self.index = 0

    def grab(self) -> np.ndarray:
        image = self.frames[min(self.index, len(self.frames) - 1)]
        self.index += 1
        return image


def build(frames: list[np.ndarray]) -> tuple[QuestMachine, Context, FakeAdbClient]:
    anchors = AnchorSet()
    client = FakeAdbClient()
    ctx = Context(
        client,  # type: ignore[arg-type]
        TemplateStore(TEMPLATE_DIR),
        threading.Event(),
        anchors=anchors,
        notifier=Notifier(enabled=False),
        frame_provider=ScriptedFrames(frames).grab,
    )
    machine = QuestMachine(
        StablePanelReader(
            QuestPanelReader(
                anchors.get(QUEST_PANEL_SAMPLE), panel_area=anchors.get(QUEST_PANEL)
            ),
            required=2,
        ),
        BattleScreenNavigator(anchors.get(NAV_CLOSE)),
        QuestRegistry(),
        anchors.get(QUEST_PANEL),
        anchors.get(SAFE_TAP),
        Notifier(enabled=False),
    )
    machine.start()
    return machine, ctx, client


def tapped_in(client: FakeAdbClient, area: NormRect) -> bool:
    for x, y in client.taps:
        nx, ny = x / (DEVICE.width - 1), y / (DEVICE.height - 1)
        if area.x <= nx <= area.x + area.w and area.y <= ny <= area.y + area.h:
            return True
    return False


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(Context, "sleep", lambda self, seconds: True)


def test_X_가_없으면_빈_곳을_누른다():
    machine, ctx, client = build([frame(close_button=False)])

    ctx.set_frame(ctx.refresh())
    machine.tick(ctx)

    assert tapped_in(client, AnchorSet().get(SAFE_TAP)), "빈 곳을 누르지 않았습니다"


def test_누르기_직전에_X_가_떴으면_누르지_않는다():
    """걸음을 시작할 때는 X 가 없었지만 그새 팝업이 올라온 경우."""
    machine, ctx, client = build([frame(close_button=False), frame(close_button=True)])

    ctx.set_frame(ctx.refresh())  # X 없는 화면으로 걸음을 시작한다
    machine.tick(ctx)  # 누르기 직전에 다시 보면 X 가 있다

    assert not client.taps, f"X 가 있는데 눌렀습니다: {client.taps}"


def test_늦게_뜬_X_는_판독_실패로_세지_않는다():
    """헛누른 것이 아니니 '몇 번 못 읽었다' 는 셈에도 들어가지 않는다."""
    machine, ctx, _ = build([frame(close_button=False), frame(close_button=True)])

    ctx.set_frame(ctx.refresh())
    machine.tick(ctx)

    assert machine._unknown_reads == 0
