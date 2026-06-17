from __future__ import annotations

import os
import platform
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .recorder import InputRecorder


class RecorderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Macro Input Recorder")
        self.root.geometry("620x360")
        self.root.minsize(560, 330)
        self.recorder = InputRecorder()
        self.output_dir: Path | None = None

        self.status_var = tk.StringVar(value="Ready")
        self.count_var = tk.StringVar(value="Events: 0")
        self.output_var = tk.StringVar(value="Output: not started")

        self._build_ui()
        self._poll_status()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(outer, text="Macro Input Recorder", font=("Segoe UI", 16, "bold"))
        title.pack(anchor=tk.W)

        info = ttk.Label(
            outer,
            text=(
                "Start recording, perform the target clicks/keyboard input, then stop. "
                "Each captured input writes one screenshot and one JSON event locally."
            ),
            wraplength=570,
            justify=tk.LEFT,
        )
        info.pack(anchor=tk.W, pady=(6, 14))

        controls = ttk.Frame(outer)
        controls.pack(anchor=tk.W, fill=tk.X)

        self.start_button = ttk.Button(controls, text="Start recording", command=self.start_recording)
        self.start_button.pack(side=tk.LEFT)
        self.stop_button = ttk.Button(controls, text="Stop recording", command=self.stop_recording, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(8, 0))
        self.open_button = ttk.Button(controls, text="Open output folder", command=self.open_output_folder, state=tk.DISABLED)
        self.open_button.pack(side=tk.LEFT, padx=(8, 0))

        status_box = ttk.LabelFrame(outer, text="Status", padding=12)
        status_box.pack(fill=tk.BOTH, expand=True, pady=(16, 0))

        ttk.Label(status_box, textvariable=self.status_var).pack(anchor=tk.W)
        ttk.Label(status_box, textvariable=self.count_var).pack(anchor=tk.W, pady=(8, 0))
        path_label = ttk.Label(status_box, textvariable=self.output_var, wraplength=540, justify=tk.LEFT)
        path_label.pack(anchor=tk.W, pady=(8, 0))

        note = ttk.Label(
            status_box,
            text="Output format: Desktop\\recording\\<started time>\\output\\events.json + images\\*.png",
            foreground="#555555",
            wraplength=540,
            justify=tk.LEFT,
        )
        note.pack(anchor=tk.W, pady=(14, 0))

    def start_recording(self) -> None:
        try:
            paths = self.recorder.start()
        except Exception as exc:
            messagebox.showerror("Could not start recording", str(exc))
            self.status_var.set(f"Start failed: {exc}")
            return

        self.output_dir = paths.output_dir
        self.status_var.set("Recording... click Stop recording when finished.")
        self.output_var.set(f"Output: {paths.output_dir}")
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.open_button.configure(state=tk.NORMAL)

    def stop_recording(self) -> None:
        snapshot = self.recorder.stop()
        self.status_var.set("Stopped. Recording files are saved.")
        self.count_var.set(f"Events: {snapshot.event_count}")
        if snapshot.output_dir:
            self.output_dir = snapshot.output_dir
            self.output_var.set(f"Output: {snapshot.output_dir}")
        if snapshot.last_error:
            self.status_var.set(f"Stopped with warning: {snapshot.last_error}")
        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        self.open_button.configure(state=tk.NORMAL if self.output_dir else tk.DISABLED)

    def open_output_folder(self) -> None:
        if self.output_dir is None:
            return
        open_folder(self.output_dir)

    def _poll_status(self) -> None:
        snapshot = self.recorder.snapshot()
        self.count_var.set(f"Events: {snapshot.event_count}")
        if snapshot.running:
            self.status_var.set("Recording... click Stop recording when finished.")
        elif snapshot.last_error:
            self.status_var.set(f"Warning: {snapshot.last_error}")
        self.root.after(300, self._poll_status)

    def _on_close(self) -> None:
        snapshot = self.recorder.snapshot()
        if snapshot.running:
            if not messagebox.askyesno("Stop recording?", "Recording is still active. Stop and exit?"):
                return
            self.recorder.stop()
        self.root.destroy()


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]
    elif platform.system() == "Darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def main() -> int:
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    RecorderApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
