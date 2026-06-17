from __future__ import annotations

import platform
import time
from dataclasses import dataclass

POS_TITLE_HINTS = (
    "mom's touch",
    "moms touch",
    "momstouch",
    "mom's",
    "moms",
    "p2c",
    "pos",
    "포스",
    "판매",
    "주문",
    "결제",
)

EXCLUDED_TITLE_HINTS = (
    "p2c 포스 자동화",
    "p2cposmacro",
    "macro input recorder",
    "python",
    "tk",
    "cmd",
    "powershell",
)


@dataclass(frozen=True)
class FocusResult:
    success: bool
    message: str
    title: str = ""


def focus_pos_window(settle_seconds: float = 0.5) -> FocusResult:
    """Bring the POS window to foreground on Windows without Alt+Tab.

    The run buttons live in our Tk window, so the POS must be restored/focused
    before screen matching and coordinate fallback start. This uses Win32 window
    enumeration and title scoring instead of replaying a recorded Alt+Tab.
    """
    if platform.system() != "Windows":
        return FocusResult(False, "Windows가 아니어서 창 포커스 단계를 건너뜁니다.")

    try:
        import ctypes
        from ctypes import wintypes
    except Exception as exc:  # pragma: no cover - Windows-only safety net
        return FocusResult(False, f"Windows 창 제어를 불러오지 못했습니다: {exc}")

    user32 = ctypes.windll.user32
    candidates: list[tuple[int, str, int]] = []

    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_proc(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        score = score_pos_window_title(title)
        if score > 0:
            candidates.append((score, title, hwnd))
        return True

    user32.EnumWindows(enum_proc_type(enum_proc), 0)
    if not candidates:
        return FocusResult(False, "POS로 보이는 창 제목을 찾지 못했습니다.")

    _score, title, hwnd = max(candidates, key=lambda item: (item[0], len(item[1])))
    try:
        SW_RESTORE = 9
        VK_MENU = 0x12
        KEYEVENTF_KEYUP = 0x0002
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        # Windows may reject SetForegroundWindow unless the caller recently sent
        # input. Tapping ALT through keybd_event is the standard foreground-lock
        # workaround and is not an Alt+Tab replay.
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(max(0.0, settle_seconds))
    except Exception as exc:  # pragma: no cover - Windows-only safety net
        return FocusResult(False, f"POS 창 포커스 실패: {exc}", title=title)

    return FocusResult(True, "POS 창을 앞으로 가져왔습니다.", title=title)


def score_pos_window_title(title: str) -> int:
    normalized = " ".join(title.lower().replace("_", " ").split())
    if not normalized:
        return 0
    if any(excluded in normalized for excluded in EXCLUDED_TITLE_HINTS):
        return 0

    score = 0
    for hint in POS_TITLE_HINTS:
        if hint in normalized:
            score += 10
    if "mom" in normalized and "touch" in normalized:
        score += 25
    if "pos" in normalized or "포스" in normalized:
        score += 12
    if "p2c" in normalized:
        score += 12
    return score
