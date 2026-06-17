from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

from .window_focus import focus_pos_window
from .workflow import MacroStep, MacroWorkflow, workflow_asset_base

LogFn = Callable[[str], None]


@dataclass
class RunOptions:
    confidence: float = 0.78
    coordinate_fallback: bool = True
    confirm_before_run: bool = True
    step_delay_ms: int = 250
    max_retries: int = 2
    focus_pos_before_run: bool = True


class StopRequested(Exception):
    pass


class MacroRunner:
    def __init__(self, log: LogFn | None = None) -> None:
        self._stop = threading.Event()
        self._log = log or (lambda message: None)

    def stop(self) -> None:
        self._stop.set()

    def reset_stop(self) -> None:
        self._stop.clear()

    def run(self, workflow: MacroWorkflow, options: RunOptions | None = None) -> None:
        options = options or RunOptions()
        self.reset_stop()
        if not workflow.steps:
            raise ValueError("실행할 내장 단계가 없습니다. 프로그램을 다시 실행해 주세요.")
        import pyautogui

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        if options.focus_pos_before_run:
            focus_result = focus_pos_window()
            if focus_result.success:
                self._log(f"POS 창 포커스: {focus_result.title}")
            else:
                self._log(f"POS 창 자동 포커스 확인 필요: {focus_result.message}")
                time.sleep(0.4)
        self._log(f"'{workflow.name}' 실행 시작: {len(workflow.steps)}단계")
        for step in workflow.steps:
            self._check_stop()
            self._run_step(step, workflow, options)
            time.sleep(max(0, options.step_delay_ms + step.wait_after_ms) / 1000)
        self._log(f"'{workflow.name}' 실행 완료")

    def _run_step(self, step: MacroStep, workflow: MacroWorkflow, options: RunOptions) -> None:
        import pyautogui

        if step.event_type == "mouse_click":
            x, y, route = self._locate_click(step, workflow, options)
            self._log(f"{step.index}단계 클릭: {x}, {y} ({route})")
            pyautogui.click(x, y, button=(step.button or "left"))
            return
        if step.event_type == "key_press":
            if step.char:
                self._log(f"{step.index}단계 키 입력: {step.char}")
                pyautogui.write(step.char)
            elif step.key:
                key = _normalize_key(step.key)
                self._log(f"{step.index}단계 특수키: {key}")
                pyautogui.press(key)
            return
        self._log(f"{step.index}단계 건너뜀: {step.event_type}")

    def _locate_click(self, step: MacroStep, workflow: MacroWorkflow, options: RunOptions) -> tuple[int, int, str]:
        for attempt in range(options.max_retries + 1):
            self._check_stop()
            found = self._try_template(step, workflow, options.confidence)
            if found:
                return (*found, f"이미지 인식 {attempt + 1}회")
            if attempt < options.max_retries:
                time.sleep(0.35)
        role_point = self._try_visual_role(step)
        if role_point:
            return (*role_point, f"화면 구조 감지 {step.role}")
        if options.coordinate_fallback:
            point = self._fallback_point(step)
            if point:
                return (*point, "좌표 보정 fallback")
        raise RuntimeError(f"{step.index}단계 버튼 이미지를 찾지 못했습니다.")

    def _try_template(self, step: MacroStep, workflow: MacroWorkflow, confidence: float) -> tuple[int, int] | None:
        if not step.anchor or step.anchor_offset_x is None or step.anchor_offset_y is None:
            return None
        anchor_path = workflow_asset_base(workflow) / step.anchor
        if not anchor_path.exists():
            return None
        import pyautogui

        screenshot = pyautogui.screenshot()
        result = _match_template(screenshot, Image.open(anchor_path), confidence)
        if result is None:
            return None
        left, top = result
        return left + step.anchor_offset_x, top + step.anchor_offset_y

    def _try_visual_role(self, step: MacroStep) -> tuple[int, int] | None:
        if not step.role:
            return None
        import pyautogui

        screenshot = pyautogui.screenshot()
        return _find_button_by_role(screenshot, step)

    def _fallback_point(self, step: MacroStep) -> tuple[int, int] | None:
        import pyautogui

        screen_width, screen_height = pyautogui.size()
        if step.x_ratio is not None and step.y_ratio is not None:
            return round(screen_width * step.x_ratio), round(screen_height * step.y_ratio)
        if step.x is not None and step.y is not None:
            if step.screen_width and step.screen_height:
                return round(screen_width * step.x / step.screen_width), round(screen_height * step.y / step.screen_height)
            return step.x, step.y
        return None

    def _check_stop(self) -> None:
        if self._stop.is_set():
            raise StopRequested("사용자가 중지했습니다.")


