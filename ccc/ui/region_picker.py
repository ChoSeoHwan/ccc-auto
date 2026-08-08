"""캡처된 화면 위에서 영역을 드래그로 고르는 위젯.

템플릿 캡처와 앵커 보정이 같은 조작을 쓰므로 위젯 하나로 뽑아 뒀다.
표시용으로 축소하더라도 결과는 항상 정규화 좌표라 원본 해상도와 무관하다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

import numpy as np

from ..geometry import NormRect, Rect

_ACCENT = "#00d4ff"
_MIN_DRAG = 6


class ImageRegionPicker(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        frame_bgr: np.ndarray,
        max_size: int = 900,
        on_select: Callable[[NormRect], None] | None = None,
    ):
        super().__init__(master)
        self.frame_bgr = frame_bgr
        self.on_select = on_select
        self.selection: NormRect | None = None

        source_h, source_w = frame_bgr.shape[:2]
        self._scale = min(1.0, max_size / max(source_w, source_h))
        view_w = max(1, int(source_w * self._scale))
        view_h = max(1, int(source_h * self._scale))

        self._photo = _to_photo(frame_bgr, view_w, view_h)
        self.canvas = tk.Canvas(
            self, width=view_w, height=view_h, highlightthickness=0, cursor="crosshair"
        )
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        self._start: tuple[int, int] | None = None
        self._rect_id: int | None = None
        self._overlay_ids: list[int] = []

    # ------------------------------------------------------------------
    # 기존 영역 표시
    # ------------------------------------------------------------------
    def show_overlay(self, rect: NormRect, label: str, color: str = "#ff5c8a") -> None:
        view = rect.scaled(*self._view_size)
        self._overlay_ids.append(
            self.canvas.create_rectangle(
                view.x, view.y, view.right, view.bottom, outline=color, width=2, dash=(4, 3)
            )
        )
        self._overlay_ids.append(
            self.canvas.create_text(
                view.x + 3,
                max(8, view.y - 8),
                anchor="sw",
                fill=color,
                font=("Helvetica", 11, "bold"),
                text=label,
            )
        )

    def clear_overlays(self) -> None:
        for item in self._overlay_ids:
            self.canvas.delete(item)
        self._overlay_ids.clear()

    # ------------------------------------------------------------------
    # 미리 잡아 주기
    # ------------------------------------------------------------------
    def set_selection(self, rect: NormRect, notify: bool = True) -> None:
        """드래그 없이 영역을 지정해 둔다. 마법사가 기본 자리를 띄울 때 쓴다."""
        self.selection = rect
        self._draw_selection_rect(rect)
        if notify and self.on_select:
            self.on_select(rect)

    def _draw_selection_rect(self, rect: NormRect) -> None:
        self._clear_selection_rect()
        view = rect.scaled(*self._view_size)
        self._rect_id = self.canvas.create_rectangle(
            view.x, view.y, view.right, view.bottom, outline=_ACCENT, width=2
        )

    # ------------------------------------------------------------------
    # 드래그
    # ------------------------------------------------------------------
    def _on_press(self, event: tk.Event) -> None:
        self._start = (event.x, event.y)
        self._clear_selection_rect()

    def _on_drag(self, event: tk.Event) -> None:
        if self._start is None:
            return
        self._clear_selection_rect()
        self._rect_id = self.canvas.create_rectangle(
            *self._start, event.x, event.y, outline=_ACCENT, width=2
        )

    def _on_release(self, event: tk.Event) -> None:
        if self._start is None:
            return
        view = Rect.from_corners(*self._start, event.x, event.y)
        self._start = None
        if not view.is_valid(min_size=_MIN_DRAG):
            self.selection = None
            return

        self.selection = NormRect.from_pixels(view, *self._view_size)
        if self.on_select:
            self.on_select(self.selection)

    def _clear_selection_rect(self) -> None:
        if self._rect_id is not None:
            self.canvas.delete(self._rect_id)
            self._rect_id = None

    # ------------------------------------------------------------------
    @property
    def _view_size(self) -> tuple[int, int]:
        return int(self.canvas["width"]), int(self.canvas["height"])

    def selection_pixels(self) -> Rect | None:
        """선택 영역을 원본 프레임 픽셀 좌표로."""
        if self.selection is None:
            return None
        source_h, source_w = self.frame_bgr.shape[:2]
        return self.selection.scaled(source_w, source_h)


def _to_photo(frame_bgr: np.ndarray, width: int, height: int) -> tk.PhotoImage:
    from PIL import Image, ImageTk

    image = Image.fromarray(frame_bgr[:, :, ::-1]).resize((width, height), Image.LANCZOS)
    return ImageTk.PhotoImage(image)
