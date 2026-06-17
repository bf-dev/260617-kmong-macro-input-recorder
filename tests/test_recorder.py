import json
from datetime import datetime, timezone
from pathlib import Path

from macro_input_recorder.recorder import InputRecorder


class FakeScreenshotter:
    def capture(self, path: Path) -> None:
        path.write_bytes(b"fake png")


class FakeKey:
    char = "a"
    name = None


def test_recorder_writes_json_and_screenshots(tmp_path: Path) -> None:
    recorder = InputRecorder(screenshotter=FakeScreenshotter())
    started = datetime(2026, 6, 17, 9, 8, 7, tzinfo=timezone.utc)
    paths = recorder.start(tmp_path, started, start_listeners=False)

    recorder.record_mouse_click(120, 230, "left", True)
    recorder.record_key_press(FakeKey())
    assert recorder.wait_idle(timeout=5)
    snapshot = recorder.stop()

    assert snapshot.event_count == 2
    assert paths.events_json.exists()
    data = json.loads(paths.events_json.read_text(encoding="utf-8"))
    assert data["event_count"] == 2
    assert data["events"][0]["event_type"] == "mouse_click"
    assert data["events"][0]["x"] == 120
    assert data["events"][0]["y"] == 230
    assert data["events"][0]["screenshot"] == "images/000001_mouse_click.png"
    assert data["events"][1]["event_type"] == "key_press"
    assert data["events"][1]["char"] == "a"
    assert (paths.images_dir / "000001_mouse_click.png").read_bytes() == b"fake png"
    assert (paths.images_dir / "000002_key_press.png").read_bytes() == b"fake png"
    assert len(paths.events_jsonl.read_text(encoding="utf-8").splitlines()) == 2


def test_mouse_release_is_not_recorded(tmp_path: Path) -> None:
    recorder = InputRecorder(screenshotter=FakeScreenshotter())
    recorder.start(tmp_path, start_listeners=False)
    recorder.record_mouse_click(10, 20, "left", False)
    assert recorder.wait_idle(timeout=1)
    snapshot = recorder.stop()
    assert snapshot.event_count == 0
