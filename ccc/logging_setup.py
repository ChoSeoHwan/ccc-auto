"""로깅 설정."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "ccc-auto.log"


def setup(level: int = logging.INFO) -> None:
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    handlers: list[logging.Handler] = [console]
    try:
        file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    except OSError:
        pass  # 파일을 못 열면 콘솔만 쓴다

    root = logging.getLogger()
    root.setLevel(level)
    for handler in handlers:
        root.addHandler(handler)
