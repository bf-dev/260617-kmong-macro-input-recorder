from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import time
import tkinter as tk
from pathlib import Path

from PIL import ImageGrab

from macro_input_recorder.p2c_app import P2CApp


def _full_window_bbox(root: tk.Tk) -> tuple[int, int, int, int]:
    """Return the outer window rectangle (incl. the native title bar and borders).

    winfo_rootx/rooty only cover the client area, so a preview grabbed from those
    would drop the Windows title bar. Walk up to the real top-level HWND and read
    GetWindowRect so the capture keeps the standard Windows chrome.
    """
    user32 = ctypes.windll.user32
    # Set wide handle types so 64-bit HWNDs are not truncated to 32-bit ints.
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL

    GA_ROOT = 2
    top_hwnd = user32.GetAncestor(wintypes.HWND(root.winfo_id()), GA_ROOT)
    if not top_hwnd:
        top_hwnd = user32.GetForegroundWindow()

    rect = wintypes.RECT()
    if top_hwnd and user32.GetWindowRect(top_hwnd, ctypes.byref(rect)):
        if rect.right > rect.left and rect.bottom > rect.top:
            return rect.left, rect.top, rect.right, rect.bottom

    # Fallback: extend the client area upward to include an estimated title bar.
    left = root.winfo_rootx()
    top = root.winfo_rooty()
    right = left + root.winfo_width()
    bottom = top + root.winfo_height()
    title_bar = 32
    border = 8
    return left - border, top - title_bar, right + border, bottom + border


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    root = tk.Tk()
    root.geometry("780x600+80+80")
    app = P2CApp(root)
    app.workflow_combo.configure(values=["개점", "마감", "가승인"])
    app.selected_workflow.set("가승인")
    # Show the settings tab so the preview reflects the actual control surface.
    app.notebook.select(app.settings_tab)

    root.update_idletasks()
    root.deiconify()
    root.lift()
    root.attributes("-topmost", True)
    root.focus_force()
    root.update()
    time.sleep(0.8)
    root.attributes("-topmost", False)
    root.update()
    time.sleep(0.2)
    root.update()

    bbox = _full_window_bbox(root)
    ImageGrab.grab(bbox=bbox).save(output)
    root.destroy()
    print(f"Saved UI screenshot: {output} bbox={bbox}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
