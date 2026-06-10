from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .metrics import add_days, project_progress, task_end_date
from .models import ArchiveItem, DailyLog, InboxTask, ProgressEntry, Project, Task, Workspace, new_id, to_dict, today, APP_VERSION

LOCAL_KEYS = ("project-desk-local-v5", "project-desk-local-v4", "project-desk-v3")
RISKS = {"H", "M", "L"}
STATUSES = {"Open", "Ongoing", "Closed"}
ARCHIVE_TYPES = {"实验数据", "汇报PPT", "会议纪要", "图片截图", "交付版本", "其他"}
INBOX_STATUSES = {"待处理", "已转任务", "已归档", "已建项目", "已忽略"}


def pick(source: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return default


def clamp_progress(value: Any) -> int:
    try:
        number = round(float(value))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, number))


def clean_date(value: Any, fallback: str | None = None) -> str:
    text = str(value or "")
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text
    return fallback if fallback is not None else today()


def unwrap_payload(raw: Any) -> tuple[dict[str, Any], str]:
    if not isinstance(raw, dict):
        raise ValueError("JSON 顶层必须是对象。")
    for key in LOCAL_KEYS:
        if key in raw:
            value = raw[key]
            return (json.loads(value) if isinstance(value, str) else value), f"localStorage {key}"
    if isinstance(raw.get("payload"), dict):
        return raw["payload"], "Supabase legacy payload"
    if isinstance(raw.get("workspace"), dict):
        return raw["workspace"], "wrapped workspace"
    if isinstance(raw.get("data"), dict):
        return raw["data"], "wrapped data"
    if isinstance(raw.get("projects"), list):
        return raw, "workspace"
    if "tasks" in raw or "dailyLogs" in raw or "daily_logs" in raw:
        return {"projects": [raw]}, "single project"
    raise ValueError("没有识别到 workspace、projects、payload、data 或单项目结构。")


def normalize_workspace(raw: Any) -> tuple[Workspace, list[str]]:
    payload, format_name = unwrap_payload(raw)
    diagnostics = [f"识别格式：{format_name}"]
    projects_raw = payload.get("projects") or []
    if not projects_raw:
        raise ValueError("JSON 中没有项目。")
    projects: list[Project] = []
    for index, item in enumerate(projects_raw, start=1):
        tasks = [_normalize_task(task, payload) for task in item.get("tasks", [])]
        task_ids = {task.id for task in tasks}
        logs: list[DailyLog] = []
        for log_item in pick(item, "dailyLogs", "daily_logs", default=[]):
            if not isinstance(log_item, dict):
                continue
            log = _normalize_log(log_item)
            if log.result == "延期" and not log.delayReason:
                diagnostics.append(f"项目 {index} 有延期日报缺少原因，已标记为待补充。")
            if not task_ids or log.taskId in task_ids:
                logs.append(log)
        archives = [
            _normalize_archive(archive)
            for archive in pick(item, "archives", "archiveItems", "archive_items", default=[])
            if isinstance(archive, dict)
        ]
        project = Project(
            id=str(pick(item, "id", default=new_id())),
            name=str(pick(item, "name", "title", default="未命名项目")),
            deadline=clean_date(pick(item, "deadline")),
            summary=str(pick(item, "summary", default="")),
            topRisk=str(pick(item, "topRisk", "top_risk", default="")),
            nextStep=str(pick(item, "nextStep", "next_step", default="")),
            isPublic=bool(pick(item, "isPublic", "is_public", default=False)),
            publicSlug=str(pick(item, "publicSlug", "public_slug", default="")),
            tasks=tasks,
            dailyLogs=logs,
            archives=archives,
        )
        projects.append(project)
    selected_project_id = str(pick(payload, "selectedProjectId", "selected_project_id", default=projects[0].id))
    if selected_project_id not in {project.id for project in projects}:
        selected_project_id = projects[0].id
    inbox_tasks = [
        _normalize_inbox(item)
        for item in pick(payload, "inboxTasks", "inbox_tasks", "temporaryTasks", "temporary_tasks", default=[])
        if isinstance(item, dict)
    ]
    workspace = Workspace(
        selectedProjectId=selected_project_id,
        selectedDate=clean_date(pick(payload, "selectedDate", "selected_date")),
        projects=projects,
        inboxTasks=inbox_tasks,
        version=str(pick(payload, "version", default=APP_VERSION)),
    )
    diagnostics.append(f"归一化项目 {len(projects)} 个、临时任务 {len(inbox_tasks)} 条。")
    return workspace, diagnostics