def _match_template(screenshot: Image.Image, template: Image.Image, confidence: float) -> tuple[int, int] | None:
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    screen = cv2.cvtColor(np.array(screenshot.convert("RGB")), cv2.COLOR_RGB2GRAY)
    base = cv2.cvtColor(np.array(template.convert("RGB")), cv2.COLOR_RGB2GRAY)
    best: tuple[float, tuple[int, int], float] | None = None
    for scale in (1.0, 0.94, 1.06, 0.88, 1.12):
        if scale == 1.0:
            tmpl = base
        else:
            width = max(20, int(base.shape[1] * scale))
            height = max(20, int(base.shape[0] * scale))
            tmpl = cv2.resize(base, (width, height), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        if tmpl.shape[0] > screen.shape[0] or tmpl.shape[1] > screen.shape[1]:
            continue
        result = cv2.matchTemplate(screen, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if best is None or max_val > best[0]:
            best = (float(max_val), (int(max_loc[0]), int(max_loc[1])), scale)
    if best and best[0] >= confidence:
        return best[1]
    return None


def _find_button_by_role(screenshot: Image.Image, step: MacroStep) -> tuple[int, int] | None:
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    arr = np.array(screenshot.convert("RGB"))
    height, width = arr.shape[:2]
    expected = _expected_point(step, width, height)
    modal_bounds = _largest_dark_modal(arr)
    role = step.role
    if role in {"modal_primary", "orange_action"}:
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        mask = ((r > 175) & (g > 105) & (g < 225) & (b < 120)).astype("uint8")
    elif role in {"modal_secondary", "light_button"}:
        gray = arr.mean(axis=2)
        mask = ((gray > 205) & (abs(arr[:, :, 0].astype("int16") - arr[:, :, 1].astype("int16")) < 25)).astype("uint8")
    else:
        return None
    num, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    candidates: list[tuple[float, int, int]] = []
    for idx in range(1, num):
        left, top, comp_width, comp_height, area = [int(v) for v in stats[idx]]
        if comp_width < 25 or comp_height < 14 or area < 120:
            continue
        if comp_width > width * 0.45 or comp_height > height * 0.25:
            continue
        cx, cy = [float(v) for v in centroids[idx]]
        if role.startswith("modal"):
            if not modal_bounds or not _inside_bounds(cx, cy, modal_bounds, padding=8):
                continue
        elif modal_bounds and _inside_bounds(cx, cy, modal_bounds, padding=8):
            continue
        distance = ((cx - expected[0]) ** 2 + (cy - expected[1]) ** 2) ** 0.5
        candidates.append((distance, round(cx), round(cy)))
    if not candidates:
        return None
    distance, x, y = min(candidates, key=lambda item: item[0])
    if distance > max(120, min(width, height) * 0.15):
        return None
    return x, y


def _expected_point(step: MacroStep, width: int, height: int) -> tuple[float, float]:
    if step.x_ratio is not None and step.y_ratio is not None:
        return width * step.x_ratio, height * step.y_ratio
    if step.x is not None and step.y is not None and step.screen_width and step.screen_height:
        return width * step.x / step.screen_width, height * step.y / step.screen_height
    return float(step.x or width // 2), float(step.y or height // 2)


def _largest_dark_modal(arr) -> tuple[int, int, int, int] | None:
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    gray = arr.mean(axis=2)
    mask = (gray < 105).astype("uint8")
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    best: tuple[int, int, int, int, int] | None = None
    height, width = gray.shape[:2]
    for idx in range(1, num):
        left, top, comp_width, comp_height, area = [int(v) for v in stats[idx]]
        if area < width * height * 0.03:
            continue
        if comp_width < 180 or comp_height < 120:
            continue
        if best is None or area > best[4]:
            best = (left, top, left + comp_width, top + comp_height, area)
    if best is None:
        return None
    return best[:4]


def _inside_bounds(x: float, y: float, bounds: tuple[int, int, int, int], padding: int = 0) -> bool:
    left, top, right, bottom = bounds
    return left - padding <= x <= right + padding and top - padding <= y <= bottom + padding


def _normalize_key(key: str) -> str:
    key = key.lower().replace("key.", "")
    mapping = {
        "space": "space",
        "enter": "enter",
        "tab": "tab",
        "esc": "esc",
        "escape": "esc",
        "backspace": "backspace",
        "delete": "delete",
        "shift": "shift",
        "ctrl": "ctrl",
        "control": "ctrl",
        "alt": "alt",
    }
    return mapping.get(key, key)
