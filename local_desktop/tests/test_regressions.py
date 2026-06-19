import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import load_workbook
from PySide6.QtWidgets import QApplication, QDateEdit

from src.app import ArchiveDialog, DailyDialog, InboxTaskDialog, ProjectDialog, TaskDialog
from src.import_export import dump_workspace_json, export_project_excel, export_tasks_csv, load_workspace_json, normalize_workspace
from src.metrics import normalize_date, task_end_date
from src.models import APP_VERSION, DailyLog, ProgressEntry, Project, Task, Workspace
from src.operations import delete_daily_log, save_daily_log, update_task
from src.storage import load_workspace, save_workspace, workspace_path


def app():
    return QApplication.instance() or QApplication([])


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

    save_daily_log(
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

    assert task.status == "Closed"
    delete_daily_log(project, done.id)

    assert task.status == "Ongoing"
    assert task.completedDate == ""


def test_update_task_does_not_write_progress_when_unchanged():
    task = Task(
        title="Task",
        startDate="2026-06-01",
        progressEntries=[
            ProgressEntry(entryDate="2026-06-01", plannedProgress=10, actualProgress=10),
            ProgressEntry(entryDate="2026-06-09", plannedProgress=80, actualProgress=80),
        ],
    )

    update_task(task, "2026-06-02", {"title": "Renamed", "plannedProgress": 80, "actualProgress": 80})

    assert task.title == "Renamed"
    assert [(entry.entryDate, entry.plannedProgress, entry.actualProgress) for entry in task.progressEntries] == [
        ("2026-06-01", 10, 10),
        ("2026-06-09", 80, 80),
    ]


def test_update_task_writes_progress_only_when_progress_changed():
    task = Task(
        title="Task",
        startDate="2026-06-01",
        progressEntries=[ProgressEntry(entryDate="2026-06-01", plannedProgress=10, actualProgress=10)],
    )

    update_task(task, "2026-06-02", {"plannedProgress": 20, "actualProgress": 15})

    assert [(entry.entryDate, entry.plannedProgress, entry.actualProgress) for entry in task.progressEntries] == [
        ("2026-06-01", 10, 10),
        ("2026-06-02", 20, 15),
    ]


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


def test_storage_writes_current_app_version(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    workspace = Workspace(projects=[Project(id="p1", name="Project")], selectedProjectId="p1")

    save_workspace(workspace)

    payload = json.loads(workspace_path().read_text(encoding="utf-8"))
    assert payload["version"] == APP_VERSION
    assert payload["workspace"]["version"] == APP_VERSION
    assert load_workspace().version == APP_VERSION


def test_json_csv_excel_export_round_trip(tmp_path):
    task = Task(
        id="t1",
        title="Task",
        responsible="Owner",
        startDate="2026-06-01",
        duration=4,
        progressEntries=[ProgressEntry(entryDate="2026-06-01", plannedProgress=20, actualProgress=10)],
    )
    project = Project(
        id="p1",
        name="Project",
        deadline="2026-06-30",
        summary="summary",
        topRisk="risk",
        nextStep="next",
        tasks=[task],
        dailyLogs=[DailyLog(taskId="t1", date="2026-06-01", responsible="Owner", planText="Plan", actualText="Actual")],
    )
    workspace = Workspace(selectedProjectId="p1", selectedDate="2026-06-01", projects=[project])

    json_path = tmp_path / "workspace.json"
    csv_path = tmp_path / "tasks.csv"
    xlsx_path = tmp_path / "project.xlsx"
    dump_workspace_json(workspace, json_path)
    loaded, diagnostics = load_workspace_json(json_path)
    export_tasks_csv(project, csv_path)
    export_project_excel(project, xlsx_path)

    assert loaded.projects[0].name == "Project"
    assert diagnostics[0].startswith("识别格式")
    assert "Task" in csv_path.read_text(encoding="utf-8-sig")
    workbook = load_workbook(xlsx_path)
    values = [cell.value for row in workbook.active.iter_rows() for cell in row if cell.value]
    assert "Project" in values
    assert "Task" in values


def test_core_date_fields_use_calendar_widgets():
    app()
    project = Project(
        name="Project",
        deadline="2026-06-30",
        tasks=[Task(id="t1", title="Task", startDate="2026-06-01", completedDate="2026-06-03")],
    )

    project_dialog = ProjectDialog(project)
    task_dialog = TaskDialog(project, project.tasks[0], selected_date="2026-06-02")
    daily_dialog = DailyDialog(project, selected_date="2026-06-02")
    archive_dialog = ArchiveDialog(project)
    inbox_dialog = InboxTaskDialog()

    for widget in [
        project_dialog.deadline,
        task_dialog.start,
        task_dialog.completed,
        daily_dialog.date,
        archive_dialog.date,
        inbox_dialog.created,
    ]:
        assert isinstance(widget, QDateEdit)
        assert widget.calendarPopup()

    assert project_dialog.values()["deadline"] == "2026-06-30"
    assert task_dialog.values()["startDate"] == "2026-06-01"
    assert daily_dialog.values()["date"] == "2026-06-02"
