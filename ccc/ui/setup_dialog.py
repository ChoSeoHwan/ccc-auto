"""템플릿 캡처 마법사.

게임 화면 이미지는 저작물이라 저장소에 없다. 처음 실행하는 사람은 필요한
조각을 자기 화면에서 직접 떠야 하는데, 무엇을 어디서 잘라야 하는지 모르면
막힌다. 각 퀘스트·모듈이 선언해 둔 안내를 목록으로 보여 주고 하나씩 뜨게 한다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from ..templates_spec import TemplateSpec
from ..vision import TemplateStore

_PAD = 10


class TemplateSetupDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        specs: list[TemplateSpec],
        store: TemplateStore,
        capture: Callable[[TemplateSpec], str | None],
    ):
        super().__init__(master)
        self.title("템플릿 설정")
        self.transient(master)
        self.minsize(560, 420)

        self.specs = specs
        self.store = store
        self._capture = capture

        self._build()
        self.refresh()

        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        ttk.Label(
            self,
            text="자동화에 필요한 화면 조각을 하나씩 떠 주세요.\n"
            "게임 화면 이미지는 저작물이라 저장소에 들어 있지 않습니다.",
            padding=(_PAD, _PAD),
            justify="left",
        ).pack(fill="x")

        body = ttk.Frame(self, padding=(_PAD, 0))
        body.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            body, columns=("state",), show="tree headings", selectmode="browse", height=10
        )
        self.tree.heading("#0", text="템플릿")
        self.tree.heading("state", text="상태")
        self.tree.column("state", width=70, anchor="center", stretch=False)
        self.tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(body, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show_guide())

        guide = ttk.LabelFrame(self, text="캡처 방법", padding=_PAD)
        guide.pack(fill="x", padx=_PAD, pady=_PAD)
        self.guide_var = tk.StringVar(value="왼쪽에서 항목을 고르세요.")
        ttk.Label(guide, textvariable=self.guide_var, justify="left", wraplength=520).pack(
            anchor="w"
        )

        bar = ttk.Frame(self, padding=(_PAD, 0, _PAD, _PAD))
        bar.pack(fill="x")
        self.status_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.status_var, foreground="#666").pack(side="left")
        ttk.Button(bar, text="닫기", command=self.destroy).pack(side="right")
        self.capture_btn = ttk.Button(
            bar, text="이 항목 캡처", command=self._capture_selected, state="disabled"
        )
        self.capture_btn.pack(side="right", padx=6)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        have = set(self.store.names())
        selected = self.tree.selection()

        self.tree.delete(*self.tree.get_children())
        for spec in self.specs:
            done = spec.name in have
            self.tree.insert(
                "", "end", iid=spec.name, text=spec.label, values=("완료" if done else "필요")
            )

        missing = [spec for spec in self.specs if spec.name not in have]
        self.status_var.set(
            f"{len(self.specs) - len(missing)} / {len(self.specs)} 완료"
            + (f" · {len(missing)}개 남음" if missing else " · 모두 준비됐습니다")
        )

        target = selected[0] if selected and self.tree.exists(selected[0]) else None
        if target is None and missing:
            target = missing[0].name
        if target:
            self.tree.selection_set(target)
            self.tree.see(target)
        self._show_guide()

    def _selected_spec(self) -> TemplateSpec | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return next((s for s in self.specs if s.name == selection[0]), None)

    def _show_guide(self) -> None:
        spec = self._selected_spec()
        if spec is None:
            self.guide_var.set("왼쪽에서 항목을 고르세요.")
            self.capture_btn.config(state="disabled")
            return

        lines = [f"화면: {spec.where}", f"대상: {spec.what}"]
        if spec.tip:
            lines.append(f"주의: {spec.tip}")
        self.guide_var.set("\n".join(lines))
        self.capture_btn.config(state="normal")

    def _capture_selected(self) -> None:
        spec = self._selected_spec()
        if spec is None:
            return
        if spec.name in self.store.names() and not messagebox.askyesno(
            "다시 캡처", f"'{spec.label}' 은 이미 있습니다. 다시 뜰까요?", parent=self
        ):
            return

        self.withdraw()
        try:
            saved = self._capture(spec)
        finally:
            self.deiconify()
            self.lift()
            self.grab_set()

        if saved:
            self.store.reload()
            self.refresh()
