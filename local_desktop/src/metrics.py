from __future__ import annotations

from datetime import date, timedelta


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def add_days(value: str, count: int) -> str:
    return (parse_date(value) + timedelta(days=count)).isoformat()


def task_end_date(task) -> str:
    return add_days(task.startDate, max(1, int(task.duration)) - 1)


def days_between(start: str, end: str) -> int:
    return (parse_date(end) - parse_date(start)).days


def latest_progress(task, on_date: str | None = None) -> tuple[int, int]:
    entries = sorted(task.progressEntries, key=lambda item: item.entryDate)
    if on_date:
      entries = [entry for entry in entries if entry.entryDate <= on_date]
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
    current = today_value or date.today().isoformat()
    return sum(1 for task in project.tasks if task.status != "Closed" and task_end_date(task) < current)
