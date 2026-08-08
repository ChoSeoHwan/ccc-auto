"""현재 화면에서 인식용 템플릿을 잘라 저장하는 창.

마법사에서 들어오면 선언에 적힌 ``default_area`` 가 이미 잡힌 채로 뜬다.
사용자는 자리가 맞는지 보고 그대로 저장하거나 다시 드래그해 고치면 된다.
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np

from ..geometry import NormRect
from ..templates_spec import TemplateSpec
from ..vision import TemplateStore
from .region_picker import ImageRegionPicker

_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\-]*$")

_FREE_GUIDE = "인식에 쓸 부분을 드래그해서 잘라 내세요."
_PRESET_GUIDE = "기본 자리를 잡아 두었습니다. 맞으면 그대로 저장하고, 아니면 다시 드래그하세요."
_MUTED = "#666"


class TemplateCaptureDialog(tk.Toplevel):
    """드래그해서 자른 조각을 이름과 함께 templates/ 에 저장한다."""

    def __init__(
        self,
        master: tk.Misc,
        frame: np.ndarray,
        store: TemplateStore,
        spec: TemplateSpec | None = None,
    ):
        super().__init__(master)
        self.title("템플릿 캡처")
        self.transient(master)
        self.resizable(False, False)

        self.store = store
        self.spec = spec
        self.preset_name = spec.name if spec else ""
        self.default_area = spec.default_area if spec else None
        self.saved_name: str | None = None

        self._build_guide()
        self.picker = ImageRegionPicker(self, frame, on_select=self._on_select)
        self.picker.pack(padx=10)
        self._build_bar()

        if self.default_area is not None:
            self.picker.set_selection(self.default_area)

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._save())
        self.grab_set()
        if not self.preset_name:
            self.name_entry.focus_set()

    # ------------------------------------------------------------------
    def _build_guide(self) -> None:
        """한 줄로 이어 붙이지 않는다. 항목마다 줄을 나눠야 눈으로 훑을 수 있다."""
        box = ttk.Frame(self, padding=(12, 10, 12, 4))
        box.pack(fill="x")

        if self.spec is None:
            ttk.Label(box, text=_FREE_GUIDE, justify="left").pack(anchor="w")
            return

        ttk.Label(
            box, text=self.spec.label, font=("Malgun Gothic", 11, "bold"), justify="left"
        ).pack(anchor="w")
        for line in self.spec.guide_lines():
            ttk.Label(
                box, text=line, justify="left", wraplength=840, foreground=_MUTED
            ).pack(anchor="w", pady=(2, 0))

        if self.default_area is not None:
            ttk.Label(box, text=_PRESET_GUIDE, justify="left").pack(anchor="w", pady=(6, 0))

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
        ttk.Label(bar, textvariable=self.info_var, foreground=_MUTED).pack(side="left")

        ttk.Button(bar, text="취소", command=self.destroy).pack(side="right")
        self.save_btn = ttk.Button(bar, text="저장", command=self._save, state="disabled")
        self.save_btn.pack(side="right", padx=6)
        if self.default_area is not None:
            ttk.Button(bar, text="기본 자리", command=self._reset_to_default).pack(
                side="right", padx=6
            )

    # ------------------------------------------------------------------
    def _reset_to_default(self) -> None:
        if self.default_area is not None:
            self.picker.set_selection(self.default_area)

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