def _normalize_task(item: dict[str, Any], payload: dict[str, Any]) -> Task:
    risk = str(pick(item, "risk", default="M"))
    status = str(pick(item, "status", default="Open"))
    entries_raw = pick(item, "progressEntries", "progress_entries", default=[])
    entries = [
        ProgressEntry(
            entryDate=clean_date(pick(entry, "entryDate", "entry_date"), clean_date(pick(payload, "selectedDate", "selected_date"))),
            plannedProgress=clamp_progress(pick(entry, "plannedProgress", "planned_progress")),
            actualProgress=clamp_progress(pick(entry, "actualProgress", "actual_progress")),
        )
        for entry in entries_raw
        if isinstance(entry, dict)
    ]
    if not entries and ("plannedProgress" in item or "actualProgress" in item):
        entries.append(
            ProgressEntry(
                entryDate=clean_date(pick(payload, "selectedDate", "selected_date")),
                plannedProgress=clamp_progress(item.get("plannedProgress")),
                actualProgress=clamp_progress(item.get("actualProgress")),
            )
        )
    return Task(
        id=str(pick(item, "id", default=new_id())),
        parentId=pick(item, "parentId", "parent_id", default=None),
        risk=risk if risk in RISKS else "M",
        title=str(pick(item, "title", "task", "name", default="未命名任务")),
        responsible=str(pick(item, "responsible", "owner", default="")),
        startDate=clean_date(pick(item, "startDate", "start_date")),
        duration=max(1, int(pick(item, "duration", default=1) or 1)),
        status=status if status in STATUSES else "Open",
        completedDate=clean_date(pick(item, "completedDate", "completed_date"), ""),
        note=str(pick(item, "note", "remark", default="")),
        archivePath=str(pick(item, "archivePath", "archive_path", "filePath", "file_path", default="")),
        archiveType=str(pick(item, "archiveType", "archive_type", default="实验数据")),
        archiveKeywords=str(pick(item, "archiveKeywords", "archive_keywords", "keywords", default="")),
        progressEntries=entries,
    )


def _normalize_log(item: dict[str, Any]) -> DailyLog:
    return DailyLog(
        id=str(pick(item, "id", default=new_id())),
        date=clean_date(pick(item, "date", "log_date", "entry_date")),
        responsible=str(pick(item, "responsible", "owner", default="")),
        taskId=str(pick(item, "taskId", "task_id", default="")),
        planText=str(pick(item, "planText", "plan_text", default="")),
        actualText=str(pick(item, "actualText", "actual_text", default="")),
        plannedProgress=clamp_progress(pick(item, "plannedProgress", "planned_progress")),
        actualProgress=clamp_progress(pick(item, "actualProgress", "actual_progress", "progressAfter")),
        result=str(pick(item, "result", default="部分完成")),
        delayReason=str(pick(item, "delayReason", "delay_reason", default="")),
    )


def _normalize_archive(item: dict[str, Any]) -> ArchiveItem:
    item_type = str(pick(item, "type", "archiveType", "archive_type", default="其他"))
    return ArchiveItem(
        id=str(pick(item, "id", default=new_id())),
        date=clean_date(pick(item, "date", "archiveDate", "archive_date")),
        type=item_type if item_type in ARCHIVE_TYPES else "其他",
        title=str(pick(item, "title", "name", default="未命名档案")),
        owner=str(pick(item, "owner", "responsible", default="")),
        keywords=str(pick(item, "keywords", "tags", default="")),
        summary=str(pick(item, "summary", "note", default="")),
        path=str(pick(item, "path", "filePath", "file_path", default="")),
        relatedTaskId=str(pick(item, "relatedTaskId", "related_task_id", default="")),
        status=str(pick(item, "status", default="已归档")),
    )


def _normalize_inbox(item: dict[str, Any]) -> InboxTask:
    status = str(pick(item, "status", default="待处理"))
    return InboxTask(
        id=str(pick(item, "id", default=new_id())),
        createdDate=clean_date(pick(item, "createdDate", "created_date", "date")),
        title=str(pick(item, "title", "name", default="")),
        description=str(pick(item, "description", "note", "summary", default="")),
        source=str(pick(item, "source", default="")),
        status=status if status in INBOX_STATUSES else "待处理",
        suggestedAction=str(pick(item, "suggestedAction", "suggested_action", default="")),
        suggestedProjectId=str(pick(item, "suggestedProjectId", "suggested_project_id", default="")),
        suggestionReason=str(pick(item, "suggestionReason", "suggestion_reason", default="")),
        confirmed=bool(pick(item, "confirmed", default=False)),
    )


def load_workspace_json(path: Path) -> tuple[Workspace, list[str]]:
    return normalize_workspace(json.loads(path.read_text(encoding="utf-8-sig")))


def dump_workspace_json(workspace: Workspace, path: Path) -> None:
    payload = {"version": APP_VERSION, "workspace": to_dict(workspace)}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_tasks_csv(project: Project, path: Path) -> None:
    rows = [["风险", "任务", "负责人", "开始", "工期", "结束", "状态", "计划%", "实际%", "实际完成日", "备注"]]
    for task in project.tasks:
        planned, actual = _latest(task)
        rows.append([task.risk, task.title, task.responsible, task.startDate, task.duration, task_end_date(task), task.status, planned, actual, task.completedDate, task.note])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerows(rows)


