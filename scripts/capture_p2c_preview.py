from __future__ import annotations

import argparse
import time
import tkinter as tk
from pathlib import Path

from PIL import ImageGrab

from macro_input_recorder.p2c_app import P2CApp


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    root = tk.Tk()
    root.geometry("760x560+60+60")
    app = P2CApp(root)
    app.workflow_combo.configure(values=["개점", "마감", "가승인"])
    app.selected_workflow.set("가승인")
    root.update_idletasks()
    root.update()
    time.sleep(0.5)
    root.update()

    left = root.winfo_rootx()
    top = root.winfo_rooty()
    right = left + root.winfo_width()
    bottom = top + root.winfo_height()
    ImageGrab.grab(bbox=(left, top, right, bottom)).save(output)
    root.destroy()
    print(f"Saved UI screenshot: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
