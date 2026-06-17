from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class SessionPaths:
    session_dir: Path
    output_dir: Path
    images_dir: Path
    events_json: Path
    events_jsonl: Path


def default_desktop() -> Path:
    """Return the user's Desktop folder, creating it when it is missing."""
    desktop = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    return desktop


def default_recordings_root() -> Path:
    return default_desktop() / "recording"


def started_folder_name(started_at: datetime) -> str:
    return started_at.strftime("%Y%m%d_%H%M%S")


def make_session_paths(recordings_root: Path | None = None, started_at: datetime | None = None) -> SessionPaths:
    started_at = started_at or datetime.now().astimezone()
    root = recordings_root or default_recordings_root()
    session_dir = root / started_folder_name(started_at)
    output_dir = session_dir / "output"
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    return SessionPaths(
        session_dir=session_dir,
        output_dir=output_dir,
        images_dir=images_dir,
        events_json=output_dir / "events.json",
        events_jsonl=output_dir / "events.jsonl",
    )