def export_project_excel(project: Project, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "项目管理表"
    header_fill = PatternFill("solid", fgColor="E5E7EB")
    blue_fill = PatternFill("solid", fgColor="BFDBFE")
    green_fill = PatternFill("solid", fgColor="86EFAC")
    thin = Side(style="thin", color="9CA3AF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def style_row(row: int) -> None:
        for cell in ws[row]:
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    planned, actual = project_progress(project)
    ws.append([project.name, "", "", ""])
    ws["A1"].font = Font(size=18, bold=True)
    ws.append(["Deadline", project.deadline, "计划进度", f"{planned}%"])
    ws.append(["一句话总结", project.summary, "实际进度", f"{actual}%"])
    ws.append(["TOP 风险", project.topRisk, "下一步计划", project.nextStep])
    for row in range(2, 5):
        style_row(row)

    ws.append([])
    task_header_row = ws.max_row + 1
    ws.append(["风险", "任务", "负责人", "开始", "工期", "结束", "状态", "计划%", "实际%", "实际完成日", "备注"])
    for cell in ws[task_header_row]:
        cell.fill = header_fill
        cell.font = Font(bold=True)
    style_row(task_header_row)
    for task in project.tasks:
        p, a = _latest(task)
        ws.append([task.risk, task.title, task.responsible, task.startDate, task.duration, task_end_date(task), task.status, p, a, task.completedDate, task.note])
        style_row(ws.max_row)

    ws.append([])
    log_header_row = ws.max_row + 1
    ws.append(["日期", "负责人", "关联任务", "计划完成", "实际完成", "计划%", "实际%", "结果", "延期原因"])
    for cell in ws[log_header_row]:
        cell.fill = header_fill
        cell.font = Font(bold=True)
    style_row(log_header_row)
    task_names = {task.id: task.title for task in project.tasks}
    for log in project.dailyLogs:
        ws.append([log.date, log.responsible, task_names.get(log.taskId, ""), log.planText, log.actualText, log.plannedProgress, log.actualProgress, log.result, log.delayReason])
        style_row(ws.max_row)

    ws.append([])
    archive_header_row = ws.max_row + 1
    ws.append(["档案日期", "类型", "标题", "负责人", "关键词", "摘要", "路径", "状态"])
    for cell in ws[archive_header_row]:
        cell.fill = header_fill
        cell.font = Font(bold=True)
    style_row(archive_header_row)
    for archive in project.archives:
        ws.append([archive.date, archive.type, archive.title, archive.owner, archive.keywords, archive.summary, archive.path, archive.status])
        style_row(ws.max_row)

    ws.append([])
    dates = _gantt_dates(project)
    if is_gantt_truncated(project):
        ws.append(["提示", "甘特图日期跨度超过 120 天，当前导出仅显示前 120 天。"])
        style_row(ws.max_row)
    gantt_header_row = ws.max_row + 1
    ws.append(["任务", "负责人", "风险", "实际%", *[item[5:] for item in dates]])
    for cell in ws[gantt_header_row]:
        cell.fill = header_fill
        cell.font = Font(bold=True)
    style_row(gantt_header_row)
    for task in project.tasks:
        _, actual_progress = _latest(task)
        row = [task.title, task.responsible, task.risk, f"{actual_progress}%"]
        end = task_end_date(task)
        row.extend("■" if task.startDate <= item <= end else "" for item in dates)
        ws.append(row)
        for index, date_value in enumerate(dates, start=5):
            if task.startDate <= date_value <= end:
                ws.cell(ws.max_row, index).fill = green_fill if task.completedDate and date_value <= task.completedDate else blue_fill
        style_row(ws.max_row)

    widths = {1: 22, 2: 34, 3: 16, 4: 14, 5: 16, 6: 36, 7: 44, 8: 14, 9: 14, 10: 14, 11: 32}
    for index, width in widths.items():
        ws.column_dimensions[get_column_letter(index)].width = width
    for index in range(12, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(index)].width = 5
    wb.save(path)


def _latest(task: Task) -> tuple[int, int]:
    if not task.progressEntries:
        return 0, 0
    entry = sorted(task.progressEntries, key=lambda item: item.entryDate)[-1]
    return entry.plannedProgress, entry.actualProgress


def _gantt_dates(project: Project) -> list[str]:
    if not project.tasks:
        return [add_days(today(), index) for index in range(14)]
    start = min(task.startDate for task in project.tasks)
    end = max(task_end_date(task) for task in project.tasks)
    total = min(max((date.fromisoformat(end) - date.fromisoformat(start)).days + 1, 14), 120)
    return [add_days(start, index) for index in range(total)]


def is_gantt_truncated(project: Project) -> bool:
    if not project.tasks:
        return False
    start = min(task.startDate for task in project.tasks)
    end = max(task_end_date(task) for task in project.tasks)
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1 > 120
