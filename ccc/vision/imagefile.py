"""그림 파일 읽고 쓰기.

``cv2.imread`` 와 ``cv2.imwrite`` 는 경로를 시스템 인코딩으로 넘긴다. 윈도우
기본 코드페이지(cp949)에 없는 글자가 경로에 섞이면 **조용히 실패한다** —
예외도 없고, ``imwrite`` 는 ``False`` 만 돌려준다.

실제로 그 때문에 오븐 레벨업 진단 화면이 한 장도 남지 않았다. 파일 이름에
'확인창' 같은 한글을 썼기 때문이다. 로그에는 "화면 저장: ...확인창.png" 가
찍혀 있었지만 폴더는 비어 있었다. 그러면 가끔만 지나가는 화면을 놓치고,
없는 파일을 있다고 알린다.

    ascii-test.png   imwrite=True   파일존재=True
    한글-test.png    imwrite=False  파일존재=False

그래서 바이트로 인코딩한 뒤 파이썬으로 읽고 쓴다. 경로는 파이썬이 다루므로
인코딩 문제가 없다. 그림을 파일로 다룰 일은 전부 여기를 거친다.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


def imread(path: Path | str, flags: int | None = None) -> np.ndarray | None:
    """그림을 읽는다. 없거나 못 읽으면 ``None``."""
    import cv2

    if flags is None:
        flags = cv2.IMREAD_COLOR
    try:
        data = np.fromfile(str(path), np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)


def imwrite(path: Path | str, image: np.ndarray) -> bool:
    """그림을 쓴다. 성공하면 True.

    **돌려준 값을 반드시 확인해라.** 저장했다고 알려 놓고 파일이 없으면,
    나중에 그 파일을 찾는 사람이 무엇이 잘못됐는지 알아낼 길이 없다.
    """
    import cv2

    target = Path(path)
    ok, buffer = cv2.imencode(target.suffix or ".png", image)
    if not ok:
        log.warning("그림을 인코딩하지 못했습니다: %s", target)
        return False
    try:
        buffer.tofile(str(target))
    except OSError:
        log.exception("그림을 쓰지 못했습니다: %s", target)
        return False
    return True
