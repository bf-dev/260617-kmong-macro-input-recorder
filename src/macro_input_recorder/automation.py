from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

from .workflow import MacroStep, MacroWorkflow, workflow_asset_base

LogFn = Callable[[str], None]


@dataclass
class RunOptions:
    confidence: float = 0.78
    coordinate_fallback: bool = True
    confirm_before_run: bool = True
    step_delay_ms: int = 250
    max_retries: int = 2


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
            raise ValueError("실행할 단계가 없습니다. 먼저 recording.zip을 가져와주세요.")
        import pyautogui

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
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
    tmpl = cv2.cvtColor(np.array(template.convert("RGB")), cv2.COLOR_RGB2GRAY)
    if tmpl.shape[0] > screen.shape[0] or tmpl.shape[1] > screen.shape[1]:
        return None
    result = cv2.matchTemplate(screen, tmpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val >= confidence:
        return int(max_loc[0]), int(max_loc[1])
    return None


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
