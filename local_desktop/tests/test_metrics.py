# -*- coding: utf-8 -*-
"""metrics 模块的单元测试。

metrics.py 是纯函数、无界面/IO 依赖，适合直接做单元测试。
运行：在 local_desktop 目录执行 `python -m pytest tests/test_metrics.py`。
"""
from src import metrics
from src.models import Task, Project, ProgressEntry


def test_parse_date_and_days_between():
    assert metrics.parse_date("2026-06-01").isoformat() == "2026-06-01"
    assert metrics.days_between("2026-06-01", "2026-06-10") == 9


def test_add_days():
    assert metrics.add_days("2026-06-01", 5) == "2026-06-06"
    assert metrics.add_days("2026-06-01", 0) == "2026-06-01"


def test_task_end_date_inclusive_duration():
    # 工期 3 天、从 6/1 开始，结束日应为 6/3（含首日）
    task = Task(startDate="2026-06-01", duration=3)
    assert metrics.task_end_date(task) == "2026-06-03"


def test_task_end_date_minimum_one_day():
    # 工期为 0 时按至少 1 天处理，结束日等于开始日
    task = Task(startDate="2026-06-01", duration=0)
    assert metrics.task_end_date(task) == "2026-06-01"


def test_average_rounds_and_handles_empty():
    assert metrics.average([]) == 0
    assert metrics.average([10, 20, 30]) == 20
    assert metrics.average([10, 11]) == 10  # round(10.5) -> 10（银行家舍入）


def test_latest_progress_empty():
    assert metrics.latest_progress(Task()) == (0, 0)


def test_latest_progress_picks_newest_entry():
    task = Task(progressEntries=[
        ProgressEntry("2026-06-01", 30, 20),
        ProgressEntry("2026-06-05", 80, 70),
        ProgressEntry("2026-06-03", 50, 40),
    ])
    assert metrics.latest_progress(task) == (80, 70)


def test_latest_progress_respects_on_date_cutoff():
    task = Task(progressEntries=[
        ProgressEntry("2026-06-01", 30, 20),
        ProgressEntry("2026-06-05", 80, 70),
    ])
    # 截至 6/3，只应看到 6/1 那条进度
    assert metrics.latest_progress(task, on_date="2026-06-03") == (30, 20)


def test_project_progress_averages_tasks():
    project = Project(tasks=[
        Task(progressEntries=[ProgressEntry("2026-06-01", 40, 20)]),
        Task(progressEntries=[ProgressEntry("2026-06-01", 60, 40)]),
    ])
    assert metrics.project_progress(project) == (50, 30)


def test_overdue_count_uses_injected_today():
    project = Project(tasks=[
        Task(startDate="2026-06-01", duration=2, status="Open"),    # 截止 6/2，已过期
        Task(startDate="2026-06-20", duration=2, status="Open"),    # 截止 6/21，未过期
        Task(startDate="2026-06-01", duration=2, status="Closed"),  # 已关闭，不计入
    ])
    assert metrics.overdue_count(project, today_value="2026-06-10") == 1
