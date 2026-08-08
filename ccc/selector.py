"""화면 위에 반투명 오버레이를 띄우고 드래그로 영역을 고르는 도구.

- 연결된 모니터마다 오버레이를 하나씩 띄우므로 다중 모니터에서도 동작한다.
- ESC 로 취소.
- 게임 화면 영역 선택과 템플릿 조각 캡처 양쪽에 쓴다.
"""

from __future__ import annotations

import logging
import tkinter as tk

from .capture.screen import list_monitors
from .geometry import Rect

log = logging.getLogger(__name__)

_OVERLAY_ALPHA = 0.35
_ACCENT = "#00d4ff"


class _Overlay:
    """모니터 한 대를 덮는 오버레이 창."""

    def __init__(self, master: tk.Tk, monitor: Rect, index: int, session: "_Session"):
        self.monitor = monitor
        self.index = index
        self.session = session

        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", _OVERLAY_ALPHA)
        except tk.TclError:  # 일부 환경에서는 투명도를 지원하지 않는다
            pass
        self.win.configure(bg="black")
        self.win.geometry(_geometry(monitor))

        self.canvas = tk.Canvas(
            self.win,
            bg="black",
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)

        self.rect_id: int | None = None
        self.label_id: int | None = None

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.win.bind("<Escape>", lambda _e: session.cancel())

        self._start: tuple[int, int] | None = None

    # ------------------------------------------------------------------
    def _on_press(self, event: tk.Event) -> None:
        self._start = (event.x, event.y)
        self._clear()

    def _on_drag(self, event: tk.Event) -> None:
        if self._start is None:
            return
        x1, y1 = self._start
        self._clear()
        self.rect_id = self.canvas.create_rectangle(
            x1, y1, event.x, event.y, outline=_ACCENT, width=2
        )
        width, height = abs(event.x - x1), abs(event.y - y1)
        self.label_id = self.canvas.create_text(
            min(x1, event.x) + 4,
            min(y1, event.y) - 10,
            anchor="sw",
            fill=_ACCENT,
            font=("Helvetica", 13, "bold"),
            text=f"{width} x {height}",
        )

    def _on_release(self, event: tk.Event) -> None:
        if self._start is None:
            return
        x1, y1 = self._start
        self._start = None
        # 캔버스 좌표는 모니터 기준이므로 가상 화면 좌표로 되돌린다.
        rect = Rect.from_corners(
            x1 + self.monitor.x,
            y1 + self.monitor.y,
            event.x + self.monitor.x,
            event.y + self.monitor.y,
        )
        self.session.finish(rect, self.index)

    def _clear(self) -> None:
        for item in (self.rect_id, self.label_id):
            if item is not None:
                self.canvas.delete(item)
        self.rect_id = self.label_id = None


class _Session:
    """오버레이 여러 개가 공유하는 선택 상태."""

    def __init__(self) -> None:
        self.result: tuple[Rect, int] | None = None
        self.overlays: list[_Overlay] = []
        self._done = False

    def finish(self, rect: Rect, monitor_index: int) -> None:
        if rect.is_valid():
            self.result = (rect, monitor_index)
        else:
            log.info("선택 영역이 너무 작아 취소했습니다: %s", rect)
        self.close()

    def cancel(self) -> None:
        self.result = None
        self.close()

    def close(self) -> None:
        if self._done:
            return
        self._done = True
        for overlay in self.overlays:
            try:
                overlay.win.destroy()
            except tk.TclError:
                pass


def _geometry(rect: Rect) -> str:
    """Tk geometry 문자열.

    Tk 는 음수 좌표를 '+-100' 형태로 표기해야 하므로 부호와 무관하게
    항상 '+' 를 앞에 붙인다.
    """
    return f"{rect.w}x{rect.h}+{rect.x}+{rect.y}"


def select_region(master: tk.Misc | None = None, hint: str = "") -> tuple[Rect, int] | None:
    """드래그로 화면 영역을 고르게 하고 (영역, 모니터번호) 를 돌려준다.

    취소하면 None. ``master`` 가 주어지면 그 Tk 앱 안에서 모달로 동작한다.
    """
    monitors = list_monitors()
    if not monitors:
        log.error("모니터 정보를 읽지 못했습니다 (mss 미설치?).")
        return None

    owns_root = master is None
    root = tk.Tk() if owns_root else master.winfo_toplevel()
    if owns_root:
        root.withdraw()

    session = _Session()
    session.overlays = [
        _Overlay(root, monitor, index, session)
        for index, monitor in enumerate(monitors, start=1)
    ]

    if hint:
        _show_hint(session.overlays[0], hint)

    first = session.overlays[0].win
    first.focus_force()

    # 이미 mainloop 이 돌고 있는 앱 안에서도 안전하도록 중첩 이벤트 루프를 쓴다.
    root.wait_window(first)
    session.close()

    if owns_root:
        root.destroy()

    return session.result


def _show_hint(overlay: _Overlay, text: str) -> None:
    overlay.canvas.create_text(
        overlay.monitor.w // 2,
        60,
        fill="white",
        font=("Helvetica", 20, "bold"),
        text=text,
    )
    overlay.canvas.create_text(
        overlay.monitor.w // 2,
        95,
        fill="#bbbbbb",
        font=("Helvetica", 14),
        text="드래그해서 영역을 선택하세요 · ESC 취소",
    )
