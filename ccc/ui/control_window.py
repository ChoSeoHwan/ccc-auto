"""컨트롤 창 — 화면 표시와 사용자 입력만 담당한다.

판단이나 실행 로직은 전부 :class:`ccc.app.AutomationApp` 에 있고, 여기서는
그 메서드를 부르고 결과를 그려 줄 뿐이다.
"""

from __future__ import annotations

import logging
import queue
import time
import tkinter as tk
from tkinter import messagebox, ttk

from ..app import AppError, AutomationApp
from ..selector import select_region
from .anchor_dialog import AnchorEditDialog
from .diagnostics_dialog import show_detection_report
from .setup_dialog import TemplateSetupDialog
from .template_dialog import TemplateCaptureDialog

log = logging.getLogger(__name__)

_PAD = 8
_STATUS_POLL_MS = 300
_LOG_POLL_MS = 100

_MAX_LOG_LINES = 100
"""로그는 최근 이만큼만 남긴다. 오래 돌려도 메모리와 렌더링 비용이 늘지 않는다."""

_CONTROL_WIDTH = 420
"""왼쪽 조작 패널의 폭. 한글 버튼 이름이 잘리지 않을 만큼 잡는다."""


class ControlWindow(tk.Tk):
    def __init__(self, app: AutomationApp):
        super().__init__()
        self.app = app
        self.module_vars: dict[str, tk.BooleanVar] = {}
        self._log_queue: queue.Queue[str] = queue.Queue()

        app.on_log = self._log_queue.put
        app.on_engine_state = lambda state: self.after(0, self._apply_engine_state, state)

        self.title("쿠키런 크럼블 자동화")
        self.resizable(True, True)
        self.minsize(_CONTROL_WIDTH + 260, 560)
        self.geometry(f"{_CONTROL_WIDTH + 420}x640")
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        self._reload_modules()
        self._render_region()

        self.after(_LOG_POLL_MS, self._drain_log)
        self.after(_STATUS_POLL_MS, self._poll_status)
        self.after(200, lambda: self._connect(quiet=True))

    # ------------------------------------------------------------------
    # 화면 구성
    # ------------------------------------------------------------------
    def _build(self) -> None:
        """왼쪽은 조작, 오른쪽은 로그.

        로그는 탭을 오가는 동안에도 계속 보여야 상황을 놓치지 않으므로
        탭 안에 넣지 않고 옆에 둔다.
        """
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)

        controls = ttk.Frame(panes, width=_CONTROL_WIDTH)
        controls.pack_propagate(False)
        panes.add(controls, weight=0)

        notebook = ttk.Notebook(controls, padding=4)
        notebook.pack(fill="both", expand=True)

        run_tab = ttk.Frame(notebook, padding=_PAD)
        setup_tab = ttk.Frame(notebook, padding=_PAD)
        notebook.add(run_tab, text="실행")
        notebook.add(setup_tab, text="설정")

        self._build_status(run_tab)
        self._build_modules(run_tab)

        self._build_connection(setup_tab)
        self._build_region(setup_tab)
        self._build_tools(setup_tab)
        self._build_options(setup_tab)

        log_pane = ttk.Frame(panes, padding=(0, 4, 4, 4))
        panes.add(log_pane, weight=1)
        self._build_log(log_pane)

    # --- 실행 탭 -------------------------------------------------------
    def _build_status(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="상태", padding=_PAD)
        box.pack(fill="x", pady=(0, _PAD))

        self.status_var = tk.StringVar(value="정지됨")
        ttk.Label(box, textvariable=self.status_var, font=("Helvetica", 13, "bold")).pack(
            anchor="w"
        )
        self.quest_var = tk.StringVar(value="")
        ttk.Label(
            box, textvariable=self.quest_var, foreground="#666",
            wraplength=_CONTROL_WIDTH - 60, justify="left",
        ).pack(anchor="w", pady=(2, 0))

        self.setup_var = tk.StringVar(value="")
        self.setup_label = ttk.Label(
            box, textvariable=self.setup_var, foreground="#a8720c",
            wraplength=_CONTROL_WIDTH - 60, justify="left",
        )
        self.setup_label.pack(anchor="w", pady=(2, 8))

        buttons = ttk.Frame(box)
        buttons.pack(fill="x")
        self.start_btn = ttk.Button(buttons, text="시작", command=self._start)
        self.start_btn.pack(side="left", fill="x", expand=True)
        self.stop_btn = ttk.Button(
            buttons, text="정지", command=self._stop, state="disabled"
        )
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=6)

        quest_buttons = ttk.Frame(box)
        quest_buttons.pack(fill="x", pady=(6, 0))
        self.idle_btn = ttk.Button(
            quest_buttons, text="대기로 전환", command=self._to_idle, state="disabled"
        )
        self.idle_btn.pack(side="left", fill="x", expand=True)
        self.resume_btn = ttk.Button(
            quest_buttons, text="퀘스트 재개", command=self._resume, state="disabled"
        )
        self.resume_btn.pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _build_modules(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="자동화 모듈", padding=_PAD)
        box.pack(fill="x", pady=(0, _PAD))

        ttk.Button(box, text="모듈 새로고침", command=self._reload_modules).pack(anchor="w")
        self.module_frame = ttk.Frame(box)
        self.module_frame.pack(fill="x", pady=(6, 0))

    def _build_log(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text=f"로그 (최근 {_MAX_LOG_LINES}줄)", padding=4)
        box.pack(fill="both", expand=True)

        header = ttk.Frame(box)
        header.pack(fill="x", pady=(0, 4))
        self.log_count_var = tk.StringVar(value="0줄")
        ttk.Label(header, textvariable=self.log_count_var, foreground="#888").pack(side="left")
        ttk.Button(header, text="지우기", command=self._clear_log, width=7).pack(side="right")

        body = ttk.Frame(box)
        body.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            body, height=24, width=40, wrap="word", state="disabled",
            font=("Menlo", 11), spacing1=1,
        )
        scroll = ttk.Scrollbar(body, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.log_text.tag_configure("time", foreground="#888")
        self.log_text.tag_configure("warn", foreground="#a8720c")

    # --- 설정 탭 -------------------------------------------------------
    def _build_connection(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="연결", padding=_PAD)
        box.pack(fill="x", pady=(0, _PAD))

        ttk.Label(box, text="ADB 브리지").pack(anchor="w")

        row = ttk.Frame(box)
        row.pack(fill="x", pady=(2, 0))
        self.serial_var = tk.StringVar(value=self.app.config.adb_serial)
        entry = ttk.Entry(row, textvariable=self.serial_var)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _e: self._connect())
        ttk.Button(row, text="연결", command=self._connect, width=6).pack(side="left", padx=(6, 0))

        self.device_var = tk.StringVar(value="연결되지 않음")
        ttk.Label(
            box, textvariable=self.device_var, foreground="#666",
            wraplength=_CONTROL_WIDTH - 60, justify="left",
        ).pack(anchor="w", pady=(6, 0))

    def _build_region(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="화면 영역", padding=_PAD)
        box.pack(fill="x", pady=(0, _PAD))

        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Button(row, text="영역 재감지", command=self._select_region).pack(side="left")
        ttk.Button(row, text="지금 화면 보기", command=self._preview).pack(
            side="left", padx=6
        )

        self.region_var = tk.StringVar()
        ttk.Label(
            box, textvariable=self.region_var, foreground="#666",
            wraplength=_CONTROL_WIDTH - 60,
        ).pack(
            anchor="w", pady=(6, 4)
        )

        backend_row = ttk.Frame(box)
        backend_row.pack(fill="x")
        ttk.Label(backend_row, text="캡처 방식").pack(side="left")
        self.backend_var = tk.StringVar(value=self.app.config.capture_backend)
        for label, value in (("화면(빠름)", "screen"), ("adb(느림)", "adb")):
            ttk.Radiobutton(
                backend_row,
                text=label,
                value=value,
                variable=self.backend_var,
                command=self._on_backend_change,
            ).pack(side="left", padx=(8, 0))

    def _build_tools(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="인식 보정", padding=_PAD)
        box.pack(fill="x", pady=(0, _PAD))

        # 한 줄에 넷을 넣으면 한글 버튼 이름이 잘린다. 2x2 로 편다.
        buttons = [
            ("템플릿 설정", self._open_setup),
            ("템플릿 캡처", self._capture_template),
            ("영역 보정", self._edit_anchors),
            ("인식 진단", self._diagnose),
        ]
        for index, (label, command) in enumerate(buttons):
            ttk.Button(box, text=label, command=command).grid(
                row=index // 2, column=index % 2, sticky="ew", padx=(0, 6), pady=2
            )
        box.columnconfigure(0, weight=1)
        box.columnconfigure(1, weight=1)

    def _build_options(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="옵션", padding=_PAD)
        box.pack(fill="x")

        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text="속도").pack(side="left")
        self.fps_var = tk.StringVar(value=f"{self.app.config.fps:g}")
        ttk.Spinbox(
            row,
            from_=0.5,
            to=20.0,
            increment=0.5,
            width=5,
            textvariable=self.fps_var,
            command=self._save,
        ).pack(side="left", padx=(4, 2))
        ttk.Label(row, text="fps").pack(side="left")

        self.dry_var = tk.BooleanVar(value=self.app.config.dry_run)
        ttk.Checkbutton(
            box, text="안전 모드 (인식만 하고 입력은 보내지 않음)",
            variable=self.dry_var, command=self._save,
        ).pack(anchor="w", pady=(6, 0))

        self.notify_var = tk.BooleanVar(value=self.app.config.notify)
        ttk.Checkbutton(
            box, text="멈췄을 때 OS 알림 보내기", variable=self.notify_var, command=self._save
        ).pack(anchor="w")

    # ------------------------------------------------------------------
    # 동작 — 전부 app 에 위임한다
    # ------------------------------------------------------------------
    def _connect(self, quiet: bool = False) -> None:
        try:
            device = self.app.connect(self.serial_var.get())
        except AppError as exc:
            self.device_var.set("연결 실패")
            self._log(str(exc))
            if not quiet:
                messagebox.showerror("연결 실패", str(exc), parent=self)
            return

        self.device_var.set(
            f"{device.model or '디바이스'} · {device.width}x{device.height} · {device.serial}"
        )
        self._log(f"연결됨: {device.serial} ({device.width}x{device.height})")
        self._render_region()
        self._save()

    def _select_region(self) -> None:
        # 영역 선택은 화면 전체를 오버레이로 덮으므로, 캡처가 돌고 있으면 게임
        # 대신 오버레이를 찍게 된다. 사용자에게 정지를 떠넘기지 말고 여기서
        # 잠시 멈췄다가 되돌린다.
        resume = self.app.running
        if resume:
            if not messagebox.askyesno(
                "자동화 잠시 멈춤",
                "영역을 다시 잡는 동안 화면 캡처를 멈춰야 합니다.\n"
                "멈추고 영역을 잡은 뒤 자동으로 다시 시작할까요?",
                parent=self,
            ):
                return
            self._log("영역을 다시 잡기 위해 자동화를 잠시 멈춥니다.")
            self.app.stop()

        self.withdraw()
        self.update_idletasks()
        try:
            result = select_region(self, hint="블루스택의 게임 화면을 선택하세요")
        finally:
            self.deiconify()
            self.lift()

        if result is None:
            self._log("영역 선택을 취소했습니다.")
            if resume:
                self._resume_after_region()
            return

        rect, monitor_index = result
        self.app.set_region(rect, monitor_index)
        self.backend_var.set(self.app.config.capture_backend)
        self._log(f"영역 설정: {rect.x},{rect.y} {rect.w}x{rect.h}")
        self._render_region()
        self._save()
        if resume:
            self._resume_after_region()

    def _resume_after_region(self) -> None:
        try:
            self.app.start()
        except AppError as exc:
            self._log(f"자동화를 다시 시작하지 못했습니다: {exc}")

    def _on_backend_change(self) -> None:
        self.app.config.capture_backend = self.backend_var.get()
        self._render_region()
        self._save()

    def _render_region(self) -> None:
        rect = self.app.config.region
        if self.app.config.capture_backend == "adb":
            self.region_var.set("adb 캡처 — 영역 선택 없이 디바이스 화면 전체를 봅니다.")
            return
        if rect is None:
            self.region_var.set("영역이 아직 설정되지 않았습니다. '영역 재감지' 를 눌러 주세요.")
            return

        text = f"{rect.x}, {rect.y} · {rect.w}x{rect.h} · 비율 {rect.aspect:.2f}"
        warning = self.app.region_warning()
        self.region_var.set(f"{text}\n⚠ {warning}" if warning else text)

    def _preview(self) -> None:
        frame = self._capture()
        if frame is None:
            return
        height, width = frame.shape[:2]
        self._log(f"현재 캡처: {width}x{height}")
        self._open_template_dialog(frame, title="지금 화면")

    def _capture_template(self) -> None:
        frame = self._capture()
        if frame is not None:
            self._open_template_dialog(frame)

    def _open_template_dialog(self, frame, title: str = "") -> None:
        dialog = TemplateCaptureDialog(self, frame, self.app.templates)
        if title:
            dialog.title(title)
        self.wait_window(dialog)
        if dialog.saved_name:
            self._log(f"템플릿 저장됨: {dialog.saved_name}")

    def _open_setup(self) -> None:
        dialog = TemplateSetupDialog(
            self, self.app.required_templates(), self.app.templates, self._capture_for
        )
        self.wait_window(dialog)
        self._render_setup_state()

    def _capture_for(self, spec) -> str | None:
        """마법사가 항목 하나를 캡처할 때 부른다."""
        frame = self._capture()
        if frame is None:
            return None
        guide = f"[{spec.label}]  화면: {spec.where}  ·  대상: {spec.what}"
        if spec.tip:
            guide += f"\n주의: {spec.tip}"
        dialog = TemplateCaptureDialog(
            self, frame, self.app.templates, preset_name=spec.name, guide=guide
        )
        self.wait_window(dialog)
        if dialog.saved_name:
            self._log(f"템플릿 저장됨: {spec.label} ({dialog.saved_name})")
        return dialog.saved_name

    def _render_setup_state(self) -> None:
        missing = self.app.missing_templates()
        if missing:
            self.setup_var.set(
                f"⚠ 템플릿 {len(missing)}개가 없습니다 — 설정 탭의 '템플릿 설정' 에서 채우세요"
            )
        else:
            self.setup_var.set("")

    def _edit_anchors(self) -> None:
        frame = self._capture()
        if frame is None:
            return
        dialog = AnchorEditDialog(self, frame, self.app.anchors)
        self.wait_window(dialog)
        if dialog.changed:
            self._save()
            self._log("영역 보정을 저장했습니다. 다음 시작부터 적용됩니다.")

    def _diagnose(self) -> None:
        frame = self._capture()
        if frame is None:
            return
        for line in show_detection_report(self, frame, self.app.anchors):
            self._log(line)

    def _capture(self):
        try:
            return self.app.capture()
        except AppError as exc:
            self._log(str(exc))
            messagebox.showerror("캡처 실패", str(exc), parent=self)
            return None

    # ------------------------------------------------------------------
    def _reload_modules(self) -> None:
        for child in self.module_frame.winfo_children():
            child.destroy()
        self.module_vars.clear()

        modules = self.app.reload_modules()
        if not modules:
            ttk.Label(
                self.module_frame,
                text="모듈이 없습니다. ccc/modules/ 에 파일을 추가하세요.",
                foreground="#999",
            ).pack(anchor="w")

        for module in modules:
            var = tk.BooleanVar(value=self.app.is_module_enabled(module))
            self.module_vars[module.key] = var
            ttk.Checkbutton(
                self.module_frame, text=module.label, variable=var, command=self._save
            ).pack(anchor="w")

        for name, error in self.app.module_errors.items():
            self._log(f"⚠ 모듈 로드 실패 {name}: {error}")
        self._log(f"모듈 {len(modules)}개 로드됨")
        self._render_setup_state()

    # ------------------------------------------------------------------
    def _start(self) -> None:
        self._save()
        try:
            self.app.start()
        except AppError as exc:
            messagebox.showerror("시작할 수 없음", str(exc), parent=self)

    def _stop(self) -> None:
        self.app.stop()

    def _to_idle(self) -> None:
        module = self.app.quest_module()
        if module:
            module.request_idle()
            self._log("퀘스트 자동화를 대기 상태로 전환했습니다.")

    def _resume(self) -> None:
        module = self.app.quest_module()
        if module:
            module.request_start()
            self._log("퀘스트 자동화를 재개합니다.")

    # ------------------------------------------------------------------
    # 주기 갱신
    # ------------------------------------------------------------------
    def _poll_status(self) -> None:
        module = self.app.quest_module()
        running = self.app.running
        self.quest_var.set(f"퀘스트: {module.status}" if module else "")
        state = "normal" if running and module else "disabled"
        self.idle_btn.config(state=state)
        self.resume_btn.config(state=state)
        self.after(_STATUS_POLL_MS, self._poll_status)

    def _apply_engine_state(self, state: str) -> None:
        running = state == "running"
        self.status_var.set("실행 중" if running else "정지됨")
        self.start_btn.config(state="disabled" if running else "normal")
        self.stop_btn.config(state="normal" if running else "disabled")

    def _drain_log(self) -> None:
        try:
            while True:
                self._log(self._log_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(_LOG_POLL_MS, self._drain_log)

    def _log(self, message: str) -> None:
        self.log_text.config(state="normal")
        self.log_text.insert("end", time.strftime("%H:%M:%S "), "time")
        self.log_text.insert("end", message + "\n", "warn" if "⚠" in message else "")
        self._trim_log()
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _trim_log(self) -> None:
        """오래된 줄부터 버려 최근 것만 남긴다. 호출자가 편집 가능 상태로 열어 둔다."""
        excess = self._log_lines() - _MAX_LOG_LINES
        if excess > 0:
            self.log_text.delete("1.0", f"{excess + 1}.0")
        self.log_count_var.set(f"{self._log_lines()}줄")

    def _log_lines(self) -> int:
        # 마지막 줄바꿈 뒤의 빈 줄은 세지 않는다.
        return int(self.log_text.index("end-1c").split(".")[0]) - 1

    def _clear_log(self) -> None:
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_count_var.set("0줄")
        self.log_text.config(state="disabled")

    # ------------------------------------------------------------------
    def _save(self) -> None:
        config = self.app.config
        config.adb_serial = self.serial_var.get().strip()
        config.capture_backend = self.backend_var.get()
        config.fps = _parse_fps(self.fps_var.get(), config.fps)
        config.dry_run = self.dry_var.get()
        config.notify = self.notify_var.get()
        self.app.set_enabled_modules(
            [key for key, var in self.module_vars.items() if var.get()]
        )
        self.app.save_config()

    def _on_close(self) -> None:
        self.app.stop()
        self._save()
        self.destroy()


def _parse_fps(raw: str, fallback: float) -> float:
    try:
        return max(0.2, float(raw))
    except ValueError:
        return fallback

