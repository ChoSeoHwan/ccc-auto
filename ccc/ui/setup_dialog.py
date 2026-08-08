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
_WRAP = 540
_MUTED = "#666"

_GROUP_PREFIX = "그룹::"
"""묶음 행의 iid 접두사. 템플릿 이름은 영문/숫자/밑줄/하이픈뿐이라 겹치지 않는다."""


class TemplateSetupDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        groups: list[tuple[str, list[TemplateSpec]]],
        store: TemplateStore,
        capture: Callable[[TemplateSpec], str | None],
    ):
        super().__init__(master)
        self.title("템플릿 설정")
        self.transient(master)
        self.minsize(600, 520)

        self.groups = groups
        self.specs = [spec for _, specs in groups for spec in specs]
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
            body, columns=("state",), show="tree headings", selectmode="browse", height=14
        )
        self.tree.heading("#0", text="템플릿")
        self.tree.heading("state", text="상태")
        self.tree.column("#0", width=320, stretch=True)
        self.tree.column("state", width=70, anchor="center", stretch=False)
        self.tree.tag_configure("group", font=("Malgun Gothic", 10, "bold"))
        self.tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(body, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show_guide())

        self.guide = ttk.LabelFrame(self, text="캡처 방법", padding=_PAD)
        self.guide.pack(fill="x", padx=_PAD, pady=_PAD)

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
        for index, (group, specs) in enumerate(self.groups):
            done_count = sum(1 for spec in specs if spec.name in have)
            parent = self.tree.insert(
                "",
                "end",
                iid=f"{_GROUP_PREFIX}{index}",
                text=f"[{group}]",
                values=(f"{done_count}/{len(specs)}",),
                open=True,
                tags=("group",),
            )
            for spec in specs:
                self.tree.insert(
                    parent,
                    "end",
                    iid=spec.name,
                    text=spec.label,
                    values=("완료" if spec.name in have else "필요",),
                )

        missing = [spec for spec in self.specs if spec.name not in have]
        self.status_var.set(
            f"{len(self.specs) - len(missing)} / {len(self.specs)} 완료"
            + (f" · {len(missing)}개 남음" if missing else " · 모두 준비됐습니다")
        )

        target = selected[0] if selected and self.tree.exists(selected[0]) else None
        if target is None:
            # 남은 것부터, 다 됐으면 첫 항목. 안내 칸이 빈 채로 열리지 않게 한다.
            target = (missing[0] if missing else self.specs[0]).name if self.specs else None
        if target:
            self.tree.selection_set(target)
            self.tree.see(target)
        self._show_guide()

    def _selected_spec(self) -> TemplateSpec | None:
        """묶음 행을 고른 상태면 None. 그때는 캡처 버튼을 잠근다."""
        selection = self.tree.selection()
        if not selection or selection[0].startswith(_GROUP_PREFIX):
            return None
        return next((s for s in self.specs if s.name == selection[0]), None)

    def _show_guide(self) -> None:
        """항목마다 한 줄씩 띄운다. 한 덩어리로 붙여 놓으면 읽히지 않는다."""
        for child in self.guide.winfo_children():
            child.destroy()

        spec = self._selected_spec()
        if spec is None:
            ttk.Label(self.guide, text="왼쪽에서 항목을 고르세요.").pack(anchor="w")
            self.capture_btn.config(state="disabled")
            return

        for line in spec.guide_lines():
            ttk.Label(
                self.guide, text=line, justify="left", wraplength=_WRAP, foreground=_MUTED
            ).pack(anchor="w", pady=(0, 3))

        if spec.default_area is not None:
            ttk.Label(
                self.guide,
                text="'이 항목 캡처' 를 누르면 기본 자리가 잡힌 채로 열립니다.",
                justify="left",
                wraplength=_WRAP,
            ).pack(anchor="w", pady=(4, 0))

        self.capture_btn.config(state="normal")

    def _capture_selected(self) -> None:
        spec = self._selected_spec()
        if spec is None:
            return
        if spec.name in self.store.names() and not messagebox.askyesno(
            "다시 캡처", f"'{spec.title}' 은 이미 있습니다. 다시 뜰까요?", parent=self
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
