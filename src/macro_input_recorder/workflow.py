from __future__ import annotations

import json
import shutil
import zipfile
import importlib.resources as resources
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

WORKFLOW_VERSION = 1
ANCHOR_SIZE = 180
SYSTEM_NAVIGATION_KEYS = {
    "alt",
    "alt_l",
    "alt_r",
    "cmd",
    "cmd_l",
    "cmd_r",
    "meta",
    "super",
    "win",
    "windows",
}


@dataclass
class MacroStep:
    index: int
    event_type: str
    x: int | None = None
    y: int | None = None
    screen_width: int | None = None
    screen_height: int | None = None
    x_ratio: float | None = None
    y_ratio: float | None = None
    button: str | None = None
    key: str | None = None
    char: str | None = None
    anchor: str | None = None
    anchor_offset_x: int | None = None
    anchor_offset_y: int | None = None
    wait_after_ms: int = 250
    role: str = ""
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MacroStep":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None and v != ""}


@dataclass
class MacroWorkflow:
    name: str
    source: str
    steps: list[MacroStep] = field(default_factory=list)
    created_from: str = ""
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MacroWorkflow":
        return cls(
            name=str(data.get("name", "녹화 작업")),
            source=str(data.get("source", "manual")),
            steps=[MacroStep.from_dict(item) for item in data.get("steps", [])],
            created_from=str(data.get("created_from", "")),
            description=str(data.get("description", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": WORKFLOW_VERSION,
            "name": self.name,
            "source": self.source,
            "created_from": self.created_from,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
        }


def app_data_dir() -> Path:
    root = Path.home() / "Documents" / "P2C_POS_자동화"
    root.mkdir(parents=True, exist_ok=True)
    return root


def workflows_dir() -> Path:
    path = app_data_dir() / "workflows"
    path.mkdir(parents=True, exist_ok=True)
    return path


def workflow_file(name: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name).strip("_") or "workflow"
    return workflows_dir() / f"{safe}.json"




BUILTIN_WORKFLOW_VERSION = "2026-06-18-fixed-coordinate-first-v1"
BUILTIN_WORKFLOW_NAMES = ("가승인", "개점", "마감")


def ensure_builtin_workflows(root: Path | None = None, force: bool = False) -> list[MacroWorkflow]:
    """Install bundled P2C workflows into user data so the EXE works alone.

    The delivered program should not ask the customer to import recording.zip.
    We copy package-bundled workflows and anchor images on first run (or when
    the bundled version changes), then normal loading/running uses the same
    user-data structure as custom workflows.
    """
    folder = root or workflows_dir()
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / ".builtin_version"
    current_version = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
    if force or current_version != BUILTIN_WORKFLOW_VERSION:
        _copy_builtin_workflow_files(folder)
        marker.write_text(BUILTIN_WORKFLOW_VERSION, encoding="utf-8")
    workflows = load_workflows(folder)
    return [workflow for workflow in workflows if workflow.name in BUILTIN_WORKFLOW_NAMES]


def _copy_builtin_workflow_files(folder: Path) -> None:
    package = "macro_input_recorder.builtin_workflows"
    package_root = resources.files(package)
    for name in BUILTIN_WORKFLOW_NAMES:
        json_text = (package_root / f"{name}.json").read_text(encoding="utf-8")
        (folder / f"{name}.json").write_text(json_text, encoding="utf-8")
        source_dir = package_root / name
        target_dir = folder / _safe_name(name)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        _copy_resource_tree(source_dir, target_dir)


def _copy_resource_tree(source: resources.abc.Traversable, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            _copy_resource_tree(item, destination)
        else:
            destination.write_bytes(item.read_bytes())


def load_workflows(root: Path | None = None) -> list[MacroWorkflow]:
    folder = root or workflows_dir()
    if not folder.exists():
        return []
    workflows: list[MacroWorkflow] = []
    for path in sorted(folder.glob("*.json")):
        try:
            workflows.append(MacroWorkflow.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return workflows


def save_workflow(workflow: MacroWorkflow, root: Path | None = None) -> Path:
    folder = root or workflows_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = workflow_file(workflow.name) if root is None else folder / f"{workflow.name}.json"
    path.write_text(json.dumps(workflow.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def import_recording(source: Path, workflow_name: str, root: Path | None = None) -> MacroWorkflow:
    """Import one MacroInputRecorder output zip/folder into a replayable workflow.

    Expected input forms:
    - recording.zip containing output/events.json and output/images/*.png
    - a folder containing output/events.json
    - the output folder itself containing events.json
    """
    return import_recording_many(source, workflow_name, root)[0]


def import_recording_many(source: Path, workflow_name: str, root: Path | None = None) -> list[MacroWorkflow]:
    """Import every recording session found in a zip/folder.

    Customer recordings often arrive as one `recording.zip` containing several
    timestamped recording folders. In that case each `events.json` becomes a
    separate workflow so no sequence is silently ignored.
    """
    base = root or workflows_dir()
    base.mkdir(parents=True, exist_ok=True)
    source_name = _safe_name(workflow_name)
    staging = base / f"_{source_name}_import_source"
    if staging.exists():
        shutil.rmtree(staging)
    source_root = _extract_or_locate(source, staging)
    events_paths = _find_all_events_json(source_root)
    if not events_paths:
        raise FileNotFoundError("events.json을 찾지 못했습니다. recording.zip 전체를 선택해주세요.")
    if len(events_paths) == 1:
        return [_import_events_file(events_paths[0], workflow_name, str(source), base)]

    workflows: list[MacroWorkflow] = []
    for idx, events_path in enumerate(events_paths, start=1):
        session_name = events_path.parent.parent.name if events_path.parent.name == "output" else events_path.parent.name
        name = f"{workflow_name}_{idx:02d}_{session_name}"
        workflows.append(_import_events_file(events_path, name, str(source), base))
    return workflows


def _import_events_file(events_path: Path, workflow_name: str, created_from: str, base: Path) -> MacroWorkflow:
    target = base / _safe_name(workflow_name)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    data = json.loads(events_path.read_text(encoding="utf-8"))
    events = data.get("events") or []

    image_target = target / "anchors"
    image_target.mkdir(parents=True, exist_ok=True)

    steps: list[MacroStep] = []
    previous_ms = 0
    alt_seen = False
    ignore_rest = False
    for raw in events:
        event_type = str(raw.get("event_type", "input"))
        if event_type not in {"mouse_click", "key_press"}:
            continue
        key = str(raw.get("key", "")).lower().replace("key.", "") if raw.get("key") else ""
        if ignore_rest:
            continue
        if event_type == "key_press" and key in SYSTEM_NAVIGATION_KEYS:
            alt_seen = key.startswith("alt")
            continue
        if event_type == "key_press" and key == "tab" and alt_seen:
            ignore_rest = True
            continue
        index = int(raw.get("index", len(steps) + 1))
        rel_ms = int(raw.get("relative_ms") or previous_ms)
        wait_after_ms = max(120, min(2500, rel_ms - previous_ms)) if steps else 250
        previous_ms = rel_ms
        screenshot_path = _resolve_screenshot(events_path.parent, raw)
        width = height = None
        anchor_rel = None
        offset_x = offset_y = None
        x = _optional_int(raw.get("x"))
        y = _optional_int(raw.get("y"))
        if screenshot_path and screenshot_path.exists():
            if event_type == "mouse_click" and x is not None and y is not None and (
                _looks_like_taskbar_switch_click(screenshot_path, x, y)
                or _looks_like_recorder_window_click(screenshot_path, x, y)
            ):
                continue
            with Image.open(screenshot_path) as img:
                width, height = img.size
                if x is not None and y is not None and event_type == "mouse_click":
                    anchor_name, offset_x, offset_y = _write_anchor(img, x, y, image_target, index)
                    anchor_rel = f"anchors/{anchor_name}"

        step = MacroStep(
            index=index,
            event_type=event_type,
            x=x,
            y=y,
            screen_width=width,
            screen_height=height,
            x_ratio=(x / width) if x is not None and width else None,
            y_ratio=(y / height) if y is not None and height else None,
            button=str(raw.get("button", "left")) if event_type == "mouse_click" else None,
            key=str(raw.get("key", "")) if raw.get("key") else None,
            char=str(raw.get("char", "")) if raw.get("char") else None,
            anchor=anchor_rel,
            anchor_offset_x=offset_x,
            anchor_offset_y=offset_y,
            wait_after_ms=wait_after_ms,
            role=_infer_click_role(screenshot_path, x, y) if screenshot_path and screenshot_path.exists() and x is not None and y is not None and event_type == "mouse_click" else "",
        )
        steps.append(step)

    workflow = MacroWorkflow(
        name=workflow_name,
        source="recording",
        created_from=created_from,
        description=f"{len(steps)}개 입력 단계가 녹화 파일에서 생성되었습니다.",
        steps=steps,
    )
    (target / "workflow.json").write_text(json.dumps(workflow.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    save_workflow(workflow, base)
    return workflow


def workflow_asset_base(workflow: MacroWorkflow) -> Path:
    return workflows_dir() / _safe_name(workflow.name)


def _extract_or_locate(source: Path, target: Path) -> Path:
    source = source.expanduser().resolve()
    if source.is_dir():
        return source
    target.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as zf:
            zf.extractall(target)
        return target
    raise ValueError("recording.zip 또는 녹화 output 폴더를 선택해주세요.")


def _find_events_json(root: Path) -> Path:
    candidates = [root / "events.json", root / "output" / "events.json"] + list(root.rglob("events.json"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("events.json을 찾지 못했습니다. recording.zip 전체를 선택해주세요.")


def _find_all_events_json(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for candidate in [root / "events.json", root / "output" / "events.json"]:
        if candidate.exists():
            candidates.append(candidate)
    for candidate in sorted(root.rglob("events.json")):
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _resolve_screenshot(output_dir: Path, event: dict[str, Any]) -> Path | None:
    screenshot = event.get("screenshot")
    if screenshot:
        return output_dir / str(screenshot)
    screenshot_path = event.get("screenshot_path")
    if screenshot_path:
        return Path(str(screenshot_path))
    return None


def _write_anchor(img: Image.Image, x: int, y: int, target: Path, index: int) -> tuple[str, int, int]:
    half = ANCHOR_SIZE // 2
    left = max(0, x - half)
    top = max(0, y - half)
    right = min(img.width, x + half)
    bottom = min(img.height, y + half)
    if right - left < 40 or bottom - top < 40:
        left = max(0, min(left, img.width - 40))
        top = max(0, min(top, img.height - 40))
        right = min(img.width, left + max(40, right - left))
        bottom = min(img.height, top + max(40, bottom - top))
    anchor = img.crop((left, top, right, bottom))
    name = f"{index:03d}_anchor.png"
    anchor.save(target / name)
    return name, x - left, y - top


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _looks_like_recorder_window_click(screenshot_path: Path, x: int, y: int) -> bool:
    """Best-effort filter for clicks on the Macro Input Recorder itself.

    When the operator stops a recording, the recorder window is captured as a
    large bright floating panel. Replaying that final click would click our
    helper program instead of the POS screen, so importer-side filtering keeps
    those tool-control clicks out of the workflow.
    """
    try:
        import cv2
        import numpy as np

        with Image.open(screenshot_path) as img:
            arr = np.array(img.convert("RGB"))
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        mask = (gray > 235).astype("uint8")
        num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        for idx in range(1, num):
            left, top, width, height, area = [int(v) for v in stats[idx]]
            if not (left <= x <= left + width and top <= y <= top + height):
                continue
            fill_ratio = area / max(1, width * height)
            if (
                350 <= left <= 520
                and 80 <= top <= 220
                and 520 <= width <= 760
                and 300 <= height <= 460
                and fill_ratio >= 0.85
            ):
                return True
    except Exception:
        return False
    return False


def _looks_like_taskbar_switch_click(screenshot_path: Path, x: int, y: int) -> bool:
    """Filter taskbar/app-switch clicks used to return to the recorder."""
    try:
        import numpy as np

        with Image.open(screenshot_path) as img:
            arr = np.array(img.convert("RGB"))
        height, width = arr.shape[:2]
        if y < height - 36:
            return False
        left = max(0, x - 25)
        right = min(width, x + 25)
        top = max(0, y - 15)
        bottom = min(height, y + 15)
        click_region = arr[top:bottom, left:right]
        bottom_band = arr[max(0, height - 34) : height, :, :]
        click_dark_ratio = (click_region.mean(axis=2) < 90).mean()
        band_dark_ratio = (bottom_band.mean(axis=2) < 90).mean()
        return bool(click_dark_ratio > 0.35 and band_dark_ratio > 0.20)
    except Exception:
        return False



def _infer_click_role(screenshot_path: Path, x: int, y: int) -> str:
    """Classify common POS clicks for smarter runtime fallback.

    This is deliberately simple and visual: it detects the customer's POS orange
    action tiles and the dark confirmation dialogs with yellow/white buttons.
    Runtime can then recover even when exact template matching fails.
    """
    try:
        import numpy as np

        with Image.open(screenshot_path) as img:
            arr = np.array(img.convert("RGB"))
        height, width = arr.shape[:2]
        left = max(0, x - 12)
        right = min(width, x + 12)
        top = max(0, y - 12)
        bottom = min(height, y + 12)
        patch = arr[top:bottom, left:right]
        if patch.size == 0:
            return ""
        r, g, b = patch.reshape(-1, 3).mean(axis=0)
        gray = arr.mean(axis=2)
        dark_modal = (gray < 95).mean() > 0.08
        if dark_modal and r > 180 and 120 <= g <= 210 and b < 80:
            return "modal_primary"
        if dark_modal and r > 210 and g > 210 and b > 210:
            return "modal_secondary"
        if r > 180 and 120 <= g <= 210 and b < 100:
            return "orange_action"
        if r > 140 and g > 140 and b > 140:
            return "light_button"
    except Exception:
        return ""
    return ""


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name).strip("_") or "workflow"
