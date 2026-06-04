from __future__ import annotations

from uuid import uuid4

from .models import DailyLog, ProgressEntry, Project, Task, Workspace, today


def latest_entry(task: Task) -> ProgressEntry:
    if not task.progressEntries:
        return ProgressEntry(entryDate=task.startDate, plannedProgress=0, actualProgress=0)
    return sorted(task.progressEntries, key=lambda item: item.entryDate)[-1]


def upsert_progress(task: Task, entry_date: str, planned: int, actual: int) -> None:
    for entry in task.progressEntries:
        if entry.entryDate == entry_date:
            entry.plannedProgress = planned
            entry.actualProgress = actual
            return
    task.progressEntries.append(ProgressEntry(entryDate=entry_date, plannedProgress=planned, actualProgress=actual))


def add_project(workspace: Workspace, values: dict) -> Project:
    project = Project(
        name=values.get("name") or "未命名项目",
        deadline=values.get("deadline") or today(),
        summary=values.get("summary", ""),
        topRisk=values.get("topRisk", ""),
        nextStep=values.get("nextStep", ""),
    )
    workspace.projects.append(project)
    workspace.selectedProjectId = project.id
    return project


def update_project(project: Project, values: dict) -> None:
    for key in ["name", "deadline", "summary", "topRisk", "nextStep"]:
        if key in values:
            setattr(project, key, values[key])


def delete_project(workspace: Workspace, project_id: str) -> None:
    if len(workspace.projects) <= 1:
        raise ValueError("至少需要保留一个项目。")
    workspace.projects = [project for project in workspace.projects if project.id != project_id]
    if not any(project.id == workspace.selectedProjectId for project in workspace.projects):
        workspace.selectedProjectId = workspace.projects[0].id


def add_task(project: Project, selected_date: str, values: dict) -> Task:
    task = Task(
        parentId=values.get("parentId"),
        risk=values.get("risk", "M"),
        title=values.get("title") or "未命名任务",
        responsible=values.get("responsible", ""),
        startDate=values.get("startDate") or today(),
        duration=max(1, int(values.get("duration") or 1)),
        status=values.get("status", "Open"),
        completedDate=values.get("completedDate", ""),
        note=values.get("note", ""),
    )
    upsert_progress(task, selected_date or task.startDate, int(values.get("plannedProgress", 0)), int(values.get("actualProgress", 0)))
    project.tasks.append(task)
    return task


def update_task(task: Task, selected_date: str, values: dict) -> None:
    for key in ["parentId", "risk", "title", "responsible", "startDate", "duration", "status", "completedDate", "note"]:
        if key in values:
            setattr(task, key, values[key])
    task.duration = max(1, int(task.duration or 1))
    upsert_progress(task, selected_date or task.startDate, int(values.get("plannedProgress", 0)), int(values.get("actualProgress", 0)))


def delete_task(project: Project, task_id: str) -> set[str]:
    ids = {task_id}
    changed = True
    while changed:
        changed = False
        for task in project.tasks:
            if task.parentId in ids and task.id not in ids:
                ids.add(task.id)
                changed = True
    project.tasks = [task for task in project.tasks if task.id not in ids]
    project.dailyLogs = [log for log in project.dailyLogs if log.taskId not in ids]
    return ids


def save_daily_log(workspace: Workspace, project: Project, log: DailyLog | None, values: dict) -> DailyLog:
    if values.get("result") == "延期" and not values.get("delayReason"):
        raise ValueError("日报结果为延期时，必须填写延期原因。")
    is_new = log is None
    log = log or DailyLog()
    old_task_id = log.taskId
    old_date = log.date
    for key in ["taskId", "date", "responsible", "planText", "actualText", "plannedProgress", "actualProgress", "result", "delayReason"]:
        if key in values:
            setattr(log, key, values[key])
    if is_new:
        project.dailyLogs.append(log)
    old_task = next((task for task in project.tasks if task.id == old_task_id), None)
    if old_task and (old_task_id != log.taskId or old_date != log.date):
        old_task.progressEntries = [entry for entry in old_task.progressEntries if entry.entryDate != old_date]
    task = next((item for item in project.tasks if item.id == log.taskId), None)
    if task:
        upsert_progress(task, log.date, int(log.plannedProgress), int(log.actualProgress))
        task.status = "Closed" if log.actualProgress == 100 else "Ongoing" if log.actualProgress > 0 else "Open"
        task.completedDate = log.date if log.actualProgress == 100 else ""
    workspace.selectedDate = log.date
    return log


def delete_daily_log(project: Project, log_id: str) -> None:
    log = next((item for item in project.dailyLogs if item.id == log_id), None)
    if not log:
        return
    project.dailyLogs = [item for item in project.dailyLogs if item.id != log.id]
    task = next((item for item in project.tasks if item.id == log.taskId), None)
    if task:
        task.progressEntries = [entry for entry in task.progressEntries if entry.entryDate != log.date]


def merge_workspace(target: Workspace, incoming: Workspace) -> None:
    first_new_project_id = None
    for project in incoming.projects:
        old_project_id = project.id
        project.id = str(uuid4())
        first_new_project_id = first_new_project_id or project.id
        task_ids = {}
        for task in project.tasks:
            old_task_id = task.id
            task.id = str(uuid4())
            task_ids[old_task_id] = task.id
        for task in project.tasks:
            if task.parentId:
                task.parentId = task_ids.get(task.parentId)
        for log in project.dailyLogs:
            log.id = str(uuid4())
            log.taskId = task_ids.get(log.taskId, log.taskId)
        if project.publicSlug:
            project.publicSlug = f"{project.publicSlug}-{project.id[:6]}"
        target.projects.append(project)
        if incoming.selectedProjectId == old_project_id:
            first_new_project_id = project.id
    if first_new_project_id:
        target.selectedProjectId = first_new_project_id
    target.selectedDate = incoming.selectedDate or target.selectedDate
