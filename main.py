"""쿠키런: 크럼블 자동화 - 실행 진입점.

    python main.py            컨트롤 창 실행
    python main.py --check    연결/캡처/인식만 점검하고 종료
    python main.py --shot     현재 화면을 파일로 저장하고 기본 뷰어로 연다
    python main.py --shot --html   원격/모바일에서 볼 수 있는 HTML 한 장으로도 저장
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from ccc import logging_setup
from ccc.app import AppError, AutomationApp
from ccc.config import CAPTURE_DIR, Config


def run_check(app: AutomationApp) -> int:
    """GUI 없이 연결 · 캡처 · 인식이 되는지 확인한다."""
    from ccc.quest.diagnostics import DetectionReport
    from ccc.quest.registry import QuestRegistry

    try:
        device = app.connect(app.config.adb_serial)
    except AppError as exc:
        print(f"[실패] ADB 연결: {exc}")
        return 1
    print(f"[정상] ADB 연결: {device.serial} {device.width}x{device.height} {device.model}")
    assert app.client is not None
    print(f"[정보] 현재 앱: {app.client.current_package() or '알 수 없음'}")

    if app.config.capture_backend == "screen" and app.config.region is None:
        print("[정보] 화면 영역이 없어 adb 캡처로 점검합니다.")
        app.config.capture_backend = "adb"

    try:
        frame = app.capture()
    except AppError as exc:
        print(f"[실패] 캡처: {exc}")
        return 1
    print(f"[정상] 캡처({app.config.capture_backend}): {frame.shape[1]}x{frame.shape[0]}")

    for line in DetectionReport(frame, app.anchors).lines():
        print(f"[인식] {line}")

    modules = app.reload_modules()
    print(f"[정보] 모듈 {len(modules)}개: {', '.join(m.label for m in modules) or '없음'}")
    for name, error in app.module_errors.items():
        print(f"[경고] 모듈 로드 실패 {name}: {error}")

    registry = QuestRegistry()
    quests = registry.load()
    print(f"[정보] 퀘스트 정의 {len(quests)}개: {', '.join(q.label for q in quests) or '없음'}")
    for name, error in registry.errors.items():
        print(f"[경고] 퀘스트 정의 로드 실패 {name}: {error}")

    required = app.required_templates()
    missing = app.missing_templates()
    print(f"[정보] 템플릿 {len(required) - len(missing)}/{len(required)}개 준비됨")
    for spec in missing:
        print(f"[필요] {spec.title} ({spec.name}) — {spec.where}")
    if missing:
        print("[안내] 컨트롤 창 > 설정 > '템플릿 설정' 에서 하나씩 캡처하세요.")
    return 0


def run_shot(
    app: AutomationApp, overlay: bool, open_viewer: bool, as_html: bool = False
) -> int:
    """현재 화면을 captures/ 에 저장하고 기본 뷰어로 연다."""
    import cv2

    from ccc.quest.diagnostics import DetectionReport

    try:
        app.connect(app.config.adb_serial)
    except AppError as exc:
        print(f"[실패] ADB 연결: {exc}")
        return 1

    if app.config.capture_backend == "screen" and app.config.region is None:
        app.config.capture_backend = "adb"

    try:
        frame = app.capture()
    except AppError as exc:
        print(f"[실패] 캡처: {exc}")
        return 1

    # 진단은 앵커를 그려 넣기 전 원본으로 낸다.
    report = DetectionReport(frame, app.anchors)
    shown = _draw_anchors(frame, app.anchors) if overlay else frame

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    path = CAPTURE_DIR / f"shot-{stamp}.png"
    cv2.imwrite(str(path), shown)
    print(f"[저장] {path}")

    if as_html:
        from ccc.report import detection_rows, write_page

        # 파일명을 고정해 두면 같은 링크로 갱신할 수 있어서 원격에서 보기 편하다.
        path = write_page(CAPTURE_DIR / "current.html", shown, detection_rows(report))
        print(f"[저장] {path}")

    for line in report.lines():
        print(f"[인식] {line}")

    if open_viewer:
        _open(path)
    return 0


def _draw_anchors(frame, anchors):
    """앵커 영역을 색 사각형으로 그려 넣은 사본을 돌려준다."""
    import cv2

    from ccc.anchors import AnchorSet

    colors = [(255, 200, 0), (255, 0, 255), (0, 0, 255), (0, 255, 0)]
    vis = frame.copy()
    height, width = vis.shape[:2]
    for index, name in enumerate(AnchorSet.names()):
        rect = anchors.get(name).scaled(width, height)
        color = colors[index % len(colors)]
        cv2.rectangle(vis, (rect.x, rect.y), (rect.right, rect.bottom), color, 4)
        cv2.putText(
            vis, name, (rect.x, max(24, rect.y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2,
        )
    return vis


def _open(path: Path) -> None:
    """OS 기본 이미지 뷰어로 연다."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        elif sys.platform.startswith("win"):
            subprocess.run(["cmd", "/c", "start", "", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except OSError as exc:
        print(f"[경고] 뷰어를 열지 못했습니다: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="쿠키런: 크럼블 자동화")
    parser.add_argument("--check", action="store_true", help="연결/캡처/인식 점검 후 종료")
    parser.add_argument("--shot", action="store_true", help="현재 화면을 저장하고 뷰어로 열기")
    parser.add_argument("--anchors", action="store_true", help="--shot 에 앵커 영역을 겹쳐 그림")
    parser.add_argument("--html", action="store_true", help="--shot 을 자체 완결형 HTML 로도 저장")
    parser.add_argument("--no-open", action="store_true", help="--shot 에서 뷰어를 열지 않음")
    parser.add_argument("--serial", help="ADB 브리지 주소 (예: 127.0.0.1:5555)")
    parser.add_argument("--debug", action="store_true", help="자세한 로그 출력")
    args = parser.parse_args()

    logging_setup.setup(logging.DEBUG if args.debug else logging.INFO)

    config = Config.load()
    if args.serial:
        config.adb_serial = args.serial
    app = AutomationApp(config)

    if args.shot:
        return run_shot(
            app,
            overlay=args.anchors,
            open_viewer=not args.no_open,
            as_html=args.html,
        )

    if args.check:
        return run_check(app)

    from ccc.ui import ControlWindow

    ControlWindow(app).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
