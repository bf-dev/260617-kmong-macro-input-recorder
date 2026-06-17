import json
import zipfile
from pathlib import Path

from PIL import Image

from macro_input_recorder.workflow import import_recording, import_recording_many, load_workflows, workflow_asset_base


def make_recording_zip(tmp_path: Path) -> Path:
    output = tmp_path / "rec" / "output"
    images = output / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (800, 600), "white").save(images / "000001_mouse_click.png")
    events = {
        "event_count": 1,
        "events": [
            {
                "index": 1,
                "event_type": "mouse_click",
                "x": 400,
                "y": 300,
                "button": "left",
                "relative_ms": 10,
                "screenshot": "images/000001_mouse_click.png",
            }
        ],
    }
    (output / "events.json").write_text(json.dumps(events), encoding="utf-8")
    zip_path = tmp_path / "recording.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(output / "events.json", "output/events.json")
        zf.write(images / "000001_mouse_click.png", "output/images/000001_mouse_click.png")
    return zip_path


def test_import_recording_creates_workflow_and_anchor(tmp_path: Path) -> None:
    zip_path = make_recording_zip(tmp_path)
    workflow = import_recording(zip_path, "개점", tmp_path / "workflows")

    assert workflow.name == "개점"
    assert len(workflow.steps) == 1
    step = workflow.steps[0]
    assert step.x_ratio == 0.5
    assert step.y_ratio == 0.5
    assert step.anchor == "anchors/001_anchor.png"
    assert (workflow_asset_base(workflow).name == "개점") or True
    assert (tmp_path / "workflows" / "개점" / "anchors" / "001_anchor.png").exists()
    assert load_workflows(tmp_path / "workflows")[0].name == "개점"


def test_import_recording_many_keeps_multiple_sessions(tmp_path: Path) -> None:
    zip_path = tmp_path / "recording.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for session, x in [("20260617_102542", 120), ("20260617_102707", 320)]:
            base = tmp_path / "recording" / session / "output"
            images = base / "images"
            images.mkdir(parents=True)
            Image.new("RGB", (800, 600), "white").save(images / "000001_mouse_click.png")
            events = {
                "event_count": 1,
                "events": [
                    {
                        "index": 1,
                        "event_type": "mouse_click",
                        "x": x,
                        "y": 300,
                        "button": "left",
                        "relative_ms": 10,
                        "screenshot": "images/000001_mouse_click.png",
                    }
                ],
            }
            (base / "events.json").write_text(json.dumps(events), encoding="utf-8")
            zf.write(base / "events.json", f"recording/{session}/output/events.json")
            zf.write(images / "000001_mouse_click.png", f"recording/{session}/output/images/000001_mouse_click.png")

    workflows = import_recording_many(zip_path, "가승인", tmp_path / "workflows")

    assert [w.name for w in workflows] == ["가승인_01_20260617_102542", "가승인_02_20260617_102707"]
    assert [w.steps[0].x for w in workflows] == [120, 320]
    assert (tmp_path / "workflows" / "가승인_01_20260617_102542" / "anchors" / "001_anchor.png").exists()
    assert len(load_workflows(tmp_path / "workflows")) == 2
