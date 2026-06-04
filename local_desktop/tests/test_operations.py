import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models import DailyLog, Project, Task, Workspace
from src.operations import (
    add_project,
    add_task,
    delete_daily_log,
    delete_project,
    delete_task,
    latest_entry,
    merge_workspace,
    save_daily_log,
    update_project,
    update_task,
)


def test_project_crud():
    workspace = Workspace(projects=[Project(name="A")])
    workspace.selectedProjectId = workspace.projects[0].id
    project = add_project(workspace, {"name": "B", "deadline": "2026-06-01", "summary": "s", "topRisk": "r", "nextStep": "n"})
    assert workspace.selectedProjectId == project.id
    update_project(project, {"name": "B2", "summary": "done"})
    assert project.name == "B2"
    assert project.summary == "done"
    delete_project(workspace, project.id)
    assert len(workspace.projects) == 1
    with pytest.raises(ValueError):
        delete_project(workspace, workspace.projects[0].id)


def test_task_crud_and_child_delete_cascade():
    project = Project(name="P")
    parent = add_task(project, "2026-05-06", {"title": "Parent", "startDate": "2026-05-06", "duration": 4, "plannedProgress": 20, "actualProgress": 10})
    child = add_task(project, "2026-05-06", {"title": "Child", "parentId": parent.id, "startDate": "2026-05-07", "duration": 2})
    project.dailyLogs.append(DailyLog(taskId=child.id, date="2026-05-07"))
    update_task(parent, "2026-05-08", {"title": "Parent2", "duration": 5, "plannedProgress": 50, "actualProgress": 30})
    assert parent.title == "Parent2"
    assert parent.duration == 5
    assert latest_entry(parent).entryDate == "2026-05-08"
    deleted_ids = delete_task(project, parent.id)
    assert parent.id in deleted_ids and child.id in deleted_ids
    assert project.tasks == []
    assert project.dailyLogs == []


def test_daily_log_requires_delay_reason_and_updates_task_progress():
    workspace = Workspace(selectedDate="2026-05-06")
    task = Task(id="t1", title="Task", startDate="2026-05-06")
    project = Project(name="P", tasks=[task])
    with pytest.raises(ValueError):
        save_daily_log(workspace, project, None, {"taskId": "t1", "date": "2026-05-06", "result": "延期", "delayReason": ""})
    log = save_daily_log(
        workspace,
        project,
        None,
        {
            "taskId": "t1",
            "date": "2026-05-06",
            "responsible": "A",
            "planText": "Plan",
            "actualText": "Actual",
            "plannedProgress": 100,
            "actualProgress": 100,
            "result": "完成",
            "delayReason": "",
        },
    )
    assert log in project.dailyLogs
    assert task.status == "Closed"
    assert task.completedDate == "2026-05-06"
    assert latest_entry(task).actualProgress == 100
    delete_daily_log(project, log.id)
    assert project.dailyLogs == []
    assert task.progressEntries == []


def test_merge_workspace_remaps_project_task_and_log_ids():
    target_project = Project(id="p1", name="Target")
    target = Workspace(selectedProjectId="p1", selectedDate="2026-05-01", projects=[target_project])
    parent = Task(id="t1", title="Parent")
    child = Task(id="t2", title="Child", parentId="t1")
    incoming_project = Project(id="p1", name="Incoming", tasks=[parent, child], dailyLogs=[DailyLog(id="l1", taskId="t2")])
    incoming = Workspace(selectedProjectId="p1", selectedDate="2026-05-06", projects=[incoming_project])
    merge_workspace(target, incoming)
    assert len(target.projects) == 2
    merged = target.projects[1]
    assert merged.id != "p1"
    assert {task.id for task in merged.tasks}.isdisjoint({"t1", "t2"})
    assert merged.tasks[1].parentId == merged.tasks[0].id
    assert merged.dailyLogs[0].taskId == merged.tasks[1].id
    assert target.selectedProjectId == merged.id
