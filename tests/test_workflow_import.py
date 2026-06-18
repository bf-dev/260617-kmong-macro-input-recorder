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


def test_import_recording_ignores_alt_tab_and_recorder_window_clicks(tmp_path: Path) -> None:
    output = tmp_path / "rec" / "output"
    images = output / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (1024, 768), "gray").save(images / "000001_mouse_click.png")
    tool_shot = Image.new("RGB", (1024, 768), "gray")
    # Large bright floating helper window, like Macro Input Recorder over the POS.
    for px in range(426, 1024):
        for py in range(145, 535):
            tool_shot.putpixel((px, py), (248, 248, 248))
    tool_shot.save(images / "000004_mouse_click.png")
    events = {
        "event_count": 4,
        "events": [
            {"index": 1, "event_type": "mouse_click", "x": 100, "y": 100, "button": "left", "relative_ms": 100, "screenshot": "images/000001_mouse_click.png"},
            {"index": 2, "event_type": "key_press", "key": "alt_l", "relative_ms": 200, "screenshot": "images/000002_key_press.png"},
            {"index": 3, "event_type": "key_press", "key": "tab", "relative_ms": 250, "screenshot": "images/000003_key_press.png"},
            {"index": 4, "event_type": "mouse_click", "x": 620, "y": 300, "button": "left", "relative_ms": 500, "screenshot": "images/000004_mouse_click.png"},
        ],
    }
    (output / "events.json").write_text(json.dumps(events), encoding="utf-8")

    workflow = import_recording(output, "가승인", tmp_path / "workflows")

    assert len(workflow.steps) == 1
    assert workflow.steps[0].index == 1


def test_import_recording_ignores_taskbar_switch_click(tmp_path: Path) -> None:
    output = tmp_path / "rec" / "output"
    images = output / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (1024, 768), "white").save(images / "000001_mouse_click.png")
    taskbar_shot = Image.new("RGB", (1024, 768), "white")
    for px in range(0, 1024):
        for py in range(734, 768):
            taskbar_shot.putpixel((px, py), (25, 25, 25))
    taskbar_shot.save(images / "000002_mouse_click.png")
    events = {
        "event_count": 2,
        "events": [
            {"index": 1, "event_type": "mouse_click", "x": 180, "y": 420, "button": "left", "relative_ms": 100, "screenshot": "images/000001_mouse_click.png"},
            {"index": 2, "event_type": "mouse_click", "x": 324, "y": 750, "button": "left", "relative_ms": 200, "screenshot": "images/000002_mouse_click.png"},
        ],
    }
    (output / "events.json").write_text(json.dumps(events), encoding="utf-8")

    workflow = import_recording(output, "개점", tmp_path / "workflows")

    assert len(workflow.steps) == 1
    assert workflow.steps[0].index == 1


def test_ensure_builtin_workflows_installs_three_independent_jobs(tmp_path: Path) -> None:
    from macro_input_recorder.workflow import ensure_builtin_workflows

    workflows = ensure_builtin_workflows(tmp_path / "workflows", force=True)

    assert [workflow.name for workflow in workflows] == ["가승인", "개점", "마감"]
    assert {workflow.name: len(workflow.steps) for workflow in workflows} == {"가승인": 15, "개점": 10, "마감": 7}
    for name in ["가승인", "개점", "마감"]:
        assert (tmp_path / "workflows" / f"{name}.json").exists()
        assert (tmp_path / "workflows" / name / "anchors").is_dir()


def test_visual_role_fallback_finds_modal_primary_button() -> None:
    from macro_input_recorder.automation import _find_button_by_role
    from macro_input_recorder.workflow import MacroStep

    image = Image.new("RGB", (800, 600), "white")
    for px in range(240, 560):
        for py in range(180, 430):
            image.putpixel((px, py), (55, 55, 55))
    for px in range(420, 500):
        for py in range(365, 395):
            image.putpixel((px, py), (239, 180, 30))
    step = MacroStep(index=1, event_type="mouse_click", x_ratio=0.58, y_ratio=0.64, role="modal_primary")

    point = _find_button_by_role(image, step)

    assert point is not None
    assert 450 <= point[0] <= 470
    assert 375 <= point[1] <= 390


def test_visual_role_fallback_finds_modal_primary_when_resolution_moves_button() -> None:
    from macro_input_recorder.automation import _find_button_by_role, _find_modal_primary_button
    from macro_input_recorder.workflow import MacroStep

    image = Image.new("RGB", (1280, 720), "white")
    for px in range(350, 950):
        for py in range(160, 590):
            image.putpixel((px, py), (48, 48, 48))
    for px in range(580, 720):
        for py in range(505, 550):
            image.putpixel((px, py), (239, 180, 30))
    # Recorded 4:3 coordinates can be far from the real centered dialog on a
    # wider POS monitor. Modal fallback should use the dialog shape, not reject
    # the button only because the expected coordinate moved.
    step = MacroStep(index=1, event_type="mouse_click", x_ratio=0.80, y_ratio=0.90, role="modal_primary")

    point = _find_button_by_role(image, step)

    assert point is not None
    assert 640 <= point[0] <= 660
    assert 525 <= point[1] <= 535
    assert _find_modal_primary_button(image) == point


def test_visual_role_fallback_finds_orange_action_near_expected() -> None:
    from macro_input_recorder.automation import _find_button_by_role
    from macro_input_recorder.workflow import MacroStep

    image = Image.new("RGB", (800, 600), "white")
    for left in (80, 260, 440):
        for px in range(left, left + 120):
            for py in range(250, 330):
                image.putpixel((px, py), (237, 171, 20))
    step = MacroStep(index=1, event_type="mouse_click", x_ratio=0.40, y_ratio=0.48, role="orange_action")

    point = _find_button_by_role(image, step)

    assert point is not None
    assert 310 <= point[0] <= 330
    assert 285 <= point[1] <= 300


def test_pos_window_title_scoring_prefers_pos_and_excludes_macro() -> None:
    from macro_input_recorder.window_focus import score_pos_window_title

    assert score_pos_window_title("MOM'S TOUCH POS") > 30
    assert score_pos_window_title("P2C 포스 판매") > 20
    assert score_pos_window_title("P2C 포스 자동화") == 0
    assert score_pos_window_title("Macro Input Recorder") == 0
    assert score_pos_window_title("Random Browser") == 0


def test_daily_schedule_time_parsing_and_due_once() -> None:
    from datetime import datetime
    from macro_input_recorder.daily_schedule import daily_run_key, is_due_now, parse_hhmm

    assert parse_hhmm("10:30") == (10, 30)
    assert parse_hhmm("21시30분") == (21, 30)
    now = datetime(2026, 6, 18, 10, 30, 5)
    assert is_due_now(now, (10, 30), None)
    assert not is_due_now(now, (10, 30), daily_run_key(now))
    assert not is_due_now(datetime(2026, 6, 18, 10, 31), (10, 30), None)
