from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from uuid import uuid4


def new_id() -> str:
    return str(uuid4())


def today() -> str:
    return date.today().isoformat()


@dataclass
class ProgressEntry:
    entryDate: str
    plannedProgress: int = 0
    actualProgress: int = 0


@dataclass
class Task:
    id: str = field(default_factory=new_id)
    parentId: str | None = None
    risk: str = "M"
    title: str = "未命名任务"
    responsible: str = ""
    startDate: str = field(default_factory=today)
    duration: int = 1
    status: str = "Open"
    completedDate: str = ""
    note: str = ""
    progressEntries: list[ProgressEntry] = field(default_factory=list)


@dataclass
class DailyLog:
    id: str = field(default_factory=new_id)
    date: str = field(default_factory=today)
    responsible: str = ""
    taskId: str = ""
    planText: str = ""
    actualText: str = ""
    plannedProgress: int = 0
    actualProgress: int = 0
    result: str = "部分完成"
    delayReason: str = ""


@dataclass
class Project:
    id: str = field(default_factory=new_id)
    name: str = "未命名项目"
    deadline: str = field(default_factory=today)
    summary: str = ""
    topRisk: str = ""
    nextStep: str = ""
    isPublic: bool = False
    publicSlug: str = ""
    tasks: list[Task] = field(default_factory=list)
    dailyLogs: list[DailyLog] = field(default_factory=list)


@dataclass
class Workspace:
    selectedProjectId: str | None = None
    selectedDate: str = field(default_factory=today)
    projects: list[Project] = field(default_factory=list)


def to_dict(value):
    return asdict(value)


def sample_workspace() -> Workspace:
    task = Task(
        risk="M",
        title="建立项目任务台账",
        responsible="负责人",
        duration=3,
        progressEntries=[ProgressEntry(entryDate=today(), plannedProgress=30, actualProgress=20)],
    )
    project = Project(
        name="示例项目",
        summary="用最少字段跟踪项目 deadline、风险、计划和实际进度。",
        topRisk="关键任务延期会影响整体交付。",
        nextStep="补齐任务台账并每天更新日报。",
        tasks=[task],
    )
    project.dailyLogs.append(
        DailyLog(
            taskId=task.id,
            responsible=task.responsible,
            planText="完成任务拆解",
            actualText="完成主要任务录入",
            plannedProgress=30,
            actualProgress=20,
        )
    )
    return Workspace(selectedProjectId=project.id, selectedDate=today(), projects=[project])
