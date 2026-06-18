from __future__ import annotations

from datetime import datetime


def parse_hhmm(value: str) -> tuple[int, int]:
    cleaned = value.strip().replace("시", ":").replace("분", "")
    if ":" not in cleaned:
        raise ValueError("시간은 10:30 형식으로 입력해주세요.")
    hour_text, minute_text = cleaned.split(":", 1)
    hour = int(hour_text.strip())
    minute = int(minute_text.strip())
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("시간 범위가 올바르지 않습니다.")
    return hour, minute


def daily_run_key(now: datetime) -> str:
    return now.strftime("%Y-%m-%d")


def is_due_now(now: datetime, hhmm: tuple[int, int], last_run_key: str | None) -> bool:
    return now.hour == hhmm[0] and now.minute == hhmm[1] and last_run_key != daily_run_key(now)
