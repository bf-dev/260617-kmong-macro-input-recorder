from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .capture import MssScreenshotter, Screenshotter
from .paths import SessionPaths, make_session_paths


@dataclass(frozen=True)
class RecorderSnapshot:
    running: bool
    event_count: int
    session_dir: Path | None
    output_dir: Path | None
    last_error: str | None


class InputRecorder:
    """Visible local input recorder for macro preparation.

    The listener callbacks only enqueue input metadata. A worker thread writes one
    screenshot and updates events.json/events.jsonl for each queued input event.
    """

    def __init__(self, screenshotter: Screenshotter | None = None) -> None:
        self._screenshotter = screenshotter or MssScreenshotter()
        self._lock = threading.RLock()
        self._queue: queue.Queue[dict[str, Any] | None] | None = None
        self._worker: threading.Thread | None = None
        self._mouse_listener: Any | None = None
        self._keyboard_listener: Any | None = None
        self._mouse_controller: Any | None = None
        self._paths: SessionPaths | None = None
        self._started_at: datetime | None = None
        self._started_perf: float = 0.0
        self._events: list[dict[str, Any]] = []
        self._running = False
        self._last_error: str | None = None

    def start(
        self,
        recordings_root: Path | None = None,
        started_at: datetime | None = None,
        *,
        start_listeners: bool = True,
    ) -> SessionPaths:
        with self._lock:
            if self._running:
                raise RuntimeError("Recording is already running.")
            self._started_at = started_at or datetime.now().astimezone()
            self._started_perf = time.perf_counter()
            self._paths = make_session_paths(recordings_root, self._started_at)
            self._events = []
            self._last_error = None
            self._queue = queue.Queue()
            self._running = True
            self._write_events_json()
            self._worker = threading.Thread(target=self._worker_loop, name="input-recorder-writer", daemon=True)
            self._worker.start()

        if start_listeners:
            try:
                self._start_listeners()
            except Exception:
                self.stop()
                raise
        return self._paths

    def stop(self) -> RecorderSnapshot:
        with self._lock:
            if not self._running:
                return self.snapshot()
            self._running = False
            mouse_listener = self._mouse_listener
            keyboard_listener = self._keyboard_listener
            event_queue = self._queue
            worker = self._worker
            self._mouse_listener = None
            self._keyboard_listener = None

        for listener in (mouse_listener, keyboard_listener):
            if listener is not None:
                try:
                    listener.stop()
                except Exception as exc:  # pragma: no cover - defensive around OS hooks
                    self._set_error(f"Listener stop error: {exc}")

        if event_queue is not None:
            event_queue.put(None)
        if worker is not None:
            worker.join(timeout=10)
            if worker.is_alive():
                self._set_error("Timed out while writing the last recorder events.")

        with self._lock:
            self._write_events_json()
            self._queue = None
            self._worker = None
            return self.snapshot()

    def wait_idle(self, timeout: float = 10.0) -> bool:
        """Wait until all queued events have been written. Mainly used by tests."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                event_queue = self._queue
            if event_queue is None or event_queue.unfinished_tasks == 0:
                return True
            time.sleep(0.02)
        return False

    def snapshot(self) -> RecorderSnapshot:
        with self._lock:
            return RecorderSnapshot(
                running=self._running,
                event_count=len(self._events),
                session_dir=self._paths.session_dir if self._paths else None,
                output_dir=self._paths.output_dir if self._paths else None,
                last_error=self._last_error,
            )

    def record_mouse_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        if not pressed:
            return
        self._enqueue(
            {
                "event_type": "mouse_click",
                "x": int(x),
                "y": int(y),
                "button": _safe_button_name(button),
                "pressed": bool(pressed),
            }
        )

    def record_key_press(self, key: Any) -> None:
        x, y = self._current_mouse_position()
        description = _describe_key(key)
        self._enqueue(
            {
                "event_type": "key_press",
                "x": x,
                "y": y,
                **description,
            }
        )

    def _start_listeners(self) -> None:
        from pynput import keyboard, mouse

        self._mouse_controller = mouse.Controller()
        self._mouse_listener = mouse.Listener(on_click=self.record_mouse_click)
        self._keyboard_listener = keyboard.Listener(on_press=self.record_key_press)
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def _enqueue(self, payload: dict[str, Any]) -> None:
        event_time = datetime.now().astimezone()
        with self._lock:
            if not self._running or self._queue is None:
                return
            payload = dict(payload)
            payload["timestamp"] = event_time.isoformat(timespec="milliseconds")
            payload["relative_ms"] = int((time.perf_counter() - self._started_perf) * 1000)
            self._queue.put(payload)

    def _worker_loop(self) -> None:
        while True:
            with self._lock:
                event_queue = self._queue
            if event_queue is None:
                return
            payload = event_queue.get()
            try:
                if payload is None:
                    return
                self._write_event(payload)
            finally:
                event_queue.task_done()

    def _write_event(self, payload: dict[str, Any]) -> None:
        with self._lock:
            paths = self._paths
            if paths is None:
                return
            index = len(self._events) + 1
        event_type = str(payload.get("event_type", "input"))
        image_name = f"{index:06d}_{event_type}.png"
        image_path = paths.images_dir / image_name
        screenshot_error: str | None = None
        captured_at: str | None = None

        try:
            self._screenshotter.capture(image_path)
            captured_at = datetime.now().astimezone().isoformat(timespec="milliseconds")
        except Exception as exc:  # pragma: no cover - depends on desktop capture permissions
            screenshot_error = str(exc)
            self._set_error(f"Screenshot failed for event {index}: {exc}")

        event = {
            "index": index,
            **payload,
            "screenshot": f"images/{image_name}",
            "screenshot_path": str(image_path),
            "screenshot_captured_at": captured_at,
        }
        if screenshot_error:
            event["screenshot_error"] = screenshot_error

        with self._lock:
            self._events.append(event)
            self._append_events_jsonl(event)
            self._write_events_json()

    def _current_mouse_position(self) -> tuple[int | None, int | None]:
        try:
            if self._mouse_controller is not None:
                x, y = self._mouse_controller.position
                return int(x), int(y)
        except Exception:
            pass
        return None, None

    def _append_events_jsonl(self, event: dict[str, Any]) -> None:
        if self._paths is None:
            return
        with self._paths.events_jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _write_events_json(self) -> None:
        if self._paths is None or self._started_at is None:
            return
        data = {
            "schema_version": 1,
            "recording_started_at": self._started_at.isoformat(timespec="milliseconds"),
            "recording_stopped_at": None if self._running else datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "event_count": len(self._events),
            "output_dir": str(self._paths.output_dir),
            "images_dir": str(self._paths.images_dir),
            "events": self._events,
        }
        tmp_path = self._paths.events_json.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self._paths.events_json)

    def _set_error(self, message: str) -> None:
        with self._lock:
            self._last_error = message


def _safe_button_name(button: Any) -> str:
    name = getattr(button, "name", None)
    if name:
        return str(name)
    text = str(button)
    return text.replace("Button.", "")


def _describe_key(key: Any) -> dict[str, Any]:
    char = getattr(key, "char", None)
    name = getattr(key, "name", None)
    key_text = char if char is not None else (name if name is not None else str(key))
    return {
        "key": key_text,
        "key_name": name,
        "char": char,
    }
