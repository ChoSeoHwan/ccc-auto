"""그림 파일 읽고 쓰기.

``cv2.imwrite`` 는 윈도우 기본 코드페이지에 없는 글자가 경로에 섞이면 조용히
실패한다. 그래서 오븐 레벨업 진단 화면이 한 장도 남지 않았다 — 이름에
'확인창' 이 들어 있었기 때문이다. 로그에는 저장했다고 찍혀 있었다.

게임 화면 없이 돈다.
"""

from __future__ import annotations

import numpy as np
import pytest

from ccc.vision import imread, imwrite

pytestmark = pytest.mark.no_frames

IMAGE = np.full((12, 20, 3), (40, 163, 245), np.uint8)


@pytest.mark.parametrize("name", ["ascii.png", "한글-확인창.png", "레벨업 누른 뒤.png"])
def test_어떤_이름이든_쓰고_다시_읽는다(tmp_path, name: str):
    path = tmp_path / name

    assert imwrite(path, IMAGE), f"쓰지 못했습니다: {name}"
    assert path.exists(), "성공이라 했는데 파일이 없습니다"

    back = imread(path)
    assert back is not None, "다시 읽지 못했습니다"
    assert back.shape == IMAGE.shape
    assert np.array_equal(back, IMAGE)


def test_없는_파일은_None(tmp_path):
    assert imread(tmp_path / "없는파일.png") is None


def test_빈_파일은_None(tmp_path):
    path = tmp_path / "빈파일.png"
    path.write_bytes(b"")

    assert imread(path) is None


def test_못_쓰면_False(tmp_path):
    """폴더가 없으면 실패다. 예외로 터지지 않고 False 로 알린다."""
    assert imwrite(tmp_path / "없는폴더" / "그림.png", IMAGE) is False
