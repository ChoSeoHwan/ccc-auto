"""이미 연결된 ADB 장치를 유지하는 규칙의 BDD 스텝 정의."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from ccc.adb.client import AdbClient

scenarios("features/adb_connection.feature")

pytestmark = pytest.mark.no_frames


@pytest.fixture
def world(monkeypatch) -> dict:
    calls = {"connect": 0, "device_lists": []}
    monkeypatch.setattr("ccc.adb.client.find_adb", lambda _preferred: "adb")

    def fake_run(command, **_kwargs):
        assert command == ["adb", "connect", "localhost:6520"]
        calls["connect"] += 1
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr("ccc.adb.client.subprocess.run", fake_run)
    return {"calls": calls, "monkeypatch": monkeypatch}


@given(parsers.parse('"{serial}" 장치가 이미 device 상태이다'))
def given_already_connected(world, serial: str):
    world["serial"] = serial
    world["calls"]["device_lists"] = [[serial]]


@given(parsers.parse('"{serial}" 장치가 처음에는 목록에 없다'))
def given_not_connected(world, serial: str):
    world["serial"] = serial
    world["calls"]["device_lists"] = [[], [serial]]


@given("adb connect 뒤에는 device 상태가 된다")
def given_connected_after_connect(world):
    assert len(world["calls"]["device_lists"]) == 2


@when("ADB 클라이언트를 연결하면")
def when_connect_client(world):
    device_lists = iter(world["calls"]["device_lists"])
    world["monkeypatch"].setattr(
        "ccc.adb.client.list_devices", lambda _adb_path: next(device_lists)
    )
    client = AdbClient(world["serial"])
    world["monkeypatch"].setattr(client, "display_size", lambda: (608, 1080))
    world["monkeypatch"].setattr(
        client, "shell", lambda _command: "HPE device\n"
    )
    world["device"] = client.connect()


@then("adb connect를 호출하지 않는다")
def then_does_not_reconnect(world):
    assert world["calls"]["connect"] == 0


@then("adb connect를 한 번 호출한다")
def then_connects_once(world):
    assert world["calls"]["connect"] == 1


@then("기존 장치 정보를 그대로 읽는다")
@then("새로 연결된 장치 정보를 읽는다")
def then_reads_device(world):
    device = world["device"]
    assert device.serial == "localhost:6520"
    assert (device.width, device.height, device.model) == (608, 1080, "HPE device")
