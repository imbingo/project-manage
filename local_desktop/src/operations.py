from __future__ import annotations

from uuid import uuid4

from .models import ArchiveItem, DailyLog, InboxTask, ProgressEntry, Project, Task, Workspace, today


def latest_entry(task: Task) -> ProgressEntry:
    if not task.progressEntries:
        return ProgressEntry(entryDate=task.startDate, plannedProgress=0, actualProgress=0)
    return sorted(task.progressEntries, key=lambda item: item.entryDate)[-1]


def upsert_progress(task: Task, entry_date: str, planned: int, actual: int) -> None:
    planned = max(0, min(100, int(planned)))
    actual = max(0, min(100, int(actual)))
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
        archivePath=values.get("archivePath", ""),
        archiveType=values.get("archiveType", "实验数据"),
        archiveKeywords=values.get("archiveKeywords", ""),
    )
    upsert_progress(task, selected_date or task.startDate, int(values.get("plannedProgress", 0)), int(values.get("actualProgress", 0)))
    project.tasks.append(task)
    return task


def update_task(task: Task, selected_date: str, values: dict) -> None:
    for key in ["parentId", "risk", "title", "responsible", "startDate", "duration", "status", "completedDate", "note", "archivePath", "archiveType", "archiveKeywords"]:
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
    existing = next((item for item in project.dailyLogs if item is not log and item.taskId == log.taskId and item.date == log.date), None)
    if existing:
        project.dailyLogs.remove(existing)
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



ARCHIVE_KEYWORDS = {
    "实验数据": ["实验", "数据", "复测", "验证", "raw", "result", "结果"],
    "会议纪要": ["会议", "纪要", "评审", "review", "同步"],
    "汇报PPT": ["ppt", "汇报", "报告", "presentation", "材料"],
    "图片截图": ["图片", "截图", "照片", "image", "png", "jpg"],
    "交付版本": ["交付", "final", "版本", "发布"],
}


def archive_type_from_text(text: str) -> str:
    lowered = text.lower()
    for item_type, keys in ARCHIVE_KEYWORDS.items():
        if any(key.lower() in lowered for key in keys):
            return item_type
    return "其他"


def add_archive(project: Project, values: dict) -> ArchiveItem:
    item = ArchiveItem(
        date=values.get("date") or today(),
        type=values.get("type") or archive_type_from_text(" ".join([values.get("title", ""), values.get("summary", ""), values.get("keywords", "")])) ,
        title=values.get("title") or "未命名档案",
        owner=values.get("owner", ""),
        keywords=values.get("keywords", ""),
        summary=values.get("summary", ""),
        path=values.get("path", ""),
        relatedTaskId=values.get("relatedTaskId", ""),
        status=values.get("status", "已归档"),
    )
    project.archives.append(item)
    return item


def update_archive(item: ArchiveItem, values: dict) -> None:
    for key in ["date", "type", "title", "owner", "keywords", "summary", "path", "relatedTaskId", "status"]:
        if key in values:
            setattr(item, key, values[key])


def delete_archive(project: Project, archive_id: str) -> None:
    project.archives = [item for item in project.archives if item.id != archive_id]


def add_inbox_task(workspace: Workspace, values: dict) -> InboxTask:
    item = InboxTask(
        createdDate=values.get("createdDate") or today(),
        title=values.get("title", "").strip(),
        description=values.get("description", "").strip(),
        source=values.get("source", "手动记录").strip(),
        status=values.get("status", "待处理"),
    )
    workspace.inboxTasks.append(item)
    return item


def update_inbox_task(item: InboxTask, values: dict) -> None:
    for key in ["createdDate", "title", "description", "source", "status", "suggestedAction", "suggestedProjectId", "suggestionReason", "confirmed"]:
        if key in values:
            setattr(item, key, values[key])


def delete_inbox_task(workspace: Workspace, item_id: str) -> None:
    workspace.inboxTasks = [item for item in workspace.inboxTasks if item.id != item_id]


def suggest_inbox_task(workspace: Workspace, item: InboxTask) -> InboxTask:
    text = f"{item.title} {item.description}".lower()
    best_project = None
    best_score = 0
    for project in workspace.projects:
        candidates = [project.name, project.summary, project.topRisk, project.nextStep]
        candidates += [task.title for task in project.tasks]
        candidates += [archive.keywords for archive in project.archives]
        score = 0
        for candidate in candidates:
            for token in str(candidate).lower().replace("_", " ").replace("-", " ").split():
                if len(token) >= 2 and token in text:
                    score += 1
        if project.name.lower() in text:
            score += 5
        if score > best_score:
            best_project = project
            best_score = score
    archive_type = archive_type_from_text(text)
    archive_like = archive_type != "其他"
    if best_project and archive_like:
        item.suggestedAction = "归档到项目"
        item.suggestedProjectId = best_project.id
        item.suggestionReason = f"匹配项目“{best_project.name}”，且内容像{archive_type}。"
    elif best_project:
        item.suggestedAction = "转为项目任务"
        item.suggestedProjectId = best_project.id
        item.suggestionReason = f"内容与项目“{best_project.name}”相关。"
    elif any(key in text for key in ["新项目", "专项", "导入", "npi", "评审", "平台", "工具"]):
        item.suggestedAction = "建议新增项目"
        item.suggestedProjectId = ""
        item.suggestionReason = "未匹配现有项目，但内容像一个独立专项。"
    else:
        item.suggestedAction = "待人工判断"
        item.suggestedProjectId = ""
        item.suggestionReason = "未找到足够明确的项目归属。"
    return item


def accept_inbox_suggestion(workspace: Workspace, item: InboxTask, default_project: Project | None = None):
    suggest_inbox_task(workspace, item)
    target_project = next((project for project in workspace.projects if project.id == item.suggestedProjectId), None) or default_project
    if item.suggestedAction == "归档到项目" and target_project:
        archive = add_archive(target_project, {
            "title": item.title or "临时记录归档",
            "summary": item.description,
            "type": archive_type_from_text(f"{item.title} {item.description}"),
            "keywords": item.source,
        })
        item.status = "已归档"
        item.confirmed = True
        return archive
    if item.suggestedAction == "转为项目任务" and target_project:
        task = add_task(target_project, today(), {
            "title": item.title or "临时任务",
            "note": item.description,
            "risk": "M",
            "status": "Open",
            "duration": 1,
            "plannedProgress": 0,
            "actualProgress": 0,
        })
        item.status = "已转任务"
        item.confirmed = True
        return task
    if item.suggestedAction == "建议新增项目":
        project = add_project(workspace, {
            "name": item.title or "新项目",
            "summary": item.description,
            "topRisk": "",
            "nextStep": "请补充项目任务台账。",
        })
        item.status = "已建项目"
        item.suggestedProjectId = project.id
        item.confirmed = True
        return project
    return None
