from __future__ import annotations

import re
from datetime import date, timedelta


def normalize_date(value: str | None, fallback_year: int | None = None) -> str | None:
    """Normalize common date inputs to YYYY-MM-DD.

    Supported examples:
    - 2026-06-02
    - 2026-6-2
    - 20260602
    - 6.2 / 6/2 / 6-2 / 6月2日  -> current/fallback year
    - 0602 -> current/fallback year
    """
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("年", "-").replace("月", "-").replace("日", "")
    text = text.replace("/", "-").replace(".", "-").replace("\\", "-")
    text = re.sub(r"\s+", "", text)
    year = fallback_year or date.today().year

    def build(y: int, m: int, d: int) -> str | None:
        try:
            return date(int(y), int(m), int(d)).isoformat()
        except Exception:
            return None

    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        return build(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    match = re.fullmatch(r"(\d{1,2})-(\d{1,2})", text)
    if match:
        return build(year, int(match.group(1)), int(match.group(2)))

    if re.fullmatch(r"\d{8}", text):
        return build(int(text[:4]), int(text[4:6]), int(text[6:8]))

    if re.fullmatch(r"\d{4}", text):
        return build(year, int(text[:2]), int(text[2:4]))

    return None


def parse_date(value: str) -> date:
    normalized = normalize_date(value)
    if not normalized:
        raise ValueError(f"Invalid date: {value!r}")
    return date.fromisoformat(normalized)


def parse_int(value, default: int = 1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def add_days(value: str, count: int) -> str:
    return (parse_date(value) + timedelta(days=count)).isoformat()


def task_end_date(task) -> str:
    return add_days(task.startDate, max(1, parse_int(task.duration, 1)) - 1)


def days_between(start: str, end: str) -> int:
    return (parse_date(end) - parse_date(start)).days


def latest_progress(task, on_date: str | None = None) -> tuple[int, int]:
    entries = sorted(task.progressEntries, key=lambda item: normalize_date(item.entryDate) or item.entryDate)
    if on_date:
        normalized_on = normalize_date(on_date) or on_date
        entries = [entry for entry in entries if (normalize_date(entry.entryDate) or entry.entryDate) <= normalized_on]
    if not entries:
        return 0, 0
    entry = entries[-1]
    return int(entry.plannedProgress), int(entry.actualProgress)


def average(values: list[int]) -> int:
    return round(sum(values) / len(values)) if values else 0


def project_progress(project) -> tuple[int, int]:
    pairs = [latest_progress(task) for task in project.tasks]
    return average([item[0] for item in pairs]), average([item[1] for item in pairs])


def overdue_count(project, today_value: str | None = None) -> int:
    current = normalize_date(today_value) or date.today().isoformat()
    return sum(1 for task in project.tasks if task.status != "Closed" and task_end_date(task) < current)
