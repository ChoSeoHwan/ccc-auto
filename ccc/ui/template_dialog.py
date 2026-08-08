"""현재 화면에서 인식용 템플릿을 잘라 저장하는 창."""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np

from ..geometry import NormRect
from ..vision import TemplateStore
from .region_picker import ImageRegionPicker

_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\-]*$")


class TemplateCaptureDialog(tk.Toplevel):
    """드래그해서 자른 조각을 이름과 함께 templates/ 에 저장한다."""

    def __init__(
        self,
        master: tk.Misc,
        frame: np.ndarray,
        store: TemplateStore,
        preset_name: str = "",
        guide: str = "",
    ):
        super().__init__(master)
        self.title("템플릿 캡처")
        self.preset_name = preset_name
        self.transient(master)
        self.resizable(False, False)

        self.store = store
        self.saved_name: str | None = None

        ttk.Label(
            self,
            text=guide or "인식에 쓸 부분을 드래그해서 잘라 내세요. "
            "숫자가 바뀌는 퀘스트는 숫자를 빼고 잡으면 둘 다 걸립니다.",
            padding=(10, 8),
            justify="left",
            wraplength=860,
        ).pack(fill="x")

        self.picker = ImageRegionPicker(self, frame, on_select=self._on_select)
        self.picker.pack(padx=10)

        self._build_bar()

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._save())
        self.grab_set()
        if not self.preset_name:
            self.name_entry.focus_set()

    # ------------------------------------------------------------------
    def _build_bar(self) -> None:
        bar = ttk.Frame(self, padding=10)
        bar.pack(fill="x")

        ttk.Label(bar, text="이름:").pack(side="left")
        self.name_var = tk.StringVar(value=self.preset_name)
        self.name_entry = ttk.Entry(
            bar,
            textvariable=self.name_var,
            width=24,
            # 마법사가 이름을 정해 줬으면 바꾸지 못하게 한다. 이름이 어긋나면
            # 코드가 찾지 못한다.
            state="readonly" if self.preset_name else "normal",
        )
        self.name_entry.pack(side="left", padx=(6, 10))

        self.info_var = tk.StringVar(value="영역을 선택하세요")
        ttk.Label(bar, textvariable=self.info_var, foreground="#666").pack(side="left")

        ttk.Button(bar, text="취소", command=self.destroy).pack(side="right")
        self.save_btn = ttk.Button(bar, text="저장", command=self._save, state="disabled")
        self.save_btn.pack(side="right", padx=6)

    # ------------------------------------------------------------------
    def _on_select(self, _rect: NormRect) -> None:
        pixels = self.picker.selection_pixels()
        if pixels is None:
            return
        self.info_var.set(f"{pixels.w} x {pixels.h} px")
        self.save_btn.config(state="normal")

    def _save(self) -> None:
        pixels = self.picker.selection_pixels()
        if pixels is None or self.picker.selection is None:
            return

        name = self.name_var.get().strip()
        if not _NAME_RE.match(name):
            messagebox.showwarning(
                "이름 확인",
                "영문/숫자/밑줄/하이픈만 쓸 수 있고 빈 값은 안 됩니다.",
                parent=self,
            )
            return
        if name in self.store.names() and not messagebox.askyesno(
            "덮어쓰기", f"'{name}' 템플릿이 이미 있습니다. 덮어쓸까요?", parent=self
        ):
            return

        patch = self.picker.frame_bgr[
            pixels.y : pixels.bottom, pixels.x : pixels.right
        ].copy()
        self.store.save(name, patch, self.picker.selection)
        self.saved_name = name
        self.destroy()
