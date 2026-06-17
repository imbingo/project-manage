import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.import_export import normalize_workspace
from src.metrics import normalize_date, task_end_date
from src.models import Project, Task, Workspace
from src.operations import delete_daily_log, save_daily_log


def test_daily_overview_date_range_includes_start_date():
    task = Task(title="range", startDate="2026-06-02", duration=8, status="Open")
    selected = normalize_date("6.2", fallback_year=2026)
    start = normalize_date(task.startDate, fallback_year=2026)
    end = task_end_date(task)

    assert selected == "2026-06-02"
    assert start <= selected <= end


def test_delete_completion_daily_log_recalculates_task_status():
    workspace = Workspace(projects=[])
    project = Project(name="p")
    task = Task(title="t", startDate="2026-06-01", duration=3)
    project.tasks = [task]
    workspace.projects = [project]

    partial = save_daily_log(
        workspace,
        project,
        None,
        {
            "taskId": task.id,
            "date": "2026-06-01",
            "responsible": "a",
            "planText": "p",
            "actualText": "a",
            "plannedProgress": 50,
            "actualProgress": 50,
            "result": "部分完成",
            "delayReason": "",
        },
    )
    done = save_daily_log(
        workspace,
        project,
        None,
        {
            "taskId": task.id,
            "date": "2026-06-02",
            "responsible": "a",
            "planText": "p",
            "actualText": "a",
            "plannedProgress": 100,
            "actualProgress": 100,
            "result": "完成",
            "delayReason": "",
        },
    )

    assert partial
    assert task.status == "Closed"
    delete_daily_log(project, done.id)

    assert task.status == "Ongoing"
    assert task.completedDate == ""


def test_import_duration_accepts_float_like_text():
    workspace, _ = normalize_workspace(
        {
            "projects": [
                {
                    "name": "p",
                    "tasks": [
                        {
                            "title": "task",
                            "startDate": "2026-06-01",
                            "duration": "4.0",
                        }
                    ],
                }
            ]
        }
    )

    assert workspace.projects[0].tasks[0].duration == 4
