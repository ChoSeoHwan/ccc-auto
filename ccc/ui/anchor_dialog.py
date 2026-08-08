"""앵커(게임 UI 요소 위치) 보정 창.

게임 업데이트나 UI 배치 변경으로 기본 좌표가 어긋났을 때, 현재 화면을 보며
직접 다시 잡는다. 기존 앵커는 점선으로 겹쳐 보여 준다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import numpy as np

from ..anchors import AnchorSet
from ..geometry import NormRect
from .region_picker import ImageRegionPicker

_COLORS = ["#ff5c8a", "#ffd24a", "#5cd6ff", "#9dff5c"]


class AnchorEditDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, frame: np.ndarray, anchors: AnchorSet):
        super().__init__(master)
        self.title("영역 보정")
        self.transient(master)
        self.resizable(False, False)

        self.anchors = anchors
        self.changed = False

        ttk.Label(
            self,
            text="보정할 항목을 고르고, 화면에서 해당 영역을 드래그하세요.",
            padding=(10, 8),
        ).pack(fill="x")

        self.picker = ImageRegionPicker(self, frame, on_select=self._on_select)
        self.picker.pack(padx=10)

        self.target_var = tk.StringVar(value=AnchorSet.names()[0])
        self._build_bar()
        self._draw_overlays()

        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()

    # ------------------------------------------------------------------
    def _build_bar(self) -> None:
        bar = ttk.Frame(self, padding=10)
        bar.pack(fill="x")

        ttk.Label(bar, text="항목:").pack(side="left")
        combo = ttk.Combobox(
            bar,
            state="readonly",
            width=18,
            values=[AnchorSet.label(name) for name in AnchorSet.names()],
        )
        combo.current(0)
        combo.pack(side="left", padx=(6, 10))
        combo.bind("<<ComboboxSelected>>", self._on_target_change)
        self.combo = combo

        self.info_var = tk.StringVar(value="영역을 드래그하면 바로 반영됩니다")
        ttk.Label(bar, textvariable=self.info_var, foreground="#666").pack(side="left")

        ttk.Button(bar, text="닫기", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="기본값으로", command=self._reset).pack(side="right", padx=6)

    # ------------------------------------------------------------------
    def _current_target(self) -> str:
        return AnchorSet.names()[self.combo.current()]

    def _on_target_change(self, _event: tk.Event) -> None:
        name = self._current_target()
        self.info_var.set(f"'{AnchorSet.label(name)}' 영역을 드래그하세요")

    def _on_select(self, rect: NormRect) -> None:
        name = self._current_target()
        self.anchors.set(name, rect)
        self.changed = True
        self.info_var.set(
            f"{AnchorSet.label(name)} → "
            f"({rect.x:.3f}, {rect.y:.3f}) {rect.w:.3f}x{rect.h:.3f}"
        )
        self._draw_overlays()

    def _reset(self) -> None:
        name = self._current_target()
        self.anchors.reset(name)
        self.changed = True
        self.info_var.set(f"{AnchorSet.label(name)} 을(를) 기본값으로 되돌렸습니다")
        self._draw_overlays()

    def _draw_overlays(self) -> None:
        self.picker.clear_overlays()
        for index, name in enumerate(AnchorSet.names()):
            suffix = "" if self.anchors.is_customized(name) else " (기본값)"
            self.picker.show_overlay(
                self.anchors.get(name),
                AnchorSet.label(name) + suffix,
                _COLORS[index % len(_COLORS)],
            )
