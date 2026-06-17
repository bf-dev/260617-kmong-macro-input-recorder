from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Screenshotter(Protocol):
    def capture(self, path: Path) -> None:
        """Capture the current screen to path."""


class MssScreenshotter:
    """Cross-platform full-desktop screenshot writer."""

    def capture(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        import mss
        import mss.tools

        with mss.mss() as sct:
            monitor = sct.monitors[0]
            image = sct.grab(monitor)
            mss.tools.to_png(image.rgb, image.size, output=str(path))
