"""인식 진단 결과를 보여 준다.

퀘스트창을 골드/회색 중 무엇으로 읽고 있는지, 닫기 버튼이 잡히는지를
숫자로 확인할 수 있어서 앵커나 임계값이 어긋났을 때 원인을 바로 찾는다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import numpy as np

from ..anchors import AnchorSet
from ..quest.diagnostics import DetectionReport


def show_detection_report(
    parent: tk.Misc, frame: np.ndarray, anchors: AnchorSet
) -> list[str]:
    """진단 결과를 팝업으로 띄우고, 로그에 남길 줄 목록을 돌려준다."""
    lines = DetectionReport(frame, anchors).lines()
    messagebox.showinfo("인식 진단", "\n".join(lines), parent=parent)
    return lines
