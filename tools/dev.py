"""개발용 명령 모음.

작업하면서 반복하는 일들(화면 확인, 템플릿 뜨기, 자동화 잠깐 돌려보기)을
한 진입점에 모았다. 셸 힙독이나 파이프 없이 단순한 명령 하나로 끝나므로
권한 규칙도 ``Bash(python3 tools/dev.py *)`` 한 줄이면 된다.

    python3 tools/dev.py diag                     연결 · 캡처 · 인식 상태
    python3 tools/dev.py shot [--anchors]         화면을 captures/ 에 저장
    python3 tools/dev.py crop 0.55 0.5 0.45 0.11  영역만 잘라서 저장 (정규화 좌표)
    python3 tools/dev.py goto-battle              팝업 · 절전 모드를 치우고 전투화면까지
    python3 tools/dev.py template save 이름 x y w h   현재 화면에서 템플릿 저장
    python3 tools/dev.py template test [이름...]      템플릿이 지금 화면에 잡히는지
    python3 tools/dev.py template list                저장된 템플릿 목록
    python3 tools/dev.py run --seconds 60             자동화를 잠깐 돌려 보기
    python3 tools/dev.py bench                        구간별 소요 시간
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccc import anchors as anchor_names  # noqa: E402
from ccc.anchors import AnchorSet  # noqa: E402
from ccc.app import AppError, AutomationApp  # noqa: E402
from ccc.config import CAPTURE_DIR, Config  # noqa: E402
from ccc.geometry import NormRect  # noqa: E402
from ccc.vision import BUTTON_ORANGE, imread, imwrite  # noqa: E402

DEFAULT_MODULES = [
    "power_save.ExitPowerSaveMode",
    "keep_alive.KeepGameForeground",
    "quest_runner.QuestAutomation",
]


# ----------------------------------------------------------------------
# 공용
# ----------------------------------------------------------------------
def connect(capture: str = "adb") -> AutomationApp:
    """설정을 읽어 연결까지 마친 앱을 돌려준다."""
    logging.disable(logging.INFO)
    config = Config.load()
    if capture == "adb" or config.region is None:
        config.capture_backend = "adb"
    app = AutomationApp(config)
    app.connect(config.adb_serial)
    return app


def save(image, prefix: str) -> Path:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = CAPTURE_DIR / f"{prefix}-{datetime.now().strftime('%H%M%S')}.png"
    if not imwrite(path, image):
        raise AppError(f"화면을 저장하지 못했습니다: {path}")
    return path


def report(app: AutomationApp, frame) -> None:
    from ccc.quest.diagnostics import DetectionReport

    for line in DetectionReport(frame, app.anchors).lines():
        print(f"  {line}")


# ----------------------------------------------------------------------
# 서브커맨드
# ----------------------------------------------------------------------
def cmd_diag(args) -> int:
    app = connect()
    device = app.device
    print(f"디바이스 {device.width}x{device.height} {device.model}")
    print(f"현재 앱  {app.client.current_package() or '알 수 없음'}")
    frame = app.capture()
    print(f"캡처     {frame.shape[1]}x{frame.shape[0]} ({app.config.capture_backend})")
    report(app, frame)
    return 0


def cmd_shot(args) -> int:
    app = connect()
    frame = app.capture()
    report(app, frame)
    image = _with_anchors(frame, app.anchors) if args.anchors else frame
    print(f"저장 {save(image, 'shot')}")
    return 0


def cmd_crop(args) -> int:
    import cv2

    app = connect()
    frame = app.capture()
    rect = NormRect(args.x, args.y, args.w, args.h).scaled(frame.shape[1], frame.shape[0])
    patch = frame[rect.y : rect.bottom, rect.x : rect.right]
    if patch.size == 0:
        print("영역이 비어 있습니다.")
        return 1
    if args.zoom > 1:
        patch = cv2.resize(
            patch,
            (patch.shape[1] * args.zoom, patch.shape[0] * args.zoom),
            interpolation=cv2.INTER_NEAREST,
        )
    print(f"저장 {save(patch, args.name)}  ({patch.shape[1]}x{patch.shape[0]})")
    return 0


def cmd_goto_battle(args) -> int:
    """팝업과 절전 모드를 치우고 메인 전투화면까지 몰아간다."""
    from ccc.modules.power_save import LABEL_TEMPLATE, MATCH_THRESHOLD, SEARCH_AREA
    from ccc.quest.navigator import BattleScreenNavigator
    from ccc.vision import find_text

    app = connect()
    navigator = BattleScreenNavigator(app.anchors.get(anchor_names.NAV_CLOSE))
    device = app.device

    def tap(area: NormRect) -> None:
        nx, ny = area.center
        app.client.tap(int(nx * (device.width - 1)), int(ny * (device.height - 1)))

    for attempt in range(args.tries):
        frame = app.capture()
        if find_text(frame, app.templates.load(LABEL_TEMPLATE), MATCH_THRESHOLD, SEARCH_AREA):
            print(f"{attempt + 1}: 절전 모드 → 뒤로가기")
            app.client.back()
        elif not navigator.is_battle_screen(frame):
            print(f"{attempt + 1}: 팝업 → 닫기")
            tap(app.anchors.get(anchor_names.NAV_CLOSE))
        else:
            print(f"전투화면 도달 ({attempt}회 조작)")
            report(app, frame)
            return 0
        time.sleep(args.wait)

    print(f"{args.tries}번 시도했으나 전투화면에 도달하지 못했습니다.")
    report(app, app.capture())
    return 1


COLORS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    # 주황은 자동화가 실제로 버튼을 찾을 때 쓰는 값 그대로다. 여기서 잰 자리가
    # 운영에서도 그대로 잡히도록 같은 상수를 쓴다.
    "orange": BUTTON_ORANGE,
    "gold": ((10, 110, 130), (40, 255, 255)),
    "teal": ((80, 60, 140), (105, 200, 255)),
    "red": ((0, 120, 90), (10, 255, 255)),
    "blue": ((100, 120, 120), (130, 255, 255)),
}


def load_frame(app: AutomationApp, source: str | None):
    """--from 이 있으면 그 파일을, 없으면 지금 화면을 쓴다."""
    if not source:
        return app.capture()

    frame = imread(source)
    if frame is None:
        raise AppError(f"이미지를 읽지 못했습니다: {source}")
    return frame


def cmd_lines(args) -> int:
    """퀘스트창 안의 글자 줄들을 찾아 정규화 좌표로 알려 준다.

    퀘스트 이름 템플릿을 뜰 때 쓴다. 눈대중으로 자르면 숫자가 섞이거나
    너무 작게 잘려서 축소 화면에서 매칭이 무너진다.
    """
    import cv2
    import numpy as np

    from ccc.vision import text_mask

    app = connect()
    frame = load_frame(app, args.source)
    height, width = frame.shape[:2]
    panel = app.anchors.get(anchor_names.QUEST_PANEL).scaled(width, height)

    mask = text_mask(frame[panel.y : panel.bottom, panel.x : panel.right])
    merged = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 35), np.uint8))
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = sorted(
        (cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > 400),
        key=lambda b: b[1],
    )

    if not boxes:
        print("퀘스트창에서 글자를 찾지 못했습니다.")
        return 1

    print(f"글자 줄 {len(boxes)}개 (위에서부터)")
    for index, (bx, by, bw, bh) in enumerate(boxes):
        pad = 5
        x, y = panel.x + bx - pad, panel.y + by - pad
        w, h = bw + pad * 2, bh + pad * 2
        print(
            f"  [{index}] px=({x},{y},{w},{h})  "
            f"norm=({x / width:.4f} {y / height:.4f} {w / width:.4f} {h / height:.4f})"
        )
    print("\n첫 줄은 보통 '퀘스트 1319' 같은 번호라 쓰면 안 된다.")
    print("이름 줄이 짧으면 다음 줄까지 함께 감싸서 템플릿을 키워라.")
    return 0


def cmd_identify(args) -> int:
    """등록된 퀘스트들이 이 화면을 각각 몇 점으로 보는지 늘어놓는다.

    판별이 왜 그렇게 났는지 확인할 때 쓴다. 1등과 2등의 차이가 충분히
    벌어지는지가 핵심이다. ``--exclude`` 로 특정 퀘스트를 빼면 그것이 아직
    등록되지 않은 상황에서 어떻게 판정되는지 미리 볼 수 있다.
    """
    import cv2

    from ccc.quest.machine import MIN_SCORE_MARGIN
    from ccc.quest.registry import QuestRegistry

    app = connect()
    frame = load_frame(app, args.source)
    height, width = frame.shape[:2]
    area = app.anchors.get(anchor_names.QUEST_PANEL)

    quests = QuestRegistry().load()
    if args.exclude:
        dropped = {name.strip() for name in args.exclude.split(",")}
        quests = [quest for quest in quests if quest.label not in dropped]
        print(f"제외: {', '.join(sorted(dropped))}")
    if not quests:
        print("등록된 퀘스트가 없습니다.")
        return 1

    ctx = _offline_context(app)
    for scale in (1.0, 0.75, 0.5):
        image = (
            frame
            if scale == 1.0
            else cv2.resize(
                frame, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA
            )
        )
        ctx.set_frame(image)
        scores = sorted(((q.match_score(ctx, area), q.label) for q in quests), reverse=True)
        margin = scores[0][0] - scores[1][0] if len(scores) > 1 else scores[0][0]
        verdict = "확정" if margin >= MIN_SCORE_MARGIN and scores[0][0] > 0 else "모호"
        print(f"\n  [{int(scale * 100)}%]")
        for score, label in scores:
            print(f"      {score:6.3f}  {label}")
        print(f"      → 1등-2등 차이 {margin:.3f} ({verdict}, 기준 {MIN_SCORE_MARGIN})")
    return 0


def _offline_context(app: AutomationApp):
    """화면만 갈아 끼우며 판별을 시험하기 위한 최소 컨텍스트."""
    import threading

    from ccc.context import Context

    return Context(
        app.client,
        app.templates,
        threading.Event(),
        anchors=app.anchors,
        notifier=app.notifier,
    )


def cmd_locate(args) -> int:
    """지정한 색 덩어리를 찾아 정규화 사각형으로 알려 준다.

    버튼 좌표를 눈대중으로 재지 않기 위한 것. --save 를 주면 그 자리를 바로
    템플릿으로 저장한다.
    """
    import cv2
    import numpy as np

    app = connect()
    frame = load_frame(app, args.source)
    height, width = frame.shape[:2]
    lower, upper = COLORS[args.color]

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(lower, np.uint8), np.array(upper, np.uint8))

    area = NormRect(*args.area) if args.area else NormRect(0.0, 0.0, 1.0, 1.0)
    band = np.zeros_like(mask)
    box = area.scaled(width, height)
    band[box.y : box.bottom, box.x : box.right] = 255
    mask = cv2.morphologyEx(
        cv2.bitwise_and(mask, band), cv2.MORPH_CLOSE, np.ones((13, 13), np.uint8)
    )

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs = sorted(contours, key=cv2.contourArea, reverse=True)[: args.top]
    if not blobs:
        print(f"'{args.color}' 덩어리를 찾지 못했습니다.")
        return 1

    for index, blob in enumerate(blobs):
        x, y, w, h = cv2.boundingRect(blob)
        rect = NormRect(x / width, y / height, w / width, h / height)
        print(
            f"  [{index}] px=({x},{y},{w},{h})  "
            f"norm=({rect.x:.4f} {rect.y:.4f} {rect.w:.4f} {rect.h:.4f})  "
            f"중심=({rect.center[0]:.4f}, {rect.center[1]:.4f})"
        )

    if args.save:
        x, y, w, h = cv2.boundingRect(blobs[args.pick])
        rect = NormRect(x / width, y / height, w / width, h / height)
        app.templates.save(args.save, frame[y : y + h, x : x + w].copy(), rect)
        print(f"템플릿 저장: {args.save}  {w}x{h}px")
    return 0


def cmd_tap(args) -> int:
    """정규화 좌표나 앵커 이름으로 한 번 누른다."""
    app = connect()
    device = app.device

    if args.anchor:
        nx, ny = app.anchors.get(args.anchor).center
    elif args.x is not None and args.y is not None:
        nx, ny = args.x, args.y
    else:
        print("좌표(x y) 또는 --anchor 중 하나를 주세요.")
        return 1

    x, y = int(nx * (device.width - 1)), int(ny * (device.height - 1))
    print(f"탭 n({nx:.4f}, {ny:.4f}) → d({x}, {y})")
    app.client.tap(x, y)
    time.sleep(args.wait)
    report(app, app.capture())
    return 0


def cmd_template(args) -> int:
    from ccc.vision import find, find_text

    app = connect()
    store = app.templates

    if args.action == "list":
        names = store.names()
        print(f"템플릿 {len(names)}개")
        for name in names:
            template = store.load(name)
            print(
                f"  {name:22s} {template.image.shape[1]:4d}x{template.image.shape[0]:<4d}"
                f" norm {template.source.w:.4f}x{template.source.h:.4f}"
            )
        return 0

    frame = load_frame(app, args.source)

    if args.action == "save":
        rect = NormRect(args.x, args.y, args.w, args.h)
        pixels = rect.scaled(frame.shape[1], frame.shape[0])
        patch = frame[pixels.y : pixels.bottom, pixels.x : pixels.right].copy()
        if patch.size == 0:
            print("영역이 비어 있습니다.")
            return 1
        store.save(args.name, patch, rect)
        print(f"저장 {args.name}  {patch.shape[1]}x{patch.shape[0]}px  norm {rect.to_dict()}")
        return 0

    # test — 지금 화면에서 잡히는지, 축소해도 잡히는지 함께 본다
    import cv2

    names = args.names or store.names()
    height, width = frame.shape[:2]
    print(f"{'템플릿':<22s}{'100%':>9s}{'75%':>9s}{'50%':>9s}")
    for name in names:
        template = store.load(name)
        scores = []
        for scale in (1.0, 0.75, 0.5):
            image = (
                frame
                if scale == 1.0
                else cv2.resize(
                    frame, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA
                )
            )
            matcher = find_text if args.text else find
            best = 0.0
            for threshold in (0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.6, 0.5, 0.4, 0.3):
                match = matcher(image, template, threshold, None)
                if match:
                    best = match.score
                    break
            scores.append(best)
        print(f"{name:<22s}" + "".join(f"{s:9.3f}" for s in scores))
    return 0


def cmd_run(args) -> int:
    app = connect()
    app.config.notify = False
    app.config.fps = args.fps
    app.config.enabled_modules = args.modules.split(",") if args.modules else DEFAULT_MODULES
    app.on_log = lambda message: print(f"{time.strftime('%H:%M:%S')} {message}", flush=True)
    app.reload_modules()
    app.start()

    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline:
        time.sleep(2)
        quest = app.quest_module()
        if args.stop_on_idle and quest and quest.machine and quest.machine.state.value == "대기":
            print("대기 상태 진입")
            break
    app.stop()

    quest = app.quest_module()
    print(f"최종 상태: {quest.status if quest else '모듈 없음'}")
    return 0


def cmd_bench(args) -> int:
    import cv2

    from ccc.quest.diagnostics import DetectionReport

    app = connect()

    def measure(label: str, action, count: int) -> None:
        action()
        start = time.perf_counter()
        for _ in range(count):
            action()
        print(f"  {label:32s} {(time.perf_counter() - start) / count * 1000:8.2f} ms")

    frame = app.capture()
    print(f"프레임 {frame.shape[1]}x{frame.shape[0]}  OpenCV {cv2.__version__}")
    measure("adb 캡처", app.capture, 5)
    measure("인식 리포트", lambda: DetectionReport(frame, app.anchors), 20)
    for name in ("oven_auto", "bag_treasure_box"):
        if name in app.templates.names():
            from ccc.vision import find

            measure(
                f"템플릿 매칭 ({name})",
                lambda n=name: find(frame, app.templates.load(n), 0.8, NormRect(0.0, 0.5, 1.0, 0.5)),
                10,
            )
    return 0


# ----------------------------------------------------------------------
def _with_anchors(frame, anchors: AnchorSet):
    import cv2

    colors = [(255, 200, 0), (255, 0, 255), (0, 0, 255), (0, 255, 0)]
    image = frame.copy()
    height, width = image.shape[:2]
    for index, name in enumerate(AnchorSet.names()):
        rect = anchors.get(name).scaled(width, height)
        color = colors[index % len(colors)]
        cv2.rectangle(image, (rect.x, rect.y), (rect.right, rect.bottom), color, 4)
        cv2.putText(
            image, name, (rect.x, max(24, rect.y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2,
        )
    return image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="쿠키런 크럼블 자동화 개발 도구")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("diag", help="연결 · 캡처 · 인식 상태").set_defaults(func=cmd_diag)

    shot = sub.add_parser("shot", help="화면을 captures/ 에 저장")
    shot.add_argument("--anchors", action="store_true", help="앵커 영역을 겹쳐 그림")
    shot.set_defaults(func=cmd_shot)

    crop = sub.add_parser("crop", help="영역만 잘라 저장 (정규화 좌표)")
    for axis in ("x", "y", "w", "h"):
        crop.add_argument(axis, type=float)
    crop.add_argument("--name", default="crop")
    crop.add_argument("--zoom", type=int, default=2)
    crop.set_defaults(func=cmd_crop)

    goto = sub.add_parser("goto-battle", help="팝업 · 절전 모드를 치우고 전투화면까지")
    goto.add_argument("--tries", type=int, default=10)
    goto.add_argument("--wait", type=float, default=1.5)
    goto.set_defaults(func=cmd_goto_battle)

    identify = sub.add_parser("identify", help="퀘스트 판별 점수를 늘어놓기")
    identify.add_argument("--from", dest="source", help="지금 화면 대신 이 이미지 파일에서")
    identify.add_argument("--exclude", help="이 퀘스트들을 등록되지 않은 것처럼 뺀다 (쉼표 구분)")
    identify.set_defaults(func=cmd_identify)

    lines = sub.add_parser("lines", help="퀘스트창 안의 글자 줄 좌표 찾기")
    lines.add_argument("--from", dest="source", help="지금 화면 대신 이 이미지 파일에서")
    lines.set_defaults(func=cmd_lines)

    locate = sub.add_parser("locate", help="색으로 버튼 위치 찾기 (눈대중 대신)")
    locate.add_argument("color", choices=sorted(COLORS))
    locate.add_argument("--area", nargs=4, type=float, metavar=("X", "Y", "W", "H"))
    locate.add_argument("--top", type=int, default=3, help="상위 몇 개를 볼지")
    locate.add_argument("--pick", type=int, default=0, help="--save 할 때 고를 번호")
    locate.add_argument("--save", help="찾은 자리를 이 이름으로 템플릿 저장")
    locate.add_argument("--from", dest="source", help="지금 화면 대신 이 이미지 파일에서")
    locate.set_defaults(func=cmd_locate)

    tap = sub.add_parser("tap", help="정규화 좌표나 앵커를 한 번 누르기")
    tap.add_argument("x", nargs="?", type=float)
    tap.add_argument("y", nargs="?", type=float)
    tap.add_argument("--anchor", help=f"앵커 이름 ({', '.join(AnchorSet.names())})")
    tap.add_argument("--wait", type=float, default=2.5)
    tap.set_defaults(func=cmd_tap)

    template = sub.add_parser("template", help="템플릿 저장 · 점검 · 목록")
    template.add_argument("action", choices=["save", "test", "list"])
    template.add_argument("name", nargs="?")
    template.add_argument("x", nargs="?", type=float)
    template.add_argument("y", nargs="?", type=float)
    template.add_argument("w", nargs="?", type=float)
    template.add_argument("h", nargs="?", type=float)
    template.add_argument("--names", nargs="*", help="test 에서 검사할 템플릿")
    template.add_argument("--text", action="store_true", help="글자 이진화 매칭으로 검사")
    template.add_argument("--from", dest="source", help="지금 화면 대신 이 이미지 파일에서")
    template.set_defaults(func=cmd_template)

    run = sub.add_parser("run", help="자동화를 잠깐 돌려 보기")
    run.add_argument("--seconds", type=int, default=60)
    run.add_argument("--fps", type=float, default=4.0)
    run.add_argument("--modules", default="", help="쉼표로 구분한 모듈 키")
    run.add_argument(
        "--stop-on-idle",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="대기 상태가 되면 멈춘다 (--no-stop-on-idle 로 계속)",
    )
    run.set_defaults(func=cmd_run)

    sub.add_parser("bench", help="구간별 소요 시간").set_defaults(func=cmd_bench)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except AppError as exc:
        print(f"[실패] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
