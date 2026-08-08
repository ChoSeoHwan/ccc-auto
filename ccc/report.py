"""화면 캡처와 인식 결과를 자체 완결형 HTML 한 장으로 묶는다.

터미널이나 채팅으로는 이미지가 안 보이는 환경(원격/모바일)에서 화면을
확인하려고 쓴다. 이미지를 data URI 로 심어 두므로 파일 하나만 열면 되고
외부 요청이 전혀 없다.
"""

from __future__ import annotations

import base64
import html
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

JPEG_QUALITY = 82
MAX_WIDTH = 900


@dataclass(frozen=True)
class ReportRow:
    """읽어 낸 값 한 줄."""

    label: str
    value: str
    state: str = "neutral"
    """pill 색을 고르는 값: gold · gray · ok · warn · neutral"""


def build_page(
    frame: np.ndarray,
    rows: list[ReportRow],
    title: str = "쿠키런 크럼블 — 현재 화면",
    subtitle: str = "",
) -> str:
    """자체 완결형 HTML 문서를 문자열로 만든다."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    height, width = frame.shape[:2]
    data_uri = _encode(frame)

    row_html = "\n".join(
        f'          <div class="row">\n'
        f'            <span class="row-label">{html.escape(row.label)}</span>\n'
        f'            <span class="pill pill--{row.state}">{html.escape(row.value)}</span>\n'
        f"          </div>"
        for row in rows
    )

    return _TEMPLATE.format(
        title=html.escape(title),
        subtitle=html.escape(subtitle or f"{width} × {height}"),
        stamp=html.escape(stamp),
        image=data_uri,
        rows=row_html,
    )


def detection_rows(report) -> list[ReportRow]:
    """``DetectionReport`` 를 표시용 줄로 옮긴다."""
    from .quest.states import PanelState

    state_style = {
        PanelState.GOLD: "gold",
        PanelState.GRAY: "gray",
        PanelState.UNKNOWN: "warn",
    }
    panel = report.panel
    return [
        ReportRow("퀘스트창", panel.state.value, state_style[panel.state]),
        ReportRow("황금 비율", f"{panel.gold_ratio:.1%}", "gold"),
        ReportRow("회색 비율", f"{panel.gray_ratio:.1%}", "gray"),
        ReportRow("닫기(X) 버튼 빨강", f"{report.close_ratio:.1%}", "neutral"),
        ReportRow(
            "현재 화면",
            "메인 전투화면" if report.is_battle_screen else "전투화면 아님",
            "ok" if report.is_battle_screen else "warn",
        ),
    ]


def write_page(path: Path, frame: np.ndarray, rows: list[ReportRow], **kwargs) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_page(frame, rows, **kwargs), encoding="utf-8")
    log.info("리포트 저장: %s", path)
    return path


def _encode(frame: np.ndarray) -> str:
    """프레임을 폰에서도 가벼운 JPEG data URI 로."""
    import cv2

    height, width = frame.shape[:2]
    if width > MAX_WIDTH:
        scale = MAX_WIDTH / width
        frame = cv2.resize(
            frame, (MAX_WIDTH, round(height * scale)), interpolation=cv2.INTER_AREA
        )

    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise RuntimeError("화면을 JPEG 로 인코딩하지 못했습니다.")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


# 퀘스트창의 황금/회색 대비를 그대로 팔레트로 쓴다. 이 페이지가 보여 주는
# 판단 자체가 그 두 색을 가르는 일이라서, 강조색을 따로 지어내지 않았다.
_TEMPLATE = """<title>{title}</title>
<style>
  :root {{
    color-scheme: light dark;
    --bg: #e9ecef;
    --surface: #ffffff;
    --line: #d3d8de;
    --ink: #171c22;
    --muted: #5f6b78;
    --gold: #a8720c;
    --gold-soft: #f6e5c0;
    --slate: #55606d;
    --slate-soft: #dde2e8;
    --ok: #1f6b4a;
    --ok-soft: #cfe8dc;
    --warn: #92400e;
    --warn-soft: #f7e0c8;
    --shadow: 0 1px 2px rgba(16, 22, 30, .08), 0 8px 24px rgba(16, 22, 30, .06);
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #12161b;
      --surface: #1a1f26;
      --line: #2b323b;
      --ink: #e4e8ec;
      --muted: #8a95a1;
      --gold: #e3ab4d;
      --gold-soft: #3b2f16;
      --slate: #9aa5b1;
      --slate-soft: #272e37;
      --ok: #6cc79b;
      --ok-soft: #16332a;
      --warn: #e0a35f;
      --warn-soft: #38281a;
      --shadow: 0 1px 2px rgba(0, 0, 0, .5), 0 8px 24px rgba(0, 0, 0, .35);
    }}
  }}
  :root[data-theme="light"] {{
    --bg: #e9ecef; --surface: #ffffff; --line: #d3d8de; --ink: #171c22;
    --muted: #5f6b78; --gold: #a8720c; --gold-soft: #f6e5c0;
    --slate: #55606d; --slate-soft: #dde2e8; --ok: #1f6b4a; --ok-soft: #cfe8dc;
    --warn: #92400e; --warn-soft: #f7e0c8;
    --shadow: 0 1px 2px rgba(16, 22, 30, .08), 0 8px 24px rgba(16, 22, 30, .06);
  }}
  :root[data-theme="dark"] {{
    --bg: #12161b; --surface: #1a1f26; --line: #2b323b; --ink: #e4e8ec;
    --muted: #8a95a1; --gold: #e3ab4d; --gold-soft: #3b2f16;
    --slate: #9aa5b1; --slate-soft: #272e37; --ok: #6cc79b; --ok-soft: #16332a;
    --warn: #e0a35f; --warn-soft: #38281a;
    --shadow: 0 1px 2px rgba(0, 0, 0, .5), 0 8px 24px rgba(0, 0, 0, .35);
  }}

  body {{
    margin: 0;
    padding: 20px 16px 48px;
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR",
                 system-ui, sans-serif;
    line-height: 1.5;
    -webkit-text-size-adjust: 100%;
  }}
  .wrap {{
    max-width: 560px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }}

  header {{ display: flex; flex-direction: column; gap: 4px; }}
  h1 {{
    margin: 0;
    font-size: 1.2rem;
    font-weight: 650;
    letter-spacing: -.015em;
    text-wrap: balance;
  }}
  .meta {{
    display: flex;
    flex-wrap: wrap;
    gap: 4px 12px;
    color: var(--muted);
    font-size: .8rem;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
    font-variant-numeric: tabular-nums;
  }}

  figure {{
    margin: 0;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 10px;
    box-shadow: var(--shadow);
  }}
  img {{
    display: block;
    width: 100%;
    height: auto;
    border-radius: 6px;
  }}

  .panel {{
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 14px;
    box-shadow: var(--shadow);
    overflow: hidden;
  }}
  .panel-title {{
    margin: 0;
    padding: 12px 16px;
    border-bottom: 1px solid var(--line);
    font-size: .7rem;
    font-weight: 600;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: var(--muted);
  }}
  .row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 11px 16px;
    border-top: 1px solid var(--line);
  }}
  .row:first-of-type {{ border-top: 0; }}
  .row-label {{ font-size: .9rem; }}
  .pill {{
    flex: none;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: .8rem;
    font-weight: 600;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
    font-variant-numeric: tabular-nums;
    text-align: right;
  }}
  .pill--gold {{ color: var(--gold); background: var(--gold-soft); }}
  .pill--gray {{ color: var(--slate); background: var(--slate-soft); }}
  .pill--ok {{ color: var(--ok); background: var(--ok-soft); }}
  .pill--warn {{ color: var(--warn); background: var(--warn-soft); }}
  .pill--neutral {{ color: var(--muted); background: var(--slate-soft); }}

  footer {{
    color: var(--muted);
    font-size: .78rem;
  }}
  code {{
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
    background: var(--slate-soft);
    padding: 2px 6px;
    border-radius: 5px;
  }}
</style>

<div class="wrap">
  <header>
    <h1>{title}</h1>
    <div class="meta"><span>{stamp}</span><span>{subtitle}</span></div>
  </header>

  <figure>
    <img src="{image}" alt="블루스택 게임 화면 캡처">
  </figure>

  <section class="panel">
    <h2 class="panel-title">인식 결과</h2>
{rows}
  </section>

  <footer>새로 찍으려면 <code>python main.py --shot --html</code></footer>
</div>
"""
