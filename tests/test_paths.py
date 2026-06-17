from datetime import datetime, timezone
from pathlib import Path

from macro_input_recorder.paths import make_session_paths, started_folder_name


def test_started_folder_name_is_file_system_friendly() -> None:
    started = datetime(2026, 6, 17, 9, 8, 7, tzinfo=timezone.utc)
    assert started_folder_name(started) == "20260617_090807"


def test_make_session_paths_creates_output_tree(tmp_path: Path) -> None:
    started = datetime(2026, 6, 17, 9, 8, 7, tzinfo=timezone.utc)
    paths = make_session_paths(tmp_path, started)

    assert paths.session_dir == tmp_path / "20260617_090807"
    assert paths.output_dir == tmp_path / "20260617_090807" / "output"
    assert paths.images_dir.is_dir()
    assert paths.events_json.name == "events.json"
    assert paths.events_jsonl.name == "events.jsonl"
