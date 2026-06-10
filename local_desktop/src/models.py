from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from uuid import uuid4


APP_VERSION = "ProjectDeskLocal-V2.3-StabilityPages"


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
    archivePath: str = ""
    archiveType: str = "实验数据"
    archiveKeywords: str = ""
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
class ArchiveItem:
    id: str = field(default_factory=new_id)
    date: str = field(default_factory=today)
    type: str = "实验数据"  # 实验数据 / 汇报PPT / 会议纪要 / 图片截图 / 交付版本 / 其他
    title: str = "未命名档案"
    owner: str = ""
    keywords: str = ""
    summary: str = ""
    path: str = ""
    relatedTaskId: str = ""
    status: str = "已归档"


@dataclass
class InboxTask:
    id: str = field(default_factory=new_id)
    createdDate: str = field(default_factory=today)
    title: str = ""
    description: str = ""
    source: str = ""
    status: str = "待处理"  # 待处理 / 已转任务 / 已归档 / 已建项目 / 已忽略
    suggestedAction: str = ""
    suggestedProjectId: str = ""
    suggestionReason: str = ""
    confirmed: bool = False


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
    archives: list[ArchiveItem] = field(default_factory=list)


@dataclass
class Workspace:
    selectedProjectId: str | None = None
    selectedDate: str = field(default_factory=today)
    projects: list[Project] = field(default_factory=list)
    inboxTasks: list[InboxTask] = field(default_factory=list)
    version: str = APP_VERSION


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
        archives=[
            ArchiveItem(
                type="实验数据",
                title="示例实验数据归档",
                keywords="实验, 数据, 验证",
                summary="这里记录实验目的、结论和原始数据路径，方便后续追溯。",
                path="",
                relatedTaskId=task.id,
            )
        ],
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
    inbox = [
        InboxTask(
            title="整理上周实验截图和复测数据",
            description="先临时记下来，后续可能归档到示例项目的实验数据中。",
            source="手动记录",
        )
    ]
    return Workspace(selectedProjectId=project.id, selectedDate=today(), projects=[project], inboxTasks=inbox)
