from __future__ import annotations

import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QEvent, QPoint, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QCalendarWidget,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .import_export import dump_workspace_json, export_project_excel, export_tasks_csv, load_workspace_json
from .metrics import add_days, days_between, overdue_count, project_progress, task_end_date, normalize_date, parse_int
from .models import ArchiveItem, DailyLog, InboxTask, ProgressEntry, Project, Task, Workspace, today, APP_VERSION
from .operations import (
    add_project as add_project_to_workspace,
    add_task as add_task_to_project,
    delete_daily_log as delete_log_from_project,
    delete_project as delete_project_from_workspace,
    delete_task as delete_task_from_project,
    latest_entry,
    merge_workspace,
    save_daily_log,
    update_project,
    update_task,
    add_archive,
    update_archive,
    delete_archive,
    add_inbox_task,
    update_inbox_task,
    delete_inbox_task,
    suggest_inbox_task,
    accept_inbox_suggestion,
    archive_type_from_text,
)
from .storage import data_dir, load_workspace, save_workspace


STATUS_LABELS = {"Open": "未开始", "Ongoing": "进行中", "Closed": "已关闭"}
RISK_COLORS = {"H": "#dc2626", "M": "#d97706", "L": "#0f766e"}
STATUS_COLORS = {"Open": "#64748b", "Ongoing": "#2563eb", "Closed": "#0f766e"}


QSS = """
QMainWindow { background: #eceff3; }
QDialog, QMessageBox { background: #eceff3; }
QWidget { font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", Arial; font-size: 13px; color: #2b333c; }
#centralRoot { background: #eceff3; }
#appBar { background: #ffffff; border-bottom: 1px solid #e7ebef; }
#brandDot { background: #2f6db0; border-radius: 5px; }
#appTitle { color: #1f2933; font-size: 15px; font-weight: 900; }
#verPill {
  color: #2f6db0; background: #eaf1f9; border: 1px solid #d6e5f4;
  border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 900;
}
#appPageLabel { color: #6b7682; font-size: 12px; font-weight: 800; }
#bodyRoot { background: #eceff3; }
QPushButton, QToolButton {
  border: 1px solid #dde2e7; border-radius: 7px; padding: 7px 12px;
  background: #ffffff; color: #46505a; font-weight: 800;
}
QPushButton:hover, QToolButton:hover { border-color: #2f6db0; color: #2f6db0; background: #ffffff; }
QPushButton:disabled, QToolButton:disabled { color: #b6bdc4; border-color: #e9edf1; }
QPushButton#primary { background: #2f6db0; color: white; border-color: #2f6db0; font-weight: 900; }
QPushButton#primary:hover { background: #285f9a; color: white; }
QPushButton#alt { background: #eaf1f9; color: #2f6db0; border-color: #d2e2f3; font-weight: 900; }
QPushButton#alt:hover { background: #dceaf7; color: #2f6db0; }
QPushButton#danger { background: #ffffff; border-color: #ecc9c6; color: #b4453a; font-weight: 900; }
QPushButton#danger:hover { background: #fbf0ef; color: #b4453a; }
QPushButton#winBtn {
  background: transparent; border: none; border-radius: 6px; color: #5b6672;
  font-size: 14px; padding: 0;
}
QPushButton#winBtn:hover { background: #eef2f6; color: #1f2933; }
QPushButton#winClose {
  background: transparent; border: none; border-radius: 6px; color: #5b6672;
  font-size: 13px; padding: 0;
}
QPushButton#winClose:hover { background: #e15b4d; color: #ffffff; }
QComboBox, QDateEdit, QLineEdit, QSpinBox {
  min-height: 28px; padding: 5px 9px; border: 1px solid #d9dee3;
  border-radius: 6px; background: #ffffff; color: #2b333c;
}
QComboBox:disabled, QDateEdit:disabled, QLineEdit:disabled, QSpinBox:disabled {
  color: #b6bdc4; background: #f6f8fa;
}
QComboBox::drop-down, QDateEdit::drop-down, QSpinBox::up-button, QSpinBox::down-button {
  subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none;
}
QComboBox QAbstractItemView {
  background: #ffffff; border: 1px solid #d9dee3; border-radius: 8px;
  padding: 5px; selection-background-color: #eaf1f9; selection-color: #2f6db0;
  outline: 0;
}
QTextEdit { border: 1px solid #d9dee3; border-radius: 8px; background: white; padding: 7px; }
QFrame#sidebar {
  background: #ffffff; border: 1px solid #e7ebef; border-radius: 12px;
}
QFrame#topbar, QFrame#panel, QFrame#card, QFrame#darkCard, QFrame#focusCard, QFrame#detailBox, QFrame#pagePanel {
  background: #ffffff; border: 1px solid #e9edf1; border-radius: 12px;
}
QFrame#darkCard { background: #eaf3fd; border-color: #cbe0f4; }
QFrame#detailBox { background: #f7f9fc; }
QLabel#sectionCaption { color: #5b6672; font-weight: 900; font-size: 11px; letter-spacing: 1px; }
QLabel#pageTitle { color: #1f2933; font-size: 22px; font-weight: 900; }
QLabel#pageDesc { color: #6b7682; }
QLabel#metricTitle { color: #7e8893; font-size: 11px; font-weight: 900; }
QLabel#metricValue { color: #14202c; font-size: 24px; font-weight: 900; }
QLabel#metricValueAccent { color: #2f6db0; font-size: 24px; font-weight: 900; }
QTableWidget {
  background: #ffffff; border: 1px solid #e9edf1; border-radius: 10px; gridline-color: #eef2f6;
  selection-background-color: #eaf1f9; alternate-background-color: #f8fafc;
  font-size: 13px;
}
QHeaderView::section {
  background: #f6f8fa; color: #5b6672; padding: 10px 8px; border: 0;
  font-weight: 900; font-size: 12px;
}
QProgressBar {
  border: 0; border-radius: 5px; background: #e6ebf1; height: 10px; text-align: center;
}
QProgressBar::chunk { border-radius: 5px; background: #2f6db0; }
QTabWidget::pane { border: 1px solid #e7ebef; background: #ffffff; border-radius: 8px; top: -1px; }
QTabBar::tab {
  background: #eef1f4; color: #7a858f; padding: 8px 18px;
  border: 1px solid #e3e7eb; border-bottom: none;
  border-top-left-radius: 7px; border-top-right-radius: 7px; font-weight: 900;
}
QTabBar::tab:selected { background: #ffffff; color: #1f2933; }
QMenu { background: #ffffff; border: 1px solid #d8dee8; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 9px 18px; border-radius: 7px; }
QMenu::item:selected { background: #eaf1f9; color: #2f6db0; }
"""


CALENDAR_QSS = """
QCalendarWidget {
  background: #ffffff;
  border: 1px solid #d8dee8;
  border-radius: 14px;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
  background: #111827;
  border-top-left-radius: 14px;
  border-top-right-radius: 14px;
  min-height: 44px;
}
QCalendarWidget QToolButton {
  background: transparent;
  border: 0;
  border-radius: 8px;
  color: #ffffff;
  font-weight: 900;
  margin: 6px 4px;
  padding: 6px 10px;
}
QCalendarWidget QToolButton:hover { background: #1f2937; }
QCalendarWidget QToolButton::menu-indicator { image: none; width: 0; }
QCalendarWidget QSpinBox {
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  color: #111827;
  min-height: 26px;
  padding: 3px 8px;
  selection-background-color: #0f766e;
}
QCalendarWidget QMenu {
  background: #ffffff;
  border: 1px solid #d8dee8;
  border-radius: 10px;
  padding: 6px;
}
QCalendarWidget QMenu::item {
  border-radius: 7px;
  padding: 7px 14px;
}
QCalendarWidget QMenu::item:selected {
  background: #ecfeff;
  color: #0f766e;
}
QCalendarWidget QAbstractItemView {
  background: #ffffff;
  border: 0;
  border-bottom-left-radius: 14px;
  border-bottom-right-radius: 14px;
  outline: 0;
  padding: 8px;
  selection-background-color: #0f766e;
  selection-color: #ffffff;
}
QCalendarWidget QAbstractItemView:enabled {
  color: #334155;
  font-weight: 700;
}
QCalendarWidget QAbstractItemView:disabled {
  color: #cbd5e1;
}
"""


def task_is_completed(task: Task) -> bool:
    return task.status == "Closed"


def task_sort_key(task: Task) -> tuple:
    risk_order = {"H": 0, "M": 1, "L": 2}
    return (
        task_is_completed(task),
        normalize_ui_date(task.startDate) or task.startDate,
        risk_order.get(task.risk, 9),
        task.title,
    )


def project_is_completed(project: Project) -> bool:
    if project.tasks and all(task_is_completed(task) for task in project.tasks):
        return True
    return project_progress(project)[1] >= 100


def sorted_projects(projects: list[Project]) -> list[Project]:
    return sorted(projects, key=lambda project: (project_is_completed(project), normalize_ui_date(project.deadline) or project.deadline, project.name))


def ordered_tasks(tasks: list[Task]) -> list[tuple[Task, int]]:
    task_map = {task.id: {"task": task, "children": []} for task in tasks}
    roots: list[Task] = []
    for task in tasks:
        if task.parentId and task.parentId in task_map:
            task_map[task.parentId]["children"].append(task)
        else:
            roots.append(task)
    output: list[tuple[Task, int]] = []

    def walk(item: Task, depth: int) -> None:
        output.append((item, depth))
        for child in sorted(task_map[item.id]["children"], key=task_sort_key):
            walk(child, depth + 1)

    for task in sorted(roots, key=task_sort_key):
        walk(task, 0)
    return output


def elide(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"


def normalize_ui_date(value: str, fallback_year: int | None = None) -> str | None:
    return normalize_date(value, fallback_year=fallback_year)


def configure_calendar(calendar: QCalendarWidget) -> QCalendarWidget:
    calendar.setFirstDayOfWeek(Qt.Monday)
    calendar.setGridVisible(False)
    calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
    calendar.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
    calendar.setMinimumSize(336, 292)
    calendar.setStyleSheet(CALENDAR_QSS)

    header_format = calendar.headerTextFormat()
    header_format.setForeground(QColor("#64748b"))
    header_format.setFontWeight(QFont.Bold)
    calendar.setHeaderTextFormat(header_format)

    weekday_format = calendar.weekdayTextFormat(Qt.Monday)
    weekday_format.setForeground(QColor("#334155"))
    weekday_format.setFontWeight(QFont.DemiBold)
    for day in [Qt.Monday, Qt.Tuesday, Qt.Wednesday, Qt.Thursday, Qt.Friday]:
        calendar.setWeekdayTextFormat(day, weekday_format)

    weekend_format = calendar.weekdayTextFormat(Qt.Saturday)
    weekend_format.setForeground(QColor("#be123c"))
    weekend_format.setFontWeight(QFont.DemiBold)
    calendar.setWeekdayTextFormat(Qt.Saturday, weekend_format)
    calendar.setWeekdayTextFormat(Qt.Sunday, weekend_format)

    today_format = calendar.dateTextFormat(QDate.currentDate())
    today_format.setForeground(QColor("#1d4ed8"))
    today_format.setBackground(QColor("#eff6ff"))
    today_format.setFontWeight(QFont.Bold)
    calendar.setDateTextFormat(QDate.currentDate(), today_format)
    return calendar


def make_date_edit(value: str = "") -> QDateEdit:
    normalized = normalize_ui_date(value) or today()
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("yyyy-MM-dd")
    edit.setCalendarWidget(configure_calendar(QCalendarWidget(edit)))
    qdate = QDate.fromString(normalized, "yyyy-MM-dd")
    edit.setDate(qdate if qdate.isValid() else QDate.currentDate())
    return edit


def date_edit_text(edit: QDateEdit) -> str:
    return edit.date().toString("yyyy-MM-dd")


def make_arrow_png(direction: str = "down", color: str = "#8a949e", size: int = 22) -> str | None:
    try:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(color))
        pen.setWidthF(size * 0.11)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        pad = size * 0.30
        center_x = size / 2.0
        if direction == "down":
            a, b, c = QPointF(pad, size * 0.40), QPointF(center_x, size * 0.62), QPointF(size - pad, size * 0.40)
        else:
            a, b, c = QPointF(pad, size * 0.60), QPointF(center_x, size * 0.38), QPointF(size - pad, size * 0.60)
        painter.drawLine(a, b)
        painter.drawLine(b, c)
        painter.end()
        path = Path(tempfile.gettempdir()) / f"project_desk_chevron_{direction}.png"
        pixmap.save(str(path))
        return str(path).replace("\\", "/")
    except Exception:
        return None


def app_stylesheet() -> str:
    down = make_arrow_png("down")
    up = make_arrow_png("up")
    if not down or not up:
        return QSS
    return QSS + (
        "QComboBox::down-arrow, QDateEdit::down-arrow { image: url(%s); width: 11px; height: 11px; margin-right: 5px; }"
        "QSpinBox::up-arrow { image: url(%s); width: 9px; height: 9px; }"
        "QSpinBox::down-arrow { image: url(%s); width: 9px; height: 9px; }"
    ) % (down, up, down)


class ProjectDialog(QDialog):
    def __init__(self, project: Project | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("项目设置" if project else "新增项目")
        self.resize(560, 430)
        self.name = QLineEdit(project.name if project else "")
        self.deadline = make_date_edit(project.deadline if project else today())
        self.summary = QTextEdit(project.summary if project else "")
        self.top_risk = QTextEdit(project.topRisk if project else "")
        self.next_step = QTextEdit(project.nextStep if project else "")
        for text_edit in [self.summary, self.top_risk, self.next_step]:
            text_edit.setFixedHeight(82)

        form = QFormLayout(self)
        form.addRow("项目名称", self.name)
        form.addRow("Deadline", self.deadline)
        form.addRow("一句话总结", self.summary)
        form.addRow("TOP 风险", self.top_risk)
        form.addRow("下一步计划", self.next_step)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def browse_archive_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择归档文件", "", "All Files (*.*)")
        if not path:
            directory = QFileDialog.getExistingDirectory(self, "选择归档目录")
            path = directory or ""
        if path:
            self.archive_path.setText(path)

    def values(self) -> dict:
        return {
            "name": self.name.text().strip() or "未命名项目",
            "deadline": date_edit_text(self.deadline),
            "summary": self.summary.toPlainText().strip(),
            "topRisk": self.top_risk.toPlainText().strip(),
            "nextStep": self.next_step.toPlainText().strip(),
        }


class TaskDialog(QDialog):
    def __init__(self, project: Project, task: Task | None = None, selected_date: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑任务" if task else "新增任务")
        self.resize(560, 560)
        self.parent_task = QComboBox()
        self.parent_task.addItem("无父任务", "")
        for item in project.tasks:
            if not task or item.id != task.id:
                self.parent_task.addItem(item.title, item.id)
        self.risk = QComboBox()
        self.risk.addItems(["H", "M", "L"])
        self.title = QLineEdit(task.title if task else "")
        self.responsible = QLineEdit(task.responsible if task else "")
        self.start = make_date_edit(task.startDate if task else (selected_date or today()))
        self.duration = QSpinBox()
        self.duration.setRange(1, 999)
        self.duration.setValue(max(1, parse_int(task.duration, 3)) if task else 3)
        self.status = QComboBox()
        self.status.addItems(["Open", "Ongoing", "Closed"])
        self.completed = make_date_edit(task.completedDate if task and task.completedDate else (selected_date or today()))
        self.note = QTextEdit(task.note if task else "")
        self.note.setFixedHeight(82)
        self.archive_type = QComboBox()
        self.archive_type.addItems(["实验数据", "汇报PPT", "会议纪要", "图片截图", "交付版本", "其他"])
        self.archive_keywords = QLineEdit(getattr(task, "archiveKeywords", "") if task else "")
        self.archive_path = QLineEdit(getattr(task, "archivePath", "") if task else "")
        browse_archive = QPushButton("选择归档文件/目录")
        browse_archive.clicked.connect(self.browse_archive_path)
        archive_path_row = QHBoxLayout()
        archive_path_row.addWidget(self.archive_path, 1)
        archive_path_row.addWidget(browse_archive)
        if task:
            self.archive_type.setCurrentText(getattr(task, "archiveType", "实验数据") or "实验数据")
        progress = latest_entry(task) if task else ProgressEntry(entryDate=selected_date or today())
        self.planned = QSpinBox()
        self.planned.setRange(0, 100)
        self.planned.setValue(progress.plannedProgress)
        self.actual = QSpinBox()
        self.actual.setRange(0, 100)
        self.actual.setValue(progress.actualProgress)
        if task:
            self.parent_task.setCurrentIndex(max(0, self.parent_task.findData(task.parentId or "")))
            self.risk.setCurrentText(task.risk)
            self.status.setCurrentText(task.status)

        form = QFormLayout(self)
        form.addRow("父任务", self.parent_task)
        form.addRow("风险", self.risk)
        form.addRow("任务名称", self.title)
        form.addRow("负责人", self.responsible)
        form.addRow("开始日期", self.start)
        form.addRow("工期", self.duration)
        form.addRow("状态", self.status)
        form.addRow("计划%", self.planned)
        form.addRow("实际%", self.actual)
        form.addRow("实际完成日", self.completed)
        form.addRow("备注", self.note)
        form.addRow("归档类型", self.archive_type)
        form.addRow("归档关键词", self.archive_keywords)
        form.addRow("归档文件/目录", archive_path_row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def browse_archive_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择归档文件", "", "All Files (*.*)")
        if not path:
            directory = QFileDialog.getExistingDirectory(self, "选择归档目录")
            path = directory or ""
        if path:
            self.archive_path.setText(path)

    def values(self) -> dict:
        return {
            "parentId": self.parent_task.currentData() or None,
            "risk": self.risk.currentText(),
            "title": self.title.text().strip() or "未命名任务",
            "responsible": self.responsible.text().strip(),
            "startDate": date_edit_text(self.start),
            "duration": self.duration.value(),
            "status": self.status.currentText(),
            "completedDate": date_edit_text(self.completed) if self.status.currentText() == "Closed" else "",
            "note": self.note.toPlainText().strip(),
            "archivePath": self.archive_path.text().strip(),
            "archiveType": self.archive_type.currentText(),
            "archiveKeywords": self.archive_keywords.text().strip(),
            "plannedProgress": self.planned.value(),
            "actualProgress": self.actual.value(),
        }


class DailyDialog(QDialog):
    def __init__(self, project: Project, log: DailyLog | None = None, selected_date: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑日报" if log else "新增日报")
        self.resize(580, 520)
        self.task = QComboBox()
        for item in project.tasks:
            self.task.addItem(item.title, item.id)
        self.date = make_date_edit(log.date if log else (selected_date or today()))
        self.responsible = QLineEdit(log.responsible if log else "")
        self.plan_text = QTextEdit(log.planText if log else "")
        self.actual_text = QTextEdit(log.actualText if log else "")
        self.plan_text.setFixedHeight(76)
        self.actual_text.setFixedHeight(76)
        self.planned = QSpinBox()
        self.planned.setRange(0, 100)
        self.planned.setValue(log.plannedProgress if log else 0)
        self.actual = QSpinBox()
        self.actual.setRange(0, 100)
        self.actual.setValue(log.actualProgress if log else 0)
        self.result = QComboBox()
        self.result.addItems(["完成", "部分完成", "延期"])
        self.delay_reason = QTextEdit(log.delayReason if log else "")
        self.delay_reason.setFixedHeight(68)
        if log:
            self.task.setCurrentIndex(max(0, self.task.findData(log.taskId)))
            self.result.setCurrentText(log.result)

        form = QFormLayout(self)
        form.addRow("关联任务", self.task)
        form.addRow("日期", self.date)
        form.addRow("负责人", self.responsible)
        form.addRow("计划完成", self.plan_text)
        form.addRow("实际完成", self.actual_text)
        form.addRow("计划%", self.planned)
        form.addRow("实际%", self.actual)
        form.addRow("结果", self.result)
        form.addRow("延期原因", self.delay_reason)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        return {
            "taskId": self.task.currentData(),
            "date": date_edit_text(self.date),
            "responsible": self.responsible.text().strip(),
            "planText": self.plan_text.toPlainText().strip(),
            "actualText": self.actual_text.toPlainText().strip(),
            "plannedProgress": self.planned.value(),
            "actualProgress": self.actual.value(),
            "result": self.result.currentText(),
            "delayReason": self.delay_reason.toPlainText().strip(),
        }


class ArchiveDialog(QDialog):
    def __init__(self, project: Project, archive: ArchiveItem | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑项目档案" if archive else "新增项目档案")
        self.resize(620, 560)
        self.project = project
        self.date = make_date_edit(archive.date if archive else today())
        self.type = QComboBox()
        self.type.addItems(["实验数据", "汇报PPT", "会议纪要", "图片截图", "交付版本", "其他"])
        self.title = QLineEdit(archive.title if archive else "")
        self.owner = QLineEdit(archive.owner if archive else "")
        self.keywords = QLineEdit(archive.keywords if archive else "")
        self.path = QLineEdit(archive.path if archive else "")
        browse = QPushButton("选择文件/目录")
        browse.clicked.connect(self.browse_path)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path, 1)
        path_row.addWidget(browse)
        self.related_task = QComboBox()
        self.related_task.addItem("无关联任务", "")
        for task in project.tasks:
            self.related_task.addItem(task.title, task.id)
        self.status = QComboBox()
        self.status.addItems(["已归档", "待补充", "已过期"])
        self.summary = QTextEdit(archive.summary if archive else "")
        self.summary.setFixedHeight(110)
        if archive:
            self.type.setCurrentText(archive.type)
            self.status.setCurrentText(archive.status)
            self.related_task.setCurrentIndex(max(0, self.related_task.findData(archive.relatedTaskId)))

        form = QFormLayout(self)
        form.addRow("日期", self.date)
        form.addRow("类型", self.type)
        form.addRow("标题", self.title)
        form.addRow("负责人", self.owner)
        form.addRow("关键词", self.keywords)
        form.addRow("文件/目录路径", path_row)
        form.addRow("关联任务", self.related_task)
        form.addRow("状态", self.status)
        form.addRow("摘要/结论", self.summary)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def browse_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择归档文件", "", "All Files (*.*)")
        if not path:
            directory = QFileDialog.getExistingDirectory(self, "选择归档目录")
            path = directory or ""
        if path:
            self.path.setText(path)

    def values(self) -> dict:
        title = self.title.text().strip()
        summary = self.summary.toPlainText().strip()
        selected_type = self.type.currentText() or archive_type_from_text(f"{title} {summary} {self.keywords.text()}")
        return {
            "date": date_edit_text(self.date),
            "type": selected_type,
            "title": title or "未命名档案",
            "owner": self.owner.text().strip(),
            "keywords": self.keywords.text().strip(),
            "summary": summary,
            "path": self.path.text().strip(),
            "relatedTaskId": self.related_task.currentData() or "",
            "status": self.status.currentText(),
        }


class InboxTaskDialog(QDialog):
    def __init__(self, item: InboxTask | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑待归档任务" if item else "新增待归档任务")
        self.resize(600, 460)
        self.created = make_date_edit(item.createdDate if item else today())
        self.title = QLineEdit(item.title if item else "")
        self.source = QLineEdit(item.source if item else "手动记录")
        self.status = QComboBox()
        self.status.addItems(["待归档", "已转项目任务", "已归档到项目", "已新建项目", "已忽略"])
        self.description = QTextEdit(item.description if item else "")
        self.description.setFixedHeight(160)
        if item:
            self.status.setCurrentText(item.status)
        form = QFormLayout(self)
        form.addRow("记录日期", self.created)
        form.addRow("标题", self.title)
        form.addRow("来源", self.source)
        form.addRow("状态", self.status)
        form.addRow("说明", self.description)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        return {
            "createdDate": date_edit_text(self.created),
            "title": self.title.text().strip() or "未命名待归档任务",
            "source": self.source.text().strip(),
            "status": self.status.currentText(),
            "description": self.description.toPlainText().strip(),
        }


class Sidebar(QFrame):
    def __init__(self, on_navigate=None) -> None:
        super().__init__()
        self.on_navigate = on_navigate
        self.active_name = "总览"
        self.buttons: dict[str, QPushButton] = {}
        self.setObjectName("sidebar")
        self.setFixedWidth(230)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 18, 14, 18)
        layout.setSpacing(8)

        logo_row = QHBoxLayout()
        title_box = QVBoxLayout()
        product = QLabel("Project Desk")
        product.setStyleSheet("color:#1f2933;font-size:18px;font-weight:900;")
        sub = QLabel("Local Workspace")
        sub.setStyleSheet("color:#8a949e;font-size:11px;font-weight:800;")
        title_box.addWidget(product)
        title_box.addWidget(sub)
        logo = QLabel()
        logo.setObjectName("brandDot")
        logo.setFixedSize(10, 10)
        logo_row.addLayout(title_box)
        logo_row.addStretch()
        logo_row.addWidget(logo)
        layout.addLayout(logo_row)
        layout.addSpacing(18)

        for name in ["总览", "任务计划", "项目看板", "待归档任务", "项目档案", "任务表格", "日报记录", "风险看板", "数据中心"]:
            button = QPushButton(self._nav_label(name))
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, value=name: self._handle_click(value))
            self.buttons[name] = button
            layout.addWidget(button)
        self.set_active("总览")

        layout.addStretch()
        health = QFrame()
        health.setStyleSheet("background:#f7f9fc;border:1px solid #e6ebf1;border-radius:12px;")
        health_layout = QVBoxLayout(health)
        health_layout.setContentsMargins(14, 13, 14, 13)
        label = QLabel("项目健康度")
        label.setStyleSheet("color:#7e8893;font-weight:900;font-size:11px;")
        self.health_value = QLabel("良好")
        self.health_value.setStyleSheet("color:#2f6db0;font-size:26px;font-weight:900;")
        self.health_detail = QLabel("暂无异常")
        self.health_detail.setStyleSheet("color:#6b7682;")
        health_layout.addWidget(label)
        health_layout.addWidget(self.health_value)
        health_layout.addWidget(self.health_detail)
        layout.addWidget(health)

    def _nav_label(self, name: str) -> str:
        icon = {
            "总览": "●",
            "任务计划": "▰",
            "待归档任务": "☑",
            "项目看板": "▤",
            "项目档案": "◆",
            "任务表格": "▦",
            "日报记录": "✎",
            "风险看板": "!",
            "数据中心": "⇅",
        }.get(name, "○")
        return f"  {icon}  {name}"

    def _handle_click(self, name: str) -> None:
        self.set_active(name)
        if self.on_navigate:
            self.on_navigate(name)

    def set_active(self, name: str) -> None:
        self.active_name = name
        for key, button in self.buttons.items():
            if key == name:
                button.setStyleSheet(
                    "QPushButton { background:#eaf1f9;color:#2f6db0;border:1px solid #cfe0f1;border-radius:10px;"
                    "padding:11px 11px;text-align:left;font-weight:900; }"
                    "QPushButton:hover { background:#dceaf7;color:#2f6db0; }"
                )
            else:
                button.setStyleSheet(
                    "QPushButton { background:transparent;color:#5b6672;border:1px solid transparent;border-radius:10px;"
                    "padding:11px 11px;text-align:left;font-weight:800; }"
                    "QPushButton:hover { background:#f6f8fa;border-color:#eef1f4;color:#2f6db0; }"
                )

    def update_health(self, overdue: int, lagging: int) -> None:
        if overdue or lagging:
            self.health_value.setText("注意")
            self.health_value.setStyleSheet("color:#b45309;font-size:26px;font-weight:900;")
            parts = []
            if overdue:
                parts.append(f"{overdue}项逾期")
            if lagging:
                parts.append(f"{lagging}项落后")
            self.health_detail.setText(" · ".join(parts))
        else:
            self.health_value.setText("良好")
            self.health_value.setStyleSheet("color:#22c55e;font-size:28px;font-weight:900;")
            self.health_detail.setText("暂无异常")


class TaskPlanWidget(QAbstractScrollArea):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.project: Project | None = None
        self.rows: list[tuple[Task, int]] = []
        self.dates: list[str] = []
        self.selected_date = today()
        self.selected_task_id: str | None = None
        self.on_task_selected = None
        self.on_task_edit = None
        self.on_date_selected = None
        self.min_left_width = 520
        self.max_left_width = 640
        self.min_timeline_width = 340
        self.divider_width = 8
        self.left_width = 540
        self._dragging_divider = False
        self.header_height = 56
        self.row_height = 62
        self.day_width = 64
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.horizontalScrollBar().valueChanged.connect(self.viewport().update)
        self.verticalScrollBar().valueChanged.connect(self.viewport().update)

    def sizeHint(self) -> QSize:
        return QSize(1280, 560)

    def minimumSizeHint(self) -> QSize:
        return QSize(920, 360)

    def set_project(self, project: Project | None, selected_date: str, selected_task_id: str | None = None) -> None:
        self.project = project
        self.rows = ordered_tasks(project.tasks) if project else []
        self.selected_date = selected_date or today()
        self.selected_task_id = selected_task_id
        self.dates = self._date_range()
        self._update_scrollbars()
        self.viewport().update()

    def _date_range(self) -> list[str]:
        if not self.project or not self.project.tasks:
            return [add_days(self.selected_date, index) for index in range(28)]
        starts = [task.startDate for task in self.project.tasks] + [self.selected_date, today()]
        ends = [task_end_date(task) for task in self.project.tasks] + [self.selected_date, today()]
        start = add_days(min(starts), -2)
        end = add_days(max(ends), 8)
        total = min(max(days_between(start, end) + 1, 28), 180)
        return [add_days(start, index) for index in range(total)]

    def _update_scrollbars(self) -> None:
        self._fit_left_width()
        time_width = len(self.dates) * self.day_width
        body_height = len(self.rows) * self.row_height
        visible_time = max(1, self.viewport().width() - self.left_width)
        visible_body = max(1, self.viewport().height() - self.header_height)
        self.horizontalScrollBar().setRange(0, max(0, time_width - visible_time))
        self.horizontalScrollBar().setPageStep(visible_time)
        self.verticalScrollBar().setRange(0, max(0, body_height - visible_body))
        self.verticalScrollBar().setPageStep(visible_body)

    def _fit_left_width(self) -> None:
        viewport_width = max(1, self.viewport().width())
        if viewport_width >= self.min_left_width + self.min_timeline_width:
            max_left = min(self.max_left_width, viewport_width - self.min_timeline_width)
            self.left_width = max(self.min_left_width, min(self.left_width, max_left))
        else:
            self.left_width = max(360, min(self.left_width, viewport_width - 260))

    def _set_left_width(self, width: int) -> None:
        viewport_width = max(1, self.viewport().width())
        lower = 360 if viewport_width < self.min_left_width + self.min_timeline_width else self.min_left_width
        upper = min(self.max_left_width, max(lower, viewport_width - 260))
        self.left_width = max(lower, min(width, upper))
        self._update_scrollbars()
        self.viewport().update()

    def resizeEvent(self, event) -> None:
        self._update_scrollbars()
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.viewport().rect()
        painter.fillRect(rect, QColor("#ffffff"))
        hx = self.horizontalScrollBar().value()
        vy = self.verticalScrollBar().value()

        # Body content is clipped below the header so vertical scrolling can never
        # draw rows, bars, or date markers over the frozen title row.
        painter.save()
        painter.setClipRect(QRectF(0, self.header_height, rect.width(), max(0, rect.height() - self.header_height)))
        self._paint_rows(painter, rect, hx, vy)
        self._paint_date_markers(painter, rect, hx)
        painter.restore()

        # Header is always painted last and is intentionally independent from the
        # vertical scrollbar: risk / task / owner / status / actual and the date
        # scale stay frozen while the task body scrolls.
        self._paint_header(painter, rect, hx)

    def _paint_header(self, painter: QPainter, rect, hx: int) -> None:
        painter.fillRect(QRectF(0, 0, rect.width(), self.header_height), QColor("#f8fafc"))
        painter.setPen(QColor("#475569"))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        headers = [("风险", 14, 48), ("任务名称", 76, 218), ("负责人", 310, 74), ("状态", 400, 68), ("实际", 476, 40)]
        painter.save()
        painter.setClipRect(QRectF(0, 0, self.left_width, self.header_height))
        for label, x, w in headers:
            painter.drawText(QRectF(x, 0, w, self.header_height), Qt.AlignVCenter | Qt.AlignLeft, label)
        painter.restore()

        painter.save()
        painter.setClipRect(QRectF(self.left_width, 0, max(0, rect.width() - self.left_width), self.header_height))
        for index, date_value in enumerate(self.dates):
            x = self.left_width + index * self.day_width - hx
            if x + self.day_width < self.left_width or x > rect.width():
                continue
            if self._is_weekend(date_value):
                painter.fillRect(QRectF(x, 0, self.day_width, self.header_height), QColor("#f8fafc"))
            painter.setPen(QColor("#64748b"))
            painter.drawText(QRectF(x, 7, self.day_width, 20), Qt.AlignCenter, date_value[5:])
            painter.setPen(QColor("#475569"))
            painter.drawText(QRectF(x, 30, self.day_width, 20), Qt.AlignCenter, self._weekday_label(date_value))
            painter.setPen(QColor("#eef2f7"))
            painter.drawLine(int(x), 0, int(x), rect.height())
        painter.restore()
        painter.setPen(QPen(QColor("#e2e8f0"), 2))
        painter.drawLine(self.left_width - 1, 0, self.left_width - 1, rect.height())
        painter.fillRect(QRectF(self.left_width - self.divider_width / 2, 0, self.divider_width, rect.height()), QColor(226, 232, 240, 120))
        painter.setPen(QColor("#e6eaf0"))
        painter.drawLine(0, self.header_height - 1, rect.width(), self.header_height - 1)

    def _paint_rows(self, painter: QPainter, rect, hx: int, vy: int) -> None:
        today_value = today()
        for row, (task, depth) in enumerate(self.rows):
            y = self.header_height + row * self.row_height - vy
            if y + self.row_height < self.header_height or y > rect.height():
                continue
            selected = task.id == self.selected_task_id
            painter.fillRect(QRectF(0, y, rect.width(), self.row_height), QColor("#eff6ff") if selected else QColor("#ffffff" if row % 2 == 0 else "#fcfcfd"))
            painter.setPen(QColor("#eef2f7"))
            painter.drawLine(0, int(y + self.row_height - 1), rect.width(), int(y + self.row_height - 1))
            painter.save()
            painter.setClipRect(QRectF(0, y, self.left_width, self.row_height))
            self._paint_left_task(painter, task, depth, y)
            painter.restore()
            painter.save()
            painter.setClipRect(QRectF(self.left_width, y, max(0, rect.width() - self.left_width), self.row_height))
            for index, date_value in enumerate(self.dates):
                x = self.left_width + index * self.day_width - hx
                if x + self.day_width < self.left_width or x > rect.width():
                    continue
                if date_value == self.selected_date:
                    painter.fillRect(QRectF(x, y, self.day_width, self.row_height), QColor(219, 234, 254, 110))
            self._paint_task_bar(painter, task, y, hx, today_value)
            painter.restore()

    def _paint_left_task(self, painter: QPainter, task: Task, depth: int, y: float) -> None:
        entry = latest_entry(task)
        risk_color = QColor(RISK_COLORS.get(task.risk, "#64748b"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(risk_color.red(), risk_color.green(), risk_color.blue(), 32))
        painter.drawRoundedRect(QRectF(14, y + 17, 34, 28), 14, 14)
        painter.setPen(risk_color)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(14, y + 17, 34, 28), Qt.AlignCenter, task.risk)
        title_x = 76 + depth * 16
        painter.setPen(QColor("#111827"))
        font.setBold(self._has_children(task))
        painter.setFont(font)
        title = elide(task.title, 19 - depth)
        painter.drawText(QRectF(title_x, y + 9, 220 - depth * 16, 24), Qt.AlignVCenter | Qt.AlignLeft, title)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#64748b"))
        painter.drawText(QRectF(title_x, y + 33, 220 - depth * 16, 20), Qt.AlignVCenter | Qt.AlignLeft, f"结束日期 {task_end_date(task)[5:]}")
        painter.setPen(QColor("#334155"))
        painter.drawText(QRectF(310, y, 80, self.row_height), Qt.AlignVCenter | Qt.AlignLeft, elide(task.responsible, 6))
        self._paint_pill(painter, QRectF(400, y + 17, 66, 28), STATUS_LABELS.get(task.status, task.status), STATUS_COLORS.get(task.status, "#64748b"))
        painter.setPen(QColor("#0f766e") if entry.actualProgress > 0 else QColor("#64748b"))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(476, y, 40, self.row_height), Qt.AlignVCenter | Qt.AlignRight, f"{entry.actualProgress}%")
        font.setBold(False)
        painter.setFont(font)

    def _paint_task_bar(self, painter: QPainter, task: Task, y: float, hx: int, today_value: str) -> None:
        if task.startDate not in self.dates:
            return
        start_index = self.dates.index(task.startDate)
        x = self.left_width + start_index * self.day_width - hx + 10
        width = max(16, task.duration * self.day_width - 20)
        if x + width < self.left_width or x > self.viewport().width():
            return
        entry = latest_entry(task)
        overdue = task.status != "Closed" and task_end_date(task) < today_value
        color = QColor("#0f766e")
        if task.status == "Closed":
            color = QColor("#16a34a")
        elif overdue or task.risk == "H":
            color = QColor("#dc2626")
        elif task.risk == "M":
            color = QColor("#d97706")
        bar_y = y + 20
        bar_h = 24
        painter.setPen(QPen(QColor("#dc2626") if overdue or task.risk == "H" else QColor("#cbd5e1"), 2 if overdue or task.risk == "H" else 1))
        painter.setBrush(QColor("#e5e7eb"))
        painter.drawRoundedRect(QRectF(x, bar_y, width, bar_h), 12, 12)
        planned_w = width * entry.plannedProgress / 100
        painter.setPen(QPen(QColor("#94a3b8"), 2, Qt.DashLine))
        painter.drawLine(int(x), int(bar_y + bar_h + 9), int(x + planned_w), int(bar_y + bar_h + 9))
        actual_w = width * entry.actualProgress / 100
        if actual_w > 0:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, bar_y, min(width, max(24, actual_w)), bar_h), 12, 12)
        if width >= 44:
            painter.setPen(QColor("#ffffff") if entry.actualProgress >= 18 else color)
            painter.drawText(QRectF(x, bar_y, width, bar_h), Qt.AlignCenter, f"{entry.actualProgress}%")

    def _paint_pill(self, painter: QPainter, rect: QRectF, text: str, color: str) -> None:
        qcolor = QColor(color)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(qcolor.red(), qcolor.green(), qcolor.blue(), 28))
        painter.drawRoundedRect(rect, 14, 14)
        painter.setPen(qcolor)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, text)
        font.setBold(False)
        painter.setFont(font)

    def _paint_date_markers(self, painter: QPainter, rect, hx: int) -> None:
        # Keep date markers as lines only. Text labels such as “今日” caused
        # collisions with the date scale on narrow windows, so the semantic hint
        # is now represented by a red vertical line plus a small top marker.
        for value, color in [(self.selected_date, "#2563eb"), (today(), "#dc2626")]:
            if value not in self.dates:
                continue
            x = self.left_width + self.dates.index(value) * self.day_width - hx + self.day_width / 2
            if self.left_width <= x <= rect.width():
                painter.setPen(QPen(QColor(color), 2))
                painter.drawLine(int(x), self.header_height, int(x), rect.height())
                if value == today():
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(color))
                    painter.drawPolygon([
                        QPoint(int(x) - 5, self.header_height + 3),
                        QPoint(int(x) + 5, self.header_height + 3),
                        QPoint(int(x), self.header_height + 12),
                    ])

    def _hit_row(self, point: QPoint) -> int | None:
        if point.y() < self.header_height:
            return None
        row = int((point.y() - self.header_height + self.verticalScrollBar().value()) / self.row_height)
        return row if 0 <= row < len(self.rows) else None

    def _hit_date(self, point: QPoint) -> str | None:
        if point.x() < self.left_width:
            return None
        index = int((point.x() - self.left_width + self.horizontalScrollBar().value()) / self.day_width)
        return self.dates[index] if 0 <= index < len(self.dates) else None

    def _near_divider(self, point: QPoint) -> bool:
        return abs(point.x() - self.left_width) <= self.divider_width

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        if self._near_divider(event.pos()):
            self._dragging_divider = True
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return
        if event.pos().x() >= self.left_width:
            date_value = self._hit_date(event.pos())
            if date_value:
                self.selected_date = date_value
                if self.on_date_selected:
                    self.on_date_selected(date_value)
            self.viewport().update()
            return
        row = self._hit_row(event.pos())
        if row is not None:
            task = self.rows[row][0]
            self.selected_task_id = task.id
            if self.on_task_selected:
                self.on_task_selected(task.id)
        self.viewport().update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._dragging_divider:
            self._dragging_divider = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        row = self._hit_row(event.pos())
        if row is not None and self.on_task_edit:
            self.on_task_edit(self.rows[row][0].id)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging_divider:
            self._set_left_width(event.pos().x())
            return
        if self._near_divider(event.pos()):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.setToolTip("拖拽调整任务字段与甘特图宽度")
            return
        self.setCursor(Qt.CursorShape.ArrowCursor)
        row = self._hit_row(event.pos())
        if row is None:
            self.setToolTip("")
            return
        task = self.rows[row][0]
        entry = latest_entry(task)
        self.setToolTip(
            f"{task.title}\n负责人：{task.responsible}\n开始：{task.startDate}\n结束：{task_end_date(task)}\n"
            f"工期：{task.duration} 天\n计划：{entry.plannedProgress}%\n实际：{entry.actualProgress}%\n"
            f"状态：{STATUS_LABELS.get(task.status, task.status)}\n备注：{task.note}"
        )

    def _is_weekend(self, value: str) -> bool:
        return date.fromisoformat(value).weekday() >= 5

    def _weekday_label(self, value: str) -> str:
        return "一二三四五六日"[date.fromisoformat(value).weekday()]

    def _has_children(self, task: Task) -> bool:
        return bool(self.project and any(item.parentId == task.id for item in self.project.tasks))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        QApplication.instance().setFont(QFont("Microsoft YaHei UI", 10))
        self.workspace: Workspace = load_workspace()
        self.selected_task_id: str | None = None
        self.selected_log_id: str | None = None
        self.active_page_name = "任务计划"
        self.setWindowTitle("Project_Manage_LocalV3.3")
        self.resize(1680, 980)
        self.setMinimumSize(1280, 760)
        self._build_ui()
        self.refresh()

    def current_project(self) -> Project | None:
        for project in self.workspace.projects:
            if project.id == self.workspace.selectedProjectId:
                return project
        projects = sorted_projects(self.workspace.projects)
        return projects[0] if projects else None

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("centralRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        appbar = self._build_appbar()
        self._appbar = appbar
        appbar.installEventFilter(self)
        root_layout.addWidget(appbar)

        body = QWidget()
        body.setObjectName("bodyRoot")
        self._body = body
        body.installEventFilter(self)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(12)
        self.sidebar = Sidebar(self.navigate_to)
        body_layout.addWidget(self.sidebar)

        self.page_stack = QStackedWidget()
        self.page_widgets: dict[str, QWidget] = {}
        task_page = self._build_task_plan_page()
        self.page_widgets["任务计划"] = task_page
        self.page_stack.addWidget(task_page)
        body_layout.addWidget(self.page_stack, 1)
        root_layout.addWidget(body, 1)

        self.setCentralWidget(root)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.statusBar().setSizeGripEnabled(True)
        self.sidebar.set_active("任务计划")

    def _build_appbar(self) -> QWidget:
        appbar = QWidget()
        appbar.setObjectName("appBar")
        appbar.setFixedHeight(50)
        layout = QHBoxLayout(appbar)
        layout.setContentsMargins(16, 0, 14, 0)
        layout.setSpacing(9)
        dot = QLabel()
        dot.setObjectName("brandDot")
        dot.setFixedSize(10, 10)
        title = QLabel("Project Desk")
        title.setObjectName("appTitle")
        version = QLabel(APP_VERSION)
        version.setObjectName("verPill")
        self.appbar_page_label = QLabel("任务计划")
        self.appbar_page_label.setObjectName("appPageLabel")
        layout.addWidget(dot)
        layout.addWidget(title)
        layout.addWidget(version)
        layout.addSpacing(8)
        layout.addWidget(self.appbar_page_label)
        layout.addStretch()
        min_button = QPushButton("-")
        max_button = QPushButton("□")
        close_button = QPushButton("x")
        self.btn_win_max = max_button
        for button in [min_button, max_button]:
            button.setObjectName("winBtn")
            button.setFixedSize(36, 28)
            button.setFocusPolicy(Qt.NoFocus)
            layout.addWidget(button)
        close_button.setObjectName("winClose")
        close_button.setFixedSize(36, 28)
        close_button.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(close_button)
        min_button.clicked.connect(self.showMinimized)
        max_button.clicked.connect(self._toggle_max_restore)
        close_button.clicked.connect(self.close)
        return appbar

    def _build_task_plan_page(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self._build_topbar())
        layout.addLayout(self._build_status_cards())
        layout.addLayout(self._build_briefs_and_focus())
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_plan_panel())
        splitter.addWidget(self._build_bottom_area())
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([560, 190])
        layout.addWidget(splitter, 1)
        return content

    def _build_topbar(self) -> QFrame:
        top = QFrame()
        top.setObjectName("topbar")
        top.setMinimumHeight(98)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(22, 14, 22, 14)
        title_box = QVBoxLayout()
        eyebrow = QLabel("Project_Manage_LocalV3.3")
        eyebrow.setStyleSheet("color:#2563eb;font-weight:900;font-size:12px;")
        self.title = QLabel()
        self.title.setStyleSheet("font-size:26px;font-weight:900;")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color:#64748b;")
        title_box.addWidget(eyebrow)
        title_box.addWidget(self.title)
        title_box.addWidget(self.summary)
        top_layout.addLayout(title_box, 1)

        self.project_select = QComboBox()
        self.project_select.setMinimumWidth(210)
        self.project_select.setMaximumWidth(280)
        self.project_select.currentIndexChanged.connect(self._select_project)
        picker_box = QVBoxLayout()
        picker_label = QLabel("当前项目")
        picker_label.setStyleSheet("color:#64748b;font-weight:800;font-size:12px;")
        picker_box.addWidget(picker_label)
        picker_box.addWidget(self.project_select)
        top_layout.addLayout(picker_box)

        add_task = QPushButton("新增任务")
        add_task.setObjectName("primary")
        add_task.clicked.connect(self.add_task)
        add_daily = QPushButton("写日报")
        add_daily.setObjectName("alt")
        add_daily.clicked.connect(self.add_daily)
        top_layout.addWidget(add_task)
        top_layout.addWidget(add_daily)
        top_layout.addWidget(self._menu_button("项目", [("项目设置", self.edit_project), ("新增项目", self.add_project), ("删除项目", self.delete_project)]))
        top_layout.addWidget(self._menu_button("数据", [("导入 JSON", self.import_json), ("导出 JSON", self.export_json), ("导出 CSV", self.export_csv), ("导出 Excel", self.export_excel), ("数据目录", self.open_data_dir)]))
        return top

    def _menu_button(self, label: str, items: list[tuple[str, object]]) -> QToolButton:
        button = QToolButton()
        button.setText(label)
        button.setFixedHeight(30)
        button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(button)
        for text, handler in items:
            action = QAction(text, self)
            action.triggered.connect(handler)
            menu.addAction(action)
        button.setMenu(menu)
        return button

    def _toggle_max_restore(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self.btn_win_max.setText("□")
        else:
            self.showMaximized()
            self.btn_win_max.setText("❐")

    def _resize_edge_at(self, global_pos: QPoint) -> Qt.Edge | None:
        if self.isMaximized():
            return None
        point = self.mapFromGlobal(global_pos)
        rect = self.rect()
        margin = 6
        edges = None
        if point.x() <= margin:
            edges = Qt.Edge.LeftEdge
        elif point.x() >= rect.width() - margin:
            edges = Qt.Edge.RightEdge
        if point.y() <= margin:
            edges = Qt.Edge.TopEdge if edges is None else edges | Qt.Edge.TopEdge
        elif point.y() >= rect.height() - margin:
            edges = Qt.Edge.BottomEdge if edges is None else edges | Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _cursor_for_edges(edges) -> Qt.CursorShape:
        left = bool(edges & Qt.Edge.LeftEdge)
        right = bool(edges & Qt.Edge.RightEdge)
        top = bool(edges & Qt.Edge.TopEdge)
        bottom = bool(edges & Qt.Edge.BottomEdge)
        if (left and top) or (right and bottom):
            return Qt.CursorShape.SizeFDiagCursor
        if (right and top) or (left and bottom):
            return Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        return Qt.CursorShape.SizeVerCursor

    def eventFilter(self, obj, event) -> bool:
        if obj is getattr(self, "_appbar", None):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                window = self.windowHandle()
                if window is not None:
                    window.startSystemMove()
                    return True
            if event.type() == QEvent.Type.MouseButtonDblClick:
                self._toggle_max_restore()
                return True
        elif obj is getattr(self, "_body", None):
            if event.type() == QEvent.Type.MouseMove and not (event.buttons() & Qt.MouseButton.LeftButton):
                edges = self._resize_edge_at(event.globalPosition().toPoint())
                obj.setCursor(self._cursor_for_edges(edges) if edges else Qt.CursorShape.ArrowCursor)
            elif event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                edges = self._resize_edge_at(event.globalPosition().toPoint())
                if edges is not None:
                    window = self.windowHandle()
                    if window is not None:
                        window.startSystemResize(edges)
                        return True
        return super().eventFilter(obj, event)

    def _build_status_cards(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        self.status_card = self._dark_status_card()
        row.addWidget(self.status_card["frame"], 0)
        self.deadline_card = self._card("Deadline")
        self.actual_card = self._card("实际进度")
        self.planned_card = self._card("计划进度")
        self.overdue_card = self._card("逾期任务")
        for card in [self.deadline_card, self.actual_card, self.planned_card, self.overdue_card]:
            row.addWidget(card["frame"], 1)
        return row

    def _dark_status_card(self) -> dict:
        frame = QFrame()
        frame.setObjectName("darkCard")
        frame.setMinimumWidth(190)
        frame.setMinimumHeight(78)
        box = QVBoxLayout(frame)
        box.setContentsMargins(20, 14, 20, 14)
        label = QLabel("项目状态")
        label.setStyleSheet("color:#94a3b8;font-weight:800;")
        value = QLabel("进行中")
        value.setStyleSheet("color:white;font-size:24px;font-weight:900;")
        note = QLabel("风险偏高")
        note.setStyleSheet("color:#fbbf24;font-weight:800;")
        box.addWidget(label)
        box.addWidget(value)
        box.addWidget(note)
        return {"frame": frame, "value": value, "note": note}

    def _card(self, label: str) -> dict:
        frame = QFrame()
        frame.setObjectName("card")
        frame.setMinimumHeight(78)
        self._add_shadow(frame)
        box = QVBoxLayout(frame)
        box.setContentsMargins(16, 10, 16, 10)
        small = QLabel(label)
        small.setStyleSheet("color:#64748b;font-weight:800;")
        value = QLabel("-")
        value.setStyleSheet("font-size:24px;font-weight:900;")
        note = QLabel("")
        note.setStyleSheet("color:#64748b;")
        box.addWidget(small)
        box.addWidget(value)
        box.addWidget(note)
        return {"frame": frame, "value": value, "note": note}

    def _build_briefs_and_focus(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        self.summary_card = self._brief("一句话总结", "#2563eb")
        self.risk_card = self._brief("TOP 风险", "#dc2626")
        self.next_card = self._brief("下一步计划", "#0f766e")
        self.focus_card = self._focus_card()
        for card in [self.summary_card, self.risk_card, self.next_card]:
            row.addWidget(card["frame"], 1)
        row.addWidget(self.focus_card["frame"], 1)
        return row

    def _brief(self, title: str, color: str) -> dict:
        frame = QFrame()
        frame.setObjectName("card")
        frame.setMinimumHeight(78)
        self._add_shadow(frame)
        box = QVBoxLayout(frame)
        box.setContentsMargins(16, 10, 16, 10)
        head = QLabel(title)
        head.setStyleSheet("font-size:14px;font-weight:900;")
        body = QLabel()
        body.setWordWrap(True)
        body.setStyleSheet("color:#334155;line-height:1.5;")
        box.addWidget(head)
        box.addWidget(body)
        frame.setStyleSheet(f"QFrame#card {{ border-left: 4px solid {color}; }}")
        return {"frame": frame, "body": body}

    def _focus_card(self) -> dict:
        frame = QFrame()
        frame.setObjectName("focusCard")
        frame.setMinimumHeight(78)
        self._add_shadow(frame)
        box = QVBoxLayout(frame)
        box.setContentsMargins(16, 10, 16, 10)
        head = QLabel("今日关注")
        head.setStyleSheet("font-size:15px;font-weight:900;")
        labels = []
        box.addWidget(head)
        for _ in range(3):
            label = QLabel("-")
            label.setStyleSheet("color:#334155;")
            labels.append(label)
            box.addWidget(label)
        return {"frame": frame, "items": labels}

    def _build_plan_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panel")
        frame.setMinimumHeight(300)
        self._add_shadow(frame)
        box = QVBoxLayout(frame)
        box.setContentsMargins(18, 14, 18, 16)
        header = QHBoxLayout()
        title = QLabel("任务计划视图")
        title.setStyleSheet("font-size:20px;font-weight:900;")
        subtitle = QLabel("左侧冻结任务字段 + 右侧横向甘特时间轴")
        subtitle.setStyleSheet("color:#64748b;")
        header.addWidget(title)
        header.addWidget(subtitle)
        header.addStretch()
        self.plan_filter_label = QLabel("全部任务")
        self.plan_filter_label.setStyleSheet("background:#f3f4f6;border:1px solid #e5e7eb;border-radius:12px;padding:7px 12px;font-weight:800;color:#334155;")
        header.addWidget(self.plan_filter_label)
        box.addLayout(header)
        self.plan = TaskPlanWidget()
        self.plan.on_task_selected = self.select_task_by_id
        self.plan.on_task_edit = self.edit_task_by_id
        self.plan.on_date_selected = self.select_date
        box.addWidget(self.plan, 1)
        return frame

    def _build_bottom_area(self) -> QWidget:
        self.context_tabs = QTabWidget()
        self.context_tabs.setMinimumHeight(168)
        self.context_tabs.setMaximumHeight(220)

        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(10, 8, 10, 10)
        log_header = QHBoxLayout()
        self.selected_date_label = QLabel()
        self.selected_date_label.setStyleSheet("color:#64748b;font-weight:800;")
        log_header.addWidget(self.selected_date_label, 1)
        for text, handler, obj in [("新增日报", self.add_daily, "alt"), ("编辑日报", self.edit_daily, ""), ("删除日报", self.delete_daily, "")]:
            button = QPushButton(text)
            if obj:
                button.setObjectName(obj)
            button.clicked.connect(handler)
            log_header.addWidget(button)
        log_layout.addLayout(log_header)
        log_layout.addWidget(self._build_log_table(), 1)

        detail_widget = self._build_detail_panel()
        self.context_tabs.addTab(detail_widget, "任务详情")
        self.context_tabs.addTab(log_widget, "选中日期日报")
        return self.context_tabs

    def _panel(self, title: str, widget: QWidget, actions: list[tuple[str, object]] | None = None) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panel")
        self._add_shadow(frame)
        box = QVBoxLayout(frame)
        box.setContentsMargins(16, 12, 16, 14)
        head_row = QHBoxLayout()
        head = QLabel(title)
        head.setStyleSheet("font-size:17px;font-weight:900;")
        head_row.addWidget(head)
        head_row.addStretch()
        for text, handler in actions or []:
            button = QPushButton(text)
            if text == "新增日报":
                button.setObjectName("alt")
            button.clicked.connect(handler)
            head_row.addWidget(button)
        box.addLayout(head_row)
        box.addWidget(widget, 1)
        return frame

    def _build_log_table(self) -> QTableWidget:
        self.log_table = QTableWidget()
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_table.setColumnCount(7)
        self.log_table.setHorizontalHeaderLabels(["负责人", "关联任务", "计划完成", "实际完成", "结果", "延期原因", "日期"])
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.verticalHeader().setDefaultSectionSize(42)
        self.log_table.horizontalHeader().setStretchLastSection(True)
        self.log_table.setColumnWidth(0, 82)
        self.log_table.setColumnWidth(1, 210)
        self.log_table.setColumnWidth(2, 180)
        self.log_table.setColumnWidth(3, 180)
        self.log_table.setColumnWidth(4, 78)
        self.log_table.setColumnHidden(6, True)
        self.log_table.itemDoubleClicked.connect(lambda _item: self.edit_daily())
        return self.log_table

    def _build_detail_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panel")
        self._add_shadow(frame)
        box = QVBoxLayout(frame)
        box.setContentsMargins(18, 16, 18, 16)
        head = QHBoxLayout()
        title = QLabel("任务详情")
        title.setStyleSheet("font-size:17px;font-weight:900;")
        edit = QPushButton("编辑任务")
        edit.clicked.connect(self.edit_task)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(edit)
        box.addLayout(head)
        self.detail_title = QLabel("未选择任务")
        self.detail_title.setWordWrap(True)
        self.detail_title.setStyleSheet("font-size:15px;font-weight:900;")
        self.detail_meta = QLabel("请选择任务计划视图中的一行")
        self.detail_meta.setStyleSheet("color:#64748b;")
        self.detail_progress = QProgressBar()
        self.detail_progress.setRange(0, 100)
        self.detail_progress.setValue(0)
        self.detail_gap = QLabel("")
        self.detail_gap.setStyleSheet("color:#dc2626;font-weight:900;")
        self.detail_note = QLabel("")
        self.detail_note.setWordWrap(True)
        self.detail_note.setStyleSheet("background:#f8fafc;border:1px solid #eef2f7;border-radius:14px;padding:14px;color:#334155;")
        box.addWidget(self.detail_title)
        box.addWidget(self.detail_meta)
        box.addWidget(self.detail_progress)
        box.addWidget(self.detail_gap)
        box.addWidget(self.detail_note, 1)
        return frame

    def _add_shadow(self, widget: QWidget) -> None:
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(18, 28, 40, 34))
        widget.setGraphicsEffect(shadow)

    def _page_shell(self, title: str, desc: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        panel = QFrame()
        panel.setObjectName("pagePanel")
        self._add_shadow(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        caption = QLabel("PROJECT DESK")
        caption.setObjectName("sectionCaption")
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        body = QLabel(desc)
        body.setObjectName("pageDesc")
        body.setWordWrap(True)
        layout.addWidget(caption)
        layout.addWidget(heading)
        layout.addWidget(body)
        outer.addWidget(panel, 1)
        return page, layout

    def _make_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(42)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _fill_table(self, table: QTableWidget, rows: list[list[str]], row_ids: list[object] | None = None) -> None:
        table.setRowCount(len(rows))
        for row_index, row_values in enumerate(rows):
            for col_index, value in enumerate(row_values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if row_ids is not None:
                    item.setData(Qt.UserRole, row_ids[row_index])
                table.setItem(row_index, col_index, item)
            table.setRowHeight(row_index, 42)
        table.resizeColumnsToContents()

    def _switch_to_task_plan(self, project_id: str | None = None, task_id: str | None = None) -> None:
        if project_id:
            self.workspace.selectedProjectId = project_id
        self.selected_task_id = task_id
        save_workspace(self.workspace)
        self.refresh()
        self.navigate_to("任务计划")

    def _show_page(self, name: str, builder) -> None:
        if name != "任务计划":
            old = self.page_widgets.get(name)
            if old is not None:
                self.page_stack.removeWidget(old)
                old.deleteLater()
            page = builder()
            self.page_widgets[name] = page
            self.page_stack.addWidget(page)
        self.active_page_name = name
        self.appbar_page_label.setText(name)
        self.sidebar.set_active(name)
        self.page_stack.setCurrentWidget(self.page_widgets[name])

    def _rebuild_active_page(self) -> None:
        if not hasattr(self, "page_stack") or self.active_page_name == "任务计划":
            return
        builders = self._page_builders()
        builder = builders.get(self.active_page_name)
        if builder:
            self._show_page(self.active_page_name, builder)

    def _page_builders(self) -> dict[str, object]:
        return {
            "总览": self._build_overview_page,
            "项目看板": self._build_project_board_page,
            "待归档任务": self._build_inbox_page,
            "项目档案": self._build_archive_page,
            "任务表格": self._build_task_table_page,
            "日报记录": self._build_daily_log_page,
            "风险看板": self._build_risk_board_page,
            "数据中心": self._build_data_center_page,
        }

    def navigate_to(self, name: str) -> None:
        if name == "任务计划":
            self.active_page_name = name
            self.appbar_page_label.setText(name)
            self.sidebar.set_active(name)
            self.page_stack.setCurrentWidget(self.page_widgets["任务计划"])
            self.plan_filter_label.setText("任务计划")
            self.plan.setFocus()
            return
        builder = self._page_builders().get(name)
        if builder:
            self._show_page(name, builder)

    def _build_overview_page(self) -> QWidget:
        page, layout = self._page_shell(
            "每日任务总览",
            "跨项目查看选中日期需要处理的任务。日期范围覆盖当天、今日截止、已逾期未关闭，或当天已有日报记录的任务都会显示。",
        )
        control_row = QHBoxLayout()
        prev_btn = QPushButton("前一天")
        today_btn = QPushButton("今天")
        next_btn = QPushButton("后一天")
        date_input = make_date_edit(normalize_ui_date(self.workspace.selectedDate) or today())
        date_input.setMaximumWidth(156)
        stats_label = QLabel("")
        stats_label.setStyleSheet("color:#46505a;font-weight:900;")
        control_row.addWidget(QLabel("日期"))
        control_row.addWidget(date_input)
        control_row.addWidget(prev_btn)
        control_row.addWidget(today_btn)
        control_row.addWidget(next_btn)
        control_row.addStretch()
        control_row.addWidget(stats_label)
        layout.addLayout(control_row)

        table = self._make_table(["项目", "关注", "风险", "任务", "负责人", "任务周期", "状态", "计划", "实际", "今日日报", "操作提示"])
        layout.addWidget(table, 1)
        rendered: list[tuple[Project, Task, DailyLog | None, str]] = []

        def safe_parse(value: str, fallback_year: int | None = None) -> date | None:
            normalized = normalize_ui_date(value, fallback_year=fallback_year)
            if not normalized:
                return None
            try:
                return date.fromisoformat(normalized)
            except Exception:
                return None

        def log_for(project: Project, task: Task, value: str) -> DailyLog | None:
            normalized_value = normalize_ui_date(value) or value
            return next((log for log in project.dailyLogs if log.taskId == task.id and (normalize_ui_date(log.date) or log.date) == normalized_value), None)

        def classify(project: Project, task: Task, value: str) -> tuple[list[str], DailyLog | None, int]:
            selected = safe_parse(value)
            fallback_year = selected.year if selected else None
            start = safe_parse(task.startDate, fallback_year=fallback_year)
            try:
                end_text = task_end_date(task)
            except Exception:
                end_text = ""
            end = safe_parse(end_text, fallback_year=fallback_year)
            log = log_for(project, task, value)
            if not selected or not start or not end:
                return (["日期异常"] if log else []), log, 99
            active = start <= selected <= end and task.status != "Closed"
            due_today = end == selected and task.status != "Closed"
            overdue = end < selected and task.status != "Closed"
            has_log = log is not None
            if not (active or due_today or overdue or has_log):
                return [], log, 99
            reasons: list[str] = []
            priority = 50
            if overdue:
                reasons.append("逾期")
                priority = min(priority, 1)
            if task.risk == "H" and task.status != "Closed":
                reasons.append("高风险")
                priority = min(priority, 2)
            if due_today:
                reasons.append("今日截止")
                priority = min(priority, 3)
            if active and not has_log:
                reasons.append("待写日报")
                priority = min(priority, 4)
            if has_log:
                reasons.append("已有日报" if log.result != "延期" else "日报延期")
                priority = min(priority, 5 if log.result != "延期" else 2)
            return reasons or ["今日相关"], log, priority

        def render() -> None:
            selected_date = date_input.date().toString("yyyy-MM-dd")
            self.workspace.selectedDate = selected_date
            rendered.clear()
            collected: list[tuple[int, Project, Task, DailyLog | None, str]] = []
            for project in self.workspace.projects:
                for task in project.tasks:
                    reasons, log, priority = classify(project, task, selected_date)
                    if reasons:
                        collected.append((priority, project, task, log, " / ".join(reasons)))
            collected.sort(key=lambda item: (item[0], item[1].deadline, item[2].risk != "H", task_end_date(item[2]), item[1].name, item[2].title))
            rendered.extend([(project, task, log, reason) for _priority, project, task, log, reason in collected])
            table.setRowCount(len(rendered))
            overdue_num = sum(1 for _p, _t, _l, reason in rendered if "逾期" in reason)
            high_num = sum(1 for _p, task, _l, _r in rendered if task.risk == "H" and task.status != "Closed")
            missing_log = sum(1 for _p, _t, log, reason in rendered if log is None and "待写日报" in reason)
            stats_label.setText(f"今日相关 {len(rendered)} 项 · 逾期 {overdue_num} · 高风险 {high_num} · 待写日报 {missing_log}")
            for row, (project, task, log, reason) in enumerate(rendered):
                entry = latest_entry(task)
                log_text = "未写" if log is None else log.result
                values = [
                    project.name,
                    reason,
                    task.risk,
                    task.title,
                    task.responsible,
                    f"{normalize_ui_date(task.startDate) or task.startDate} ~ {task_end_date(task)}",
                    STATUS_LABELS.get(task.status, task.status),
                    f"{entry.plannedProgress}%",
                    f"{entry.actualProgress}%",
                    log_text,
                    "双击进入任务计划；下方可写日报/编辑任务",
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setToolTip(str(value))
                    if "逾期" in reason:
                        item.setBackground(QColor("#fee2e2"))
                    elif "高风险" in reason:
                        item.setBackground(QColor("#fff7ed"))
                    elif log_text == "未写":
                        item.setBackground(QColor("#eaf1f9"))
                    table.setItem(row, col, item)
                table.setRowHeight(row, 42)
            table.resizeColumnsToContents()
            table.setColumnWidth(0, 180)
            table.setColumnWidth(1, 150)
            table.setColumnWidth(3, 300)
            table.setColumnWidth(10, 280)

        def selected_pair() -> tuple[Project | None, Task | None]:
            row = table.currentRow()
            if row < 0 or row >= len(rendered):
                return None, None
            project, task, _log, _reason = rendered[row]
            return project, task

        def enter_project() -> None:
            project, task = selected_pair()
            if not project or not task:
                QMessageBox.information(page, "请选择任务", "请先选中一条每日任务。")
                return
            self.workspace.selectedDate = date_input.date().toString("yyyy-MM-dd")
            self._switch_to_task_plan(project.id, task.id)

        def write_daily() -> None:
            project, task = selected_pair()
            if not project or not task:
                QMessageBox.information(page, "请选择任务", "请先选中一条每日任务。")
                return
            self.workspace.selectedDate = date_input.date().toString("yyyy-MM-dd")
            self._switch_to_task_plan(project.id, task.id)
            self.add_daily()

        def edit_selected_task() -> None:
            project, task = selected_pair()
            if not project or not task:
                QMessageBox.information(page, "请选择任务", "请先选中一条每日任务。")
                return
            self._switch_to_task_plan(project.id, task.id)
            self.edit_task()

        prev_btn.clicked.connect(lambda _checked=False: date_input.setDate(date_input.date().addDays(-1)))
        today_btn.clicked.connect(lambda _checked=False: date_input.setDate(QDate.currentDate()))
        next_btn.clicked.connect(lambda _checked=False: date_input.setDate(date_input.date().addDays(1)))
        date_input.dateChanged.connect(lambda _date: render())
        table.itemDoubleClicked.connect(lambda _item: enter_project())

        actions = QHBoxLayout()
        for label, handler, obj in [("进入项目任务计划", enter_project, "primary"), ("写日报", write_daily, "alt"), ("编辑任务", edit_selected_task, "")]:
            button = QPushButton(label)
            if obj:
                button.setObjectName(obj)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        render()
        return page

    def _build_project_board_page(self) -> QWidget:
        page, layout = self._page_shell(
            "项目看板",
            "集中查看所有项目的 deadline、计划/实际进度、逾期任务、任务完成情况和档案数量。双击项目即可切换到任务计划。",
        )
        table = self._make_table(["项目", "Deadline", "剩余/逾期", "计划", "实际", "任务数", "已关闭", "逾期", "档案", "一句话总结"])
        rows = []
        ids = []
        for project in sorted_projects(self.workspace.projects):
            planned, actual = project_progress(project)
            closed = sum(1 for task in project.tasks if task.status == "Closed")
            try:
                remain = days_between(today(), project.deadline)
                remain_text = f"剩余 {remain} 天" if remain >= 0 else f"逾期 {abs(remain)} 天"
            except Exception:
                remain_text = "-"
            ids.append(project.id)
            rows.append([project.name, project.deadline, remain_text, f"{planned}%", f"{actual}%", str(len(project.tasks)), str(closed), str(overdue_count(project)), str(len(project.archives)), project.summary])
        self._fill_table(table, rows, ids)
        table.setColumnWidth(0, 220)
        table.setColumnWidth(9, 360)
        for row in range(table.rowCount()):
            if "逾期" in table.item(row, 2).text():
                for col in range(table.columnCount()):
                    table.item(row, col).setBackground(QColor("#fee2e2"))
        layout.addWidget(table, 1)

        def switch_project() -> None:
            row = table.currentRow()
            if row < 0:
                return
            item = table.item(row, 0)
            project_id = item.data(Qt.UserRole) if item else None
            if project_id:
                self._switch_to_task_plan(project_id)

        table.itemDoubleClicked.connect(lambda _item: switch_project())
        row = QHBoxLayout()
        button = QPushButton("切换到项目")
        button.setObjectName("primary")
        button.clicked.connect(switch_project)
        row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        return page

    def _build_task_table_page(self) -> QWidget:
        page, layout = self._page_shell(
            "任务台账",
            "跨项目查看全部任务，适合按项目、负责人、状态、风险快速筛选；双击任务可直接编辑对应项目里的原始任务。",
        )
        filter_row = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("搜索任务 / 负责人 / 备注 / 项目")
        search_input.setClearButtonEnabled(True)
        project_filter = QComboBox()
        project_filter.addItem("全部项目", "")
        status_filter = QComboBox()
        status_filter.addItem("全部状态", "")
        for status, label in STATUS_LABELS.items():
            status_filter.addItem(label, status)
        risk_filter = QComboBox()
        risk_filter.addItem("全部风险", "")
        for risk in ["H", "M", "L"]:
            risk_filter.addItem(risk, risk)
        result_label = QLabel()
        result_label.setStyleSheet("color:#6b7682;font-weight:900;")
        for project in sorted_projects(self.workspace.projects):
            project_filter.addItem(project.name, project.id)
        filter_row.addWidget(search_input, 1)
        filter_row.addWidget(project_filter)
        filter_row.addWidget(status_filter)
        filter_row.addWidget(risk_filter)
        filter_row.addWidget(result_label)
        layout.addLayout(filter_row)

        table = self._make_table(["项目", "风险", "任务", "负责人", "开始", "工期", "结束", "状态", "计划", "实际", "完成日", "备注"])
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(11, QHeaderView.Stretch)
        layout.addWidget(table, 1)
        rendered: list[tuple[Project, Task]] = []

        def render() -> None:
            keyword = search_input.text().strip().lower()
            selected_project_id = project_filter.currentData()
            selected_status = status_filter.currentData()
            selected_risk = risk_filter.currentData()
            rendered.clear()
            total = 0
            for project in sorted_projects(self.workspace.projects):
                if selected_project_id and project.id != selected_project_id:
                    continue
                for task, depth in ordered_tasks(project.tasks):
                    total += 1
                    if selected_status and task.status != selected_status:
                        continue
                    if selected_risk and task.risk != selected_risk:
                        continue
                    if keyword:
                        haystack = " ".join([project.name, task.risk, task.title, task.responsible, task.status, task.note]).lower()
                        if keyword not in haystack:
                            continue
                    rendered.append((project, task))
            table.setRowCount(len(rendered))
            result_label.setText(f"{len(rendered)} / {total} 项")
            for row, (project, task) in enumerate(rendered):
                entry = latest_entry(task)
                depth = 0
                cursor = task
                while cursor.parentId:
                    parent = next((item for item in project.tasks if item.id == cursor.parentId), None)
                    if not parent:
                        break
                    depth += 1
                    cursor = parent
                values = [
                    project.name,
                    task.risk,
                    "  " * depth + task.title,
                    task.responsible,
                    task.startDate,
                    str(task.duration),
                    task_end_date(task),
                    STATUS_LABELS.get(task.status, task.status),
                    f"{entry.plannedProgress}%",
                    f"{entry.actualProgress}%",
                    task.completedDate,
                    task.note,
                ]
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    cell.setToolTip(str(value))
                    cell.setData(Qt.UserRole, task.id)
                    cell.setData(Qt.UserRole + 1, project.id)
                    table.setItem(row, col, cell)
                table.setRowHeight(row, 42)
            table.resizeColumnsToContents()
            table.setColumnWidth(0, 180)
            table.setColumnWidth(1, 70)
            table.setColumnWidth(2, 320)
            table.setColumnWidth(3, 120)
            table.setColumnWidth(7, 90)
            table.setColumnWidth(8, 80)
            table.setColumnWidth(9, 80)
            table.setColumnWidth(11, 320)

        def selected_pair() -> tuple[Project | None, Task | None]:
            row = table.currentRow()
            if row < 0 or row >= len(rendered):
                return None, None
            return rendered[row]

        def sync_selection() -> tuple[Project | None, Task | None]:
            project, task = selected_pair()
            if project and task:
                self.workspace.selectedProjectId = project.id
                self.selected_task_id = task.id
            return project, task

        def edit_current() -> None:
            project, task = sync_selection()
            if not project or not task:
                QMessageBox.information(page, "请选择任务", "请先选中一条任务。")
                return
            self.edit_task()

        def delete_current() -> None:
            project, task = sync_selection()
            if not project or not task:
                QMessageBox.information(page, "请选择任务", "请先选中一条任务。")
                return
            self.delete_task()

        def enter_plan() -> None:
            project, task = sync_selection()
            if project and task:
                self._switch_to_task_plan(project.id, task.id)

        search_input.textChanged.connect(lambda _text: render())
        project_filter.currentIndexChanged.connect(lambda _index: render())
        status_filter.currentIndexChanged.connect(lambda _index: render())
        risk_filter.currentIndexChanged.connect(lambda _index: render())
        table.itemSelectionChanged.connect(lambda: sync_selection())
        table.itemDoubleClicked.connect(lambda _item: edit_current())
        actions = QHBoxLayout()
        for label, handler, obj in [("新增当前项目任务", self.add_task, "primary"), ("编辑任务", edit_current, ""), ("删除任务", delete_current, "danger"), ("进入任务计划", enter_plan, "alt")]:
            button = QPushButton(label)
            if obj:
                button.setObjectName(obj)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        render()
        return page

    def _build_archive_page(self) -> QWidget:
        page, layout = self._page_shell(
            "项目档案",
            "按项目集中展示实验数据、汇报PPT、会议纪要、图片截图和交付版本；支持跨项目关键词搜索。",
        )
        search_row = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("搜索档案：项目 / 标题 / 关键词 / 摘要 / 负责人 / 类型 / 路径 / 关联任务")
        search_input.setClearButtonEnabled(True)
        project_filter = QComboBox()
        project_filter.addItem("全部项目", "")
        for item in self.workspace.projects:
            project_filter.addItem(item.name, item.id)
        type_filter = QComboBox()
        type_filter.addItems(["全部类型", "实验数据", "会议纪要", "汇报PPT", "图片截图", "交付版本", "其他"])
        status_filter = QComboBox()
        status_filter.addItems(["全部状态", "待整理", "已归档", "已完成", "待补充", "已废弃", "已过期"])
        result_label = QLabel()
        result_label.setStyleSheet("color:#6b7682;font-weight:900;")
        search_row.addWidget(search_input, 1)
        search_row.addWidget(project_filter)
        search_row.addWidget(type_filter)
        search_row.addWidget(status_filter)
        search_row.addWidget(result_label)
        layout.addLayout(search_row)

        table = self._make_table(["项目", "日期", "类型", "标题", "负责人", "关键词", "摘要/结论", "路径", "状态", "关联任务"])
        layout.addWidget(table, 1)
        rendered: list[tuple[Project, ArchiveItem]] = []

        def task_name(project: Project, archive: ArchiveItem) -> str:
            return next((task.title for task in project.tasks if task.id == archive.relatedTaskId), "")

        def render() -> None:
            keyword = search_input.text().strip().lower()
            selected_project_id = project_filter.currentData()
            selected_type = type_filter.currentText()
            selected_status = status_filter.currentText()
            rendered.clear()
            total = 0
            for project in self.workspace.projects:
                if selected_project_id and project.id != selected_project_id:
                    continue
                for archive in sorted(project.archives, key=lambda item: item.date, reverse=True):
                    total += 1
                    related_task_name = task_name(project, archive)
                    if selected_type != "全部类型" and archive.type != selected_type:
                        continue
                    if selected_status != "全部状态" and archive.status != selected_status:
                        continue
                    if keyword:
                        haystack = " ".join([project.name, archive.date, archive.type, archive.title, archive.owner, archive.keywords, archive.summary, archive.path, archive.status, related_task_name]).lower()
                        if keyword not in haystack:
                            continue
                    rendered.append((project, archive))
            table.setRowCount(len(rendered))
            result_label.setText(f"{len(rendered)} / {total} 条")
            for row, (project, archive) in enumerate(rendered):
                values = [project.name, archive.date, archive.type, archive.title, archive.owner, archive.keywords, archive.summary, archive.path, archive.status, task_name(project, archive)]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setToolTip(str(value))
                    item.setData(Qt.UserRole, archive.id)
                    item.setData(Qt.UserRole + 1, project.id)
                    table.setItem(row, col, item)
                table.setRowHeight(row, 42)
            table.resizeColumnsToContents()
            table.setColumnWidth(0, 180)
            table.setColumnWidth(3, 240)
            table.setColumnWidth(6, 260)
            table.setColumnWidth(7, 260)

        def selected_archive_pair() -> tuple[Project, ArchiveItem] | tuple[None, None]:
            row = table.currentRow()
            if row < 0 or row >= len(rendered):
                return None, None
            return rendered[row]

        def add_item() -> None:
            project = self.current_project() or (self.workspace.projects[0] if self.workspace.projects else None)
            if not project:
                return
            dialog = ArchiveDialog(project, parent=page)
            if dialog.exec() == QDialog.Accepted:
                add_archive(project, dialog.values())
                save_workspace(self.workspace)
                render()
                self.refresh()

        def edit_item() -> None:
            project, archive = selected_archive_pair()
            if not project or not archive:
                QMessageBox.information(page, "请选择档案", "请先选中一条档案记录。")
                return
            dialog = ArchiveDialog(project, archive, page)
            if dialog.exec() == QDialog.Accepted:
                update_archive(archive, dialog.values())
                save_workspace(self.workspace)
                render()
                self.refresh()

        def delete_item() -> None:
            project, archive = selected_archive_pair()
            if not project or not archive:
                QMessageBox.information(page, "请选择档案", "请先选中一条档案记录。")
                return
            if QMessageBox.question(page, "确认删除", f"删除档案“{archive.title}”？") == QMessageBox.Yes:
                delete_archive(project, archive.id)
                save_workspace(self.workspace)
                render()
                self.refresh()

        def open_path() -> None:
            _project, archive = selected_archive_pair()
            if not archive or not archive.path:
                QMessageBox.information(page, "没有路径", "该档案没有填写文件或目录路径。")
                return
            path = Path(archive.path)
            if path.exists():
                subprocess.Popen(["explorer", str(path if path.is_dir() else path.parent)])
            else:
                QMessageBox.warning(page, "路径不存在", str(path))

        search_input.textChanged.connect(lambda _text: render())
        project_filter.currentIndexChanged.connect(lambda _index: render())
        type_filter.currentIndexChanged.connect(lambda _index: render())
        status_filter.currentIndexChanged.connect(lambda _index: render())
        table.itemDoubleClicked.connect(lambda _item: edit_item())
        actions = QHBoxLayout()
        for label, handler, obj in [("新增档案", add_item, "primary"), ("编辑档案", edit_item, ""), ("删除档案", delete_item, "danger"), ("打开路径", open_path, "alt")]:
            button = QPushButton(label)
            if obj:
                button.setObjectName(obj)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        render()
        return page

    def _build_inbox_page(self) -> QWidget:
        page, layout = self._page_shell(
            "待归档任务收集箱",
            "先收集暂时无法归入项目的待办、实验线索、资料和想法；转为任务时必须明确目标项目，避免“当前项目”含义不清。",
        )
        target_row = QHBoxLayout()
        target_project = QComboBox()
        target_project.setMinimumWidth(240)
        for project in sorted_projects(self.workspace.projects):
            target_project.addItem(project.name, project.id)
            if project.id == self.workspace.selectedProjectId:
                target_project.setCurrentIndex(target_project.count() - 1)
        target_hint = QLabel("")
        target_hint.setStyleSheet("color:#6b7682;font-weight:900;")
        target_row.addWidget(QLabel("转任务目标项目"))
        target_row.addWidget(target_project)
        target_row.addWidget(target_hint, 1)
        layout.addLayout(target_row)
        table = self._make_table(["日期", "标题", "说明", "来源", "状态", "建议动作", "建议项目", "建议原因"])
        layout.addWidget(table, 1)
        rendered: list[InboxTask] = []
        to_task_button: QPushButton | None = None

        def selected_target_project() -> Project | None:
            project_id = target_project.currentData()
            return next((project for project in self.workspace.projects if project.id == project_id), None)

        def update_target_text() -> None:
            nonlocal to_task_button
            project = selected_target_project()
            name = project.name if project else "未选择项目"
            target_hint.setText(f"将手动转入：{name}")
            if to_task_button:
                to_task_button.setText(f"转为“{name}”任务")

        def render() -> None:
            rendered[:] = sorted(self.workspace.inboxTasks, key=lambda value: value.createdDate, reverse=True)
            table.setRowCount(len(rendered))
            for row, item in enumerate(rendered):
                values = [item.createdDate, item.title, item.description, item.source, item.status, item.suggestedAction, self._project_name(item.suggestedProjectId), item.suggestionReason]
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    cell.setToolTip(str(value))
                    cell.setData(Qt.UserRole, item.id)
                    table.setItem(row, col, cell)
                table.setRowHeight(row, 42)
            table.resizeColumnsToContents()
            table.setColumnWidth(1, 220)
            table.setColumnWidth(2, 280)
            table.setColumnWidth(7, 280)

        def selected_item() -> InboxTask | None:
            row = table.currentRow()
            if row < 0 or row >= len(rendered):
                return None
            return rendered[row]

        def add_item() -> None:
            dialog = InboxTaskDialog(parent=page)
            if dialog.exec() == QDialog.Accepted:
                item = add_inbox_task(self.workspace, dialog.values())
                suggest_inbox_task(self.workspace, item)
                save_workspace(self.workspace)
                render()
                self.refresh()

        def edit_item() -> None:
            item = selected_item()
            if not item:
                QMessageBox.information(page, "请选择待归档任务", "请先选中一条记录。")
                return
            dialog = InboxTaskDialog(item, page)
            if dialog.exec() == QDialog.Accepted:
                update_inbox_task(item, dialog.values())
                suggest_inbox_task(self.workspace, item)
                save_workspace(self.workspace)
                render()
                self.refresh()

        def delete_item() -> None:
            item = selected_item()
            if not item:
                QMessageBox.information(page, "请选择待归档任务", "请先选中一条记录。")
                return
            if QMessageBox.question(page, "确认删除", f"删除待归档任务“{item.title}”？") == QMessageBox.Yes:
                delete_inbox_task(self.workspace, item.id)
                save_workspace(self.workspace)
                render()
                self.refresh()

        def suggest_all() -> None:
            for item in self.workspace.inboxTasks:
                if item.status in ("待处理", "待归档"):
                    suggest_inbox_task(self.workspace, item)
            save_workspace(self.workspace)
            render()
            self.refresh()

        def accept_selected() -> None:
            item = selected_item()
            if not item:
                QMessageBox.information(page, "请选择待归档任务", "请先选中一条记录。")
                return
            if not item.suggestedAction:
                suggest_inbox_task(self.workspace, item)
            result = accept_inbox_suggestion(self.workspace, item, selected_target_project() or self.current_project())
            save_workspace(self.workspace)
            render()
            self.refresh()
            if result is None:
                QMessageBox.information(page, "需要人工判断", "该记录暂未形成明确建议，可手动转为任务、归档或新增项目。")

        def to_task_selected_project() -> None:
            item = selected_item()
            project = selected_target_project()
            if not item or not project:
                QMessageBox.information(page, "请选择目标项目", "请先选择要转入的项目。")
                return
            task = add_task_to_project(project, today(), {"title": item.title or "待归档任务", "note": item.description, "risk": "M", "duration": 1, "status": "Open", "plannedProgress": 0, "actualProgress": 0})
            item.status = "已转项目任务"
            item.confirmed = True
            item.suggestedProjectId = project.id
            item.suggestedAction = "转为项目任务"
            item.suggestionReason = f"已手动转为“{project.name}”任务。"
            self.workspace.selectedProjectId = project.id
            self.selected_task_id = task.id
            save_workspace(self.workspace)
            render()
            self.refresh()

        def new_project_from_item() -> None:
            item = selected_item()
            if not item:
                return
            project = add_project_to_workspace(self.workspace, {"name": item.title or "新项目", "summary": item.description, "nextStep": "请补充任务台账。"})
            item.status = "已新建项目"
            item.confirmed = True
            item.suggestedProjectId = project.id
            item.suggestedAction = "建议新建项目"
            item.suggestionReason = "已手动创建新项目。"
            save_workspace(self.workspace)
            render()
            self.refresh()
            self._switch_to_task_plan(project.id)

        table.itemDoubleClicked.connect(lambda _item: edit_item())
        target_project.currentIndexChanged.connect(lambda _index: update_target_text())
        actions = QHBoxLayout()
        for label, handler, obj in [
            ("新增待归档任务", add_item, "primary"),
            ("编辑", edit_item, ""),
            ("删除", delete_item, "danger"),
            ("刷新建议", suggest_all, ""),
            ("采纳建议", accept_selected, "alt"),
            ("转为目标项目任务", to_task_selected_project, ""),
            ("新增项目", new_project_from_item, ""),
        ]:
            button = QPushButton(label)
            if label == "转为目标项目任务":
                to_task_button = button
            if obj:
                button.setObjectName(obj)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        render()
        update_target_text()
        return page

    def _build_daily_log_page(self) -> QWidget:
        page, layout = self._page_shell("日报记录", "跨项目日报流水，默认查看全部项目；编辑或删除时会自动切换到该日报所属项目。")
        filter_row = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("搜索项目 / 负责人 / 任务 / 计划 / 实际 / 延期原因")
        search_input.setClearButtonEnabled(True)
        project_filter = QComboBox()
        project_filter.addItem("全部项目", "")
        result_filter = QComboBox()
        result_filter.addItems(["全部结果", "完成", "部分完成", "延期"])
        result_label = QLabel()
        result_label.setStyleSheet("color:#6b7682;font-weight:900;")
        for project in sorted_projects(self.workspace.projects):
            project_filter.addItem(project.name, project.id)
        filter_row.addWidget(search_input, 1)
        filter_row.addWidget(project_filter)
        filter_row.addWidget(result_filter)
        filter_row.addWidget(result_label)
        layout.addLayout(filter_row)

        table = self._make_table(["项目", "日期", "负责人", "任务", "计划完成", "实际完成", "计划", "实际", "结果", "延期原因"])
        layout.addWidget(table, 1)
        rendered: list[tuple[Project, DailyLog]] = []

        def task_name(project: Project, log: DailyLog) -> str:
            return next((task.title for task in project.tasks if task.id == log.taskId), "")

        def render() -> None:
            keyword = search_input.text().strip().lower()
            selected_project_id = project_filter.currentData()
            selected_result = result_filter.currentText()
            rendered.clear()
            total = 0
            for project in sorted_projects(self.workspace.projects):
                if selected_project_id and project.id != selected_project_id:
                    continue
                for log in project.dailyLogs:
                    total += 1
                    name = task_name(project, log)
                    if selected_result != "全部结果" and log.result != selected_result:
                        continue
                    if keyword:
                        haystack = " ".join([project.name, log.date, log.responsible, name, log.planText, log.actualText, log.result, log.delayReason]).lower()
                        if keyword not in haystack:
                            continue
                    rendered.append((project, log))
            rendered.sort(key=lambda item: (item[1].date, item[0].name), reverse=True)
            table.setRowCount(len(rendered))
            result_label.setText(f"{len(rendered)} / {total} 条")
            for row, (project, log) in enumerate(rendered):
                values = [project.name, log.date, log.responsible, task_name(project, log), log.planText, log.actualText, f"{log.plannedProgress}%", f"{log.actualProgress}%", log.result, log.delayReason]
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    cell.setToolTip(str(value))
                    cell.setData(Qt.UserRole, log.id)
                    cell.setData(Qt.UserRole + 1, project.id)
                    if log.result == "延期":
                        cell.setBackground(QColor("#fee2e2"))
                    table.setItem(row, col, cell)
                table.setRowHeight(row, 42)
            table.resizeColumnsToContents()
            table.setColumnWidth(0, 180)
            table.setColumnWidth(3, 260)
            table.setColumnWidth(4, 260)
            table.setColumnWidth(5, 260)
            table.setColumnWidth(9, 260)

        def selected_log_pair() -> tuple[Project | None, DailyLog | None]:
            row = table.currentRow()
            if row < 0 or row >= len(rendered):
                return None, None
            return rendered[row]

        def select_current_log() -> None:
            project, log = selected_log_pair()
            if project and log:
                self.workspace.selectedProjectId = project.id
                self.workspace.selectedDate = log.date
                self.selected_task_id = log.taskId
                self.selected_log_id = log.id

        def edit_current() -> None:
            project, log = selected_log_pair()
            if not project or not log:
                QMessageBox.information(page, "请选择日报", "请先选中一条日报记录。")
                return
            select_current_log()
            self.edit_daily()

        def delete_current() -> None:
            project, log = selected_log_pair()
            if not project or not log:
                QMessageBox.information(page, "请选择日报", "请先选中一条日报记录。")
                return
            select_current_log()
            self.delete_daily()

        search_input.textChanged.connect(lambda _text: render())
        project_filter.currentIndexChanged.connect(lambda _index: render())
        result_filter.currentIndexChanged.connect(lambda _index: render())
        table.itemSelectionChanged.connect(select_current_log)
        table.itemDoubleClicked.connect(lambda _item: edit_current())
        actions = QHBoxLayout()
        for label, handler, obj in [("新增当前项目日报", self.add_daily, "primary"), ("编辑日报", edit_current, ""), ("删除日报", delete_current, "danger")]:
            button = QPushButton(label)
            if obj:
                button.setObjectName(obj)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        render()
        return page

    def _build_risk_board_page(self) -> QWidget:
        page, layout = self._page_shell("风险看板", "聚合当前项目的高风险、逾期未关闭和进度落后任务。")
        project = self.current_project()
        table = self._make_table(["关注原因", "风险", "任务", "负责人", "状态", "结束", "进度", "备注"])
        rows = []
        ids = []
        if project:
            current = today()
            for task in project.tasks:
                entry = latest_entry(task)
                reasons = []
                if task.risk == "H" and task.status != "Closed":
                    reasons.append("高风险")
                if task.status != "Closed" and task_end_date(task) < current:
                    reasons.append("逾期未关闭")
                if entry.plannedProgress - entry.actualProgress >= 10 and task.status != "Closed":
                    reasons.append("进度落后")
                if reasons:
                    ids.append(task.id)
                    rows.append([" / ".join(reasons), task.risk, task.title, task.responsible, STATUS_LABELS.get(task.status, task.status), task_end_date(task), f"计划 {entry.plannedProgress}% / 实际 {entry.actualProgress}%", task.note])
        if not rows:
            rows = [["暂无异常", "", "", "", "", "", "", ""]]
            ids = [""]
        self._fill_table(table, rows, ids)
        layout.addWidget(table, 1)

        def edit_current() -> None:
            row = table.currentRow()
            if row < 0:
                return
            task_id = table.item(row, 0).data(Qt.UserRole)
            if task_id:
                self.selected_task_id = task_id
                self.edit_task()

        table.itemDoubleClicked.connect(lambda _item: edit_current())
        actions = QHBoxLayout()
        button = QPushButton("编辑选中任务")
        button.clicked.connect(edit_current)
        actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        return page

    def _build_data_center_page(self) -> QWidget:
        page, layout = self._page_shell("数据中心", "导入/导出本地 JSON、CSV、Excel，或打开本地数据目录。")
        grid = QGridLayout()
        grid.setSpacing(10)
        items = [
            ("导入网页版 JSON", "兼容网页版 workspace、单项目 JSON 和旧版导出。", self.import_json, "primary"),
            ("导出完整 JSON", "适合备份和跨设备迁移。", self.export_json, ""),
            ("导出当前项目 CSV", "导出当前项目任务台账。", self.export_csv, ""),
            ("导出当前项目 Excel", "生成包含概览、任务、日报和甘特日期表的 Excel。", self.export_excel, "alt"),
            ("打开数据目录", "查看 workspace.json 和自动备份。", self.open_data_dir, ""),
        ]
        for index, (title, desc, handler, obj) in enumerate(items):
            card = QFrame()
            card.setObjectName("card")
            self._add_shadow(card)
            box = QVBoxLayout(card)
            box.setContentsMargins(16, 14, 16, 14)
            head = QLabel(title)
            head.setStyleSheet("font-size:15px;font-weight:900;color:#1f2933;")
            note = QLabel(desc)
            note.setWordWrap(True)
            note.setStyleSheet("color:#6b7682;")
            button = QPushButton(title)
            if obj:
                button.setObjectName(obj)
            button.clicked.connect(handler)
            box.addWidget(head)
            box.addWidget(note, 1)
            box.addWidget(button)
            grid.addWidget(card, index // 3, index % 3)
        layout.addLayout(grid)
        layout.addStretch()
        return page

    def _show_table_dialog(self, title: str, headers: list[str], rows: list[list[str]], width: int = 1100, height: int = 620) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(width, height)
        layout = QVBoxLayout(dialog)
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setRowCount(len(rows))
        for row_index, row_values in enumerate(rows):
            for col_index, value in enumerate(row_values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                table.setItem(row_index, col_index, item)
            table.setRowHeight(row_index, 38)
        table.horizontalHeader().setStretchLastSection(True)
        table.resizeColumnsToContents()
        layout.addWidget(table)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        dialog.exec()


    def open_overview_view(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("总览 · 每日任务总览")
        dialog.resize(1460, 760)
        layout = QVBoxLayout(dialog)
        title = QLabel("每日任务总览")
        title.setStyleSheet("font-size:20px;font-weight:900;")
        desc = QLabel("跨项目查看选中日期需要处理的任务：日期范围覆盖当天、今日截止、已逾期未关闭，或当天已有日报记录的任务都会显示。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#64748b;")
        layout.addWidget(title)
        layout.addWidget(desc)

        control_row = QHBoxLayout()
        prev_btn = QPushButton("前一天")
        next_btn = QPushButton("后一天")
        today_btn = QPushButton("今天")
        initial_date = normalize_ui_date(self.workspace.selectedDate) or today()
        date_input = make_date_edit(initial_date)
        date_input.setMaximumWidth(158)
        date_input.setToolTip("选择每日任务总览日期")
        stats_label = QLabel("")
        stats_label.setStyleSheet("color:#334155;font-weight:800;")
        control_row.addWidget(QLabel("日期"))
        control_row.addWidget(date_input)
        control_row.addWidget(prev_btn)
        control_row.addWidget(today_btn)
        control_row.addWidget(next_btn)
        control_row.addStretch()
        control_row.addWidget(stats_label)
        layout.addLayout(control_row)

        table = QTableWidget()
        table.setColumnCount(11)
        table.setHorizontalHeaderLabels(["项目", "关注", "风险", "任务", "负责人", "任务周期", "状态", "计划", "实际", "今日日报", "操作提示"])
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table, 1)

        rendered: list[tuple[Project, Task, DailyLog | None, str]] = []

        def safe_parse(value: str, fallback_year: int | None = None) -> date | None:
            normalized = normalize_ui_date(value, fallback_year=fallback_year)
            if not normalized:
                return None
            try:
                return date.fromisoformat(normalized)
            except Exception:
                return None

        def log_for(project: Project, task: Task, value: str) -> DailyLog | None:
            normalized_value = normalize_ui_date(value) or value
            return next((log for log in project.dailyLogs if log.taskId == task.id and (normalize_ui_date(log.date) or log.date) == normalized_value), None)

        def classify(project: Project, task: Task, value: str) -> tuple[list[str], DailyLog | None, int]:
            selected = safe_parse(value)
            fallback_year = selected.year if selected else None
            start = safe_parse(task.startDate, fallback_year=fallback_year)
            try:
                end_text = task_end_date(task)
            except Exception:
                end_text = ""
            end = safe_parse(end_text, fallback_year=fallback_year)
            log = log_for(project, task, value)
            if not selected or not start or not end:
                return (["日期异常"] if log else []), log, 99
            active = start <= selected <= end and task.status != "Closed"
            due_today = end == selected and task.status != "Closed"
            overdue = end < selected and task.status != "Closed"
            has_log = log is not None
            if not (active or due_today or overdue or has_log):
                return [], log, 99
            reasons: list[str] = []
            priority = 50
            if overdue:
                reasons.append("逾期")
                priority = min(priority, 1)
            if task.risk == "H" and task.status != "Closed":
                reasons.append("高风险")
                priority = min(priority, 2)
            if due_today:
                reasons.append("今日截止")
                priority = min(priority, 3)
            if active and not has_log:
                reasons.append("待写日报")
                priority = min(priority, 4)
            if has_log:
                reasons.append("已有日报" if log.result != "延期" else "日报延期")
                priority = min(priority, 5 if log.result != "延期" else 2)
            return reasons or ["今日相关"], log, priority

        def render() -> None:
            selected_date = date_input.date().toString("yyyy-MM-dd")
            self.workspace.selectedDate = selected_date
            rendered.clear()
            collected: list[tuple[int, Project, Task, DailyLog | None, str]] = []
            for project in sorted_projects(self.workspace.projects):
                for task in project.tasks:
                    reasons, log, priority = classify(project, task, selected_date)
                    if reasons:
                        collected.append((priority, project, task, log, " / ".join(reasons)))
            collected.sort(key=lambda item: (item[0], item[1].deadline, item[2].risk != "H", task_end_date(item[2]), item[1].name, item[2].title))
            rendered.extend([(project, task, log, reason) for _priority, project, task, log, reason in collected])
            table.setRowCount(len(rendered))
            overdue_num = sum(1 for _p, _t, _l, reason in rendered if "逾期" in reason)
            high_num = sum(1 for _p, task, _l, _r in rendered if task.risk == "H" and task.status != "Closed")
            missing_log = sum(1 for _p, _t, log, reason in rendered if log is None and "待写日报" in reason)
            stats_label.setText(f"今日相关 {len(rendered)} 项 · 逾期 {overdue_num} · 高风险 {high_num} · 待写日报 {missing_log}")
            for row, (project, task, log, reason) in enumerate(rendered):
                entry = latest_entry(task)
                log_text = "未写" if log is None else log.result
                values = [
                    project.name,
                    reason,
                    task.risk,
                    task.title,
                    task.responsible,
                    f"{normalize_ui_date(task.startDate) or task.startDate} ~ {task_end_date(task)}",
                    STATUS_LABELS.get(task.status, task.status),
                    f"{entry.plannedProgress}%",
                    f"{entry.actualProgress}%",
                    log_text,
                    "双击进入项目；可用下方按钮写日报/编辑任务",
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setToolTip(str(value))
                    item.setData(Qt.UserRole, project.id)
                    item.setData(Qt.UserRole + 1, task.id)
                    if "逾期" in reason:
                        item.setBackground(QColor("#fee2e2"))
                    elif "高风险" in reason:
                        item.setBackground(QColor("#fef3c7"))
                    elif log_text == "未写":
                        item.setBackground(QColor("#eff6ff"))
                    table.setItem(row, col, item)
                table.setRowHeight(row, 42)
            table.resizeColumnsToContents()
            table.setColumnWidth(0, 180)
            table.setColumnWidth(1, 150)
            table.setColumnWidth(3, 300)
            table.setColumnWidth(10, 260)

        def selected_pair() -> tuple[Project | None, Task | None]:
            row = table.currentRow()
            if row < 0 or row >= len(rendered):
                return None, None
            project, task, _log, _reason = rendered[row]
            return project, task

        def enter_project() -> None:
            project, task = selected_pair()
            if not project or not task:
                QMessageBox.information(dialog, "请选择任务", "请先选中一条每日任务。")
                return
            self.workspace.selectedProjectId = project.id
            self.workspace.selectedDate = date_input.date().toString("yyyy-MM-dd")
            self.selected_task_id = task.id
            save_workspace(self.workspace)
            self.refresh()
            dialog.accept()
            if hasattr(self, "sidebar"):
                self.sidebar.set_active("任务计划")

        def write_daily() -> None:
            project, task = selected_pair()
            if not project or not task:
                QMessageBox.information(dialog, "请选择任务", "请先选中一条每日任务。")
                return
            self.workspace.selectedProjectId = project.id
            self.workspace.selectedDate = date_input.date().toString("yyyy-MM-dd")
            self.selected_task_id = task.id
            save_workspace(self.workspace)
            self.refresh()
            dialog.accept()
            self.add_daily()

        def edit_selected_task() -> None:
            project, task = selected_pair()
            if not project or not task:
                QMessageBox.information(dialog, "请选择任务", "请先选中一条每日任务。")
                return
            self.workspace.selectedProjectId = project.id
            self.selected_task_id = task.id
            save_workspace(self.workspace)
            self.refresh()
            dialog.accept()
            self.edit_task()

        def shift_day(delta: int) -> None:
            date_input.setDate(date_input.date().addDays(delta))

        prev_btn.clicked.connect(lambda _checked=False: shift_day(-1))
        next_btn.clicked.connect(lambda _checked=False: shift_day(1))
        today_btn.clicked.connect(lambda _checked=False: date_input.setDate(QDate.currentDate()))
        date_input.dateChanged.connect(lambda _date: render())
        table.itemDoubleClicked.connect(lambda _item: enter_project())

        buttons = QHBoxLayout()
        for label, fn, obj in [("进入项目任务计划", enter_project, "primary"), ("写日报", write_daily, "alt"), ("编辑任务", edit_selected_task, "")]:
            button = QPushButton(label)
            if obj:
                button.setObjectName(obj)
            button.clicked.connect(fn)
            buttons.addWidget(button)
        buttons.addStretch()
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        render()
        dialog.exec()

    def open_project_board_view(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("项目看板 · 全部项目")
        dialog.resize(1240, 680)
        layout = QVBoxLayout(dialog)
        title = QLabel("项目看板")
        title.setStyleSheet("font-size:20px;font-weight:900;")
        desc = QLabel("集中查看所有项目的 deadline、计划/实际进度、逾期任务、任务完成情况和档案数量。双击项目或点击“切换到项目”即可进入对应项目。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#64748b;")
        layout.addWidget(title)
        layout.addWidget(desc)
        table = QTableWidget()
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels(["项目", "Deadline", "剩余/逾期", "计划", "实际", "任务数", "已关闭", "逾期", "档案", "一句话总结"])
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        rows = []
        for project in self.workspace.projects:
            planned, actual = project_progress(project)
            closed = sum(1 for task in project.tasks if task.status == "Closed")
            try:
                remain = days_between(today(), project.deadline)
                remain_text = f"剩余 {remain} 天" if remain >= 0 else f"逾期 {abs(remain)} 天"
            except Exception:
                remain_text = "-"
            rows.append((project, [
                project.name,
                project.deadline,
                remain_text,
                f"{planned}%",
                f"{actual}%",
                str(len(project.tasks)),
                str(closed),
                str(overdue_count(project)),
                str(len(project.archives)),
                project.summary,
            ]))
        table.setRowCount(len(rows))
        for row, (project, values) in enumerate(rows):
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                item.setData(Qt.UserRole, project.id)
                if col == 2 and "逾期" in str(value):
                    item.setBackground(QColor("#fee2e2"))
                table.setItem(row, col, item)
            table.setRowHeight(row, 42)
        table.resizeColumnsToContents()
        table.setColumnWidth(0, 220)
        table.setColumnWidth(9, 360)
        layout.addWidget(table, 1)

        def switch_project() -> None:
            row = table.currentRow()
            if row < 0:
                return
            item = table.item(row, 0)
            project_id = item.data(Qt.UserRole) if item else None
            if project_id:
                self.workspace.selectedProjectId = project_id
                self.selected_task_id = None
                save_workspace(self.workspace)
                self.refresh()
                dialog.accept()
                if hasattr(self, "sidebar"):
                    self.sidebar.set_active("任务计划")

        table.itemDoubleClicked.connect(lambda _item: switch_project())
        buttons = QHBoxLayout()
        switch_btn = QPushButton("切换到项目")
        switch_btn.setObjectName("primary")
        switch_btn.clicked.connect(switch_project)
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        buttons.addWidget(switch_btn)
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)
        dialog.exec()

    def _project_name(self, project_id: str) -> str:
        return next((project.name for project in self.workspace.projects if project.id == project_id), "")

    def open_archive_view(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("项目档案 · 全部项目")
        dialog.resize(1420, 760)
        layout = QVBoxLayout(dialog)
        header = QHBoxLayout()
        title = QLabel("项目档案")
        title.setStyleSheet("font-size:20px;font-weight:900;")
        subtitle = QLabel("按项目集中展示实验数据、汇报PPT、会议纪要、图片截图和交付版本；支持跨项目关键词搜索。")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#64748b;")
        title_box = QVBoxLayout()
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        layout.addLayout(header)

        search_row = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("搜索档案：项目 / 标题 / 关键词 / 摘要 / 负责人 / 类型 / 路径 / 关联任务")
        search_input.setClearButtonEnabled(True)
        search_input.setMinimumHeight(36)
        project_filter = QComboBox()
        project_filter.addItem("全部项目", "")
        for item in self.workspace.projects:
            project_filter.addItem(item.name, item.id)
        type_filter = QComboBox()
        type_filter.addItems(["全部类型", "实验数据", "会议纪要", "汇报PPT", "图片截图", "交付版本", "其他"])
        status_filter = QComboBox()
        status_filter.addItems(["全部状态", "待整理", "已归档", "已完成", "待补充", "已废弃", "已过期"])
        result_label = QLabel()
        result_label.setStyleSheet("color:#64748b;font-weight:700;")
        search_row.addWidget(search_input, 1)
        search_row.addWidget(project_filter)
        search_row.addWidget(type_filter)
        search_row.addWidget(status_filter)
        search_row.addWidget(result_label)
        layout.addLayout(search_row)

        table = QTableWidget()
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels(["项目", "日期", "类型", "标题", "负责人", "关键词", "摘要/结论", "路径", "状态", "关联任务"])
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table, 1)

        rendered: list[tuple[Project, ArchiveItem]] = []

        def task_name(project: Project, archive: ArchiveItem) -> str:
            return next((task.title for task in project.tasks if task.id == archive.relatedTaskId), "")

        def render() -> None:
            keyword = search_input.text().strip().lower()
            selected_project_id = project_filter.currentData()
            selected_type = type_filter.currentText()
            selected_status = status_filter.currentText()
            rendered.clear()
            total = 0
            for project in self.workspace.projects:
                if selected_project_id and project.id != selected_project_id:
                    continue
                for archive in sorted(project.archives, key=lambda item: item.date, reverse=True):
                    total += 1
                    related_task_name = task_name(project, archive)
                    if selected_type != "全部类型" and archive.type != selected_type:
                        continue
                    if selected_status != "全部状态" and archive.status != selected_status:
                        continue
                    if keyword:
                        haystack = " ".join([
                            project.name, archive.date, archive.type, archive.title, archive.owner,
                            archive.keywords, archive.summary, archive.path, archive.status, related_task_name,
                        ]).lower()
                        if keyword not in haystack:
                            continue
                    rendered.append((project, archive))
            table.setRowCount(len(rendered))
            result_label.setText(f"{len(rendered)} / {total} 条")
            for row, (project, archive) in enumerate(rendered):
                values = [project.name, archive.date, archive.type, archive.title, archive.owner, archive.keywords, archive.summary, archive.path, archive.status, task_name(project, archive)]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setToolTip(str(value))
                    item.setData(Qt.UserRole, archive.id)
                    item.setData(Qt.UserRole + 1, project.id)
                    table.setItem(row, col, item)
                table.setRowHeight(row, 42)
            table.resizeColumnsToContents()
            table.setColumnWidth(0, 180)
            table.setColumnWidth(3, 240)
            table.setColumnWidth(6, 260)
            table.setColumnWidth(7, 260)

        def selected_archive_pair() -> tuple[Project, ArchiveItem] | tuple[None, None]:
            row = table.currentRow()
            if row < 0 or row >= len(rendered):
                return None, None
            return rendered[row]

        def add_item() -> None:
            project = self.current_project() or (self.workspace.projects[0] if self.workspace.projects else None)
            if not project:
                return
            dlg = ArchiveDialog(project, parent=dialog)
            if dlg.exec() == QDialog.Accepted:
                add_archive(project, dlg.values())
                save_workspace(self.workspace)
                render()
                self.refresh()

        def edit_item() -> None:
            project, archive = selected_archive_pair()
            if not project or not archive:
                QMessageBox.information(dialog, "请选择档案", "请先选中一条档案记录。")
                return
            dlg = ArchiveDialog(project, archive, dialog)
            if dlg.exec() == QDialog.Accepted:
                update_archive(archive, dlg.values())
                save_workspace(self.workspace)
                render()
                self.refresh()

        def delete_item() -> None:
            project, archive = selected_archive_pair()
            if not project or not archive:
                QMessageBox.information(dialog, "请选择档案", "请先选中一条档案记录。")
                return
            if QMessageBox.question(dialog, "确认删除", f"删除档案“{archive.title}”？") == QMessageBox.Yes:
                delete_archive(project, archive.id)
                save_workspace(self.workspace)
                render()
                self.refresh()

        def open_path() -> None:
            _project, archive = selected_archive_pair()
            if not archive or not archive.path:
                QMessageBox.information(dialog, "没有路径", "该档案没有填写文件或目录路径。")
                return
            path = Path(archive.path)
            if path.exists():
                subprocess.Popen(["explorer", str(path if path.is_dir() else path.parent)])
            else:
                QMessageBox.warning(dialog, "路径不存在", str(path))

        search_input.textChanged.connect(lambda _text: render())
        project_filter.currentIndexChanged.connect(lambda _index: render())
        type_filter.currentIndexChanged.connect(lambda _index: render())
        status_filter.currentIndexChanged.connect(lambda _index: render())

        buttons = QHBoxLayout()
        for label, fn, obj in [("新增档案", add_item, "primary"), ("编辑档案", edit_item, ""), ("删除档案", delete_item, ""), ("打开路径", open_path, "alt")]:
            button = QPushButton(label)
            if obj:
                button.setObjectName(obj)
            button.clicked.connect(fn)
            buttons.addWidget(button)
        buttons.addStretch()
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        render()
        dialog.exec()

    def open_inbox_view(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("待归档任务收集箱")
        dialog.resize(1320, 720)
        layout = QVBoxLayout(dialog)
        header = QVBoxLayout()
        title = QLabel("待归档任务收集箱")
        title.setStyleSheet("font-size:20px;font-weight:900;")
        desc = QLabel("先把暂时无法归入项目的待办、实验线索、资料和想法放入收集箱；后续可建议归档、手动归档、转为项目任务，或新建项目。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#64748b;")
        header.addWidget(title)
        header.addWidget(desc)
        layout.addLayout(header)

        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(["日期", "标题", "说明", "来源", "状态", "建议动作", "建议项目", "建议原因"])
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table, 1)

        def render() -> None:
            table.setRowCount(len(self.workspace.inboxTasks))
            for row, item in enumerate(sorted(self.workspace.inboxTasks, key=lambda value: value.createdDate, reverse=True)):
                values = [item.createdDate, item.title, item.description, item.source, item.status, item.suggestedAction, self._project_name(item.suggestedProjectId), item.suggestionReason]
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    cell.setToolTip(str(value))
                    cell.setData(Qt.UserRole, item.id)
                    table.setItem(row, col, cell)
                table.setRowHeight(row, 42)
            table.resizeColumnsToContents()
            table.setColumnWidth(1, 220)
            table.setColumnWidth(2, 280)
            table.setColumnWidth(7, 280)

        def selected_item() -> InboxTask | None:
            row = table.currentRow()
            if row < 0:
                return None
            cell = table.item(row, 0)
            item_id = cell.data(Qt.UserRole) if cell else None
            return next((item for item in self.workspace.inboxTasks if item.id == item_id), None)

        def add_item() -> None:
            dlg = InboxTaskDialog(parent=dialog)
            if dlg.exec() == QDialog.Accepted:
                item = add_inbox_task(self.workspace, dlg.values())
                suggest_inbox_task(self.workspace, item)
                save_workspace(self.workspace)
                render()
                self.refresh()

        def edit_item() -> None:
            item = selected_item()
            if not item:
                QMessageBox.information(dialog, "请选择待归档任务", "请先选中一条记录。")
                return
            dlg = InboxTaskDialog(item, dialog)
            if dlg.exec() == QDialog.Accepted:
                update_inbox_task(item, dlg.values())
                suggest_inbox_task(self.workspace, item)
                save_workspace(self.workspace)
                render()
                self.refresh()

        def delete_item() -> None:
            item = selected_item()
            if not item:
                QMessageBox.information(dialog, "请选择待归档任务", "请先选中一条记录。")
                return
            if QMessageBox.question(dialog, "确认删除", f"删除待归档任务“{item.title}”？") == QMessageBox.Yes:
                delete_inbox_task(self.workspace, item.id)
                save_workspace(self.workspace)
                render()
                self.refresh()

        def suggest_all() -> None:
            for item in self.workspace.inboxTasks:
                if item.status in ("待处理", "待归档"):
                    suggest_inbox_task(self.workspace, item)
            save_workspace(self.workspace)
            render()
            self.refresh()

        def accept_selected() -> None:
            item = selected_item()
            if not item:
                QMessageBox.information(dialog, "请选择待归档任务", "请先选中一条记录。")
                return
            if not item.suggestedAction:
                suggest_inbox_task(self.workspace, item)
            current = self.current_project()
            result = accept_inbox_suggestion(self.workspace, item, current)
            save_workspace(self.workspace)
            render()
            self.refresh()
            if result is None:
                QMessageBox.information(dialog, "需要人工判断", "该记录暂未形成明确建议，可手动转为任务、归档或新增项目。")
            else:
                QMessageBox.information(dialog, "已采纳建议", f"已执行：{item.suggestedAction}")

        def to_task_current() -> None:
            item = selected_item()
            project = self.current_project()
            if not item or not project:
                return
            task = add_task_to_project(project, today(), {"title": item.title or "待归档任务", "note": item.description, "risk": "M", "duration": 1, "status": "Open", "plannedProgress": 0, "actualProgress": 0})
            item.status = "已转项目任务"
            item.confirmed = True
            item.suggestedProjectId = project.id
            item.suggestedAction = "转为项目任务"
            item.suggestionReason = f"已手动转为当前项目“{project.name}”任务。"
            self.selected_task_id = task.id
            save_workspace(self.workspace)
            render()
            self.refresh()

        def archive_current() -> None:
            item = selected_item()
            if not item:
                QMessageBox.information(dialog, "请选择待归档任务", "请先选中一条记录。")
                return
            chooser = QDialog(dialog)
            chooser.setWindowTitle("手动归档待归档任务")
            chooser.resize(560, 360)
            form = QFormLayout(chooser)
            project_combo = QComboBox()
            for project_item in self.workspace.projects:
                project_combo.addItem(project_item.name, project_item.id)
            task_combo = QComboBox()

            def refresh_tasks() -> None:
                task_combo.clear()
                task_combo.addItem("无关联任务", "")
                project_id = project_combo.currentData()
                project_item = next((p for p in self.workspace.projects if p.id == project_id), None)
                if project_item:
                    for task_item in project_item.tasks:
                        task_combo.addItem(task_item.title, task_item.id)

            project_combo.currentIndexChanged.connect(lambda _index: refresh_tasks())
            refresh_tasks()
            archive_type = QComboBox()
            archive_type.addItems(["实验数据", "汇报PPT", "会议纪要", "图片截图", "交付版本", "其他"])
            archive_type.setCurrentText(archive_type_from_text(f"{item.title} {item.description}"))
            keywords = QLineEdit(item.source)
            path_input = QLineEdit()
            browse = QPushButton("选择文件/目录")

            def browse_path() -> None:
                path, _ = QFileDialog.getOpenFileName(chooser, "选择归档文件", "", "All Files (*.*)")
                if not path:
                    directory = QFileDialog.getExistingDirectory(chooser, "选择归档目录")
                    path = directory or ""
                if path:
                    path_input.setText(path)

            browse.clicked.connect(browse_path)
            path_row = QHBoxLayout()
            path_row.addWidget(path_input, 1)
            path_row.addWidget(browse)
            form.addRow("目标项目", project_combo)
            form.addRow("关联任务", task_combo)
            form.addRow("档案类型", archive_type)
            form.addRow("关键词", keywords)
            form.addRow("路径", path_row)
            buttons_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons_box.accepted.connect(chooser.accept)
            buttons_box.rejected.connect(chooser.reject)
            form.addRow(buttons_box)
            if chooser.exec() != QDialog.Accepted:
                return
            project_id = project_combo.currentData()
            project = next((p for p in self.workspace.projects if p.id == project_id), None)
            if not project:
                return
            add_archive(project, {
                "title": item.title or "待归档记录归档",
                "summary": item.description,
                "type": archive_type.currentText(),
                "keywords": keywords.text().strip(),
                "path": path_input.text().strip(),
                "relatedTaskId": task_combo.currentData() or "",
                "status": "已归档",
            })
            item.status = "已归档到项目"
            item.confirmed = True
            item.suggestedProjectId = project.id
            item.suggestedAction = "手动归档到项目"
            item.suggestionReason = f"已手动归档到项目“{project.name}”，关联任务：{task_combo.currentText()}。"
            save_workspace(self.workspace)
            render()
            self.refresh()

        def new_project_from_item() -> None:
            item = selected_item()
            if not item:
                return
            project = add_project_to_workspace(self.workspace, {"name": item.title or "新项目", "summary": item.description, "nextStep": "请补充任务台账。"})
            item.status = "已新建项目"
            item.confirmed = True
            item.suggestedProjectId = project.id
            item.suggestedAction = "建议新建项目"
            item.suggestionReason = "已手动创建新项目。"
            save_workspace(self.workspace)
            render()
            self.refresh()

        buttons = QHBoxLayout()
        actions = [
            ("新增待归档任务", add_item, "primary"),
            ("编辑", edit_item, ""),
            ("删除", delete_item, ""),
            ("刷新建议", suggest_all, ""),
            ("采纳建议", accept_selected, "alt"),
            ("转为当前项目任务", to_task_current, ""),
            ("手动归档到项目", archive_current, ""),
            ("新增项目", new_project_from_item, ""),
        ]
        for label, fn, obj in actions:
            button = QPushButton(label)
            if obj:
                button.setObjectName(obj)
            button.clicked.connect(fn)
            buttons.addWidget(button)
        buttons.addStretch()
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        render()
        dialog.exec()

    def open_task_table_view(self) -> None:
        project = self.current_project()
        if not project:
            return
        rows = []
        for task, depth in ordered_tasks(project.tasks):
            entry = latest_entry(task)
            rows.append([
                task.risk,
                "  " * depth + task.title,
                task.responsible,
                task.startDate,
                task.duration,
                task_end_date(task),
                STATUS_LABELS.get(task.status, task.status),
                f"{entry.plannedProgress}%",
                f"{entry.actualProgress}%",
                task.completedDate,
                task.note,
            ])
        self._show_table_dialog(
            "任务表格",
            ["风险", "任务", "负责人", "开始", "工期", "结束", "状态", "计划", "实际", "完成日", "备注"],
            rows,
            1280,
            720,
        )

    def open_daily_log_view(self) -> None:
        project = self.current_project()
        if not project:
            return
        task_names = {task.id: task.title for task in project.tasks}
        rows = [
            [log.date, log.responsible, task_names.get(log.taskId, ""), log.planText, log.actualText, f"{log.plannedProgress}%", f"{log.actualProgress}%", log.result, log.delayReason]
            for log in sorted(project.dailyLogs, key=lambda item: item.date, reverse=True)
        ]
        self._show_table_dialog(
            "日报记录",
            ["日期", "负责人", "任务", "计划完成", "实际完成", "计划", "实际", "结果", "延期原因"],
            rows,
            1280,
            720,
        )

    def open_risk_board_view(self) -> None:
        project = self.current_project()
        if not project:
            return
        current = today()
        rows = []
        for task in project.tasks:
            entry = latest_entry(task)
            reasons = []
            if task.risk == "H" and task.status != "Closed":
                reasons.append("高风险")
            if task.status != "Closed" and task_end_date(task) < current:
                reasons.append("逾期未关闭")
            if entry.plannedProgress - entry.actualProgress >= 10 and task.status != "Closed":
                reasons.append("进度落后")
            if reasons:
                rows.append([
                    " / ".join(reasons),
                    task.risk,
                    task.title,
                    task.responsible,
                    STATUS_LABELS.get(task.status, task.status),
                    task_end_date(task),
                    f"计划 {entry.plannedProgress}% / 实际 {entry.actualProgress}%",
                    task.note,
                ])
        self._show_table_dialog(
            "风险看板",
            ["关注原因", "风险", "任务", "负责人", "状态", "结束", "进度", "备注"],
            rows or [["暂无异常", "", "", "", "", "", "", ""]],
            1180,
            620,
        )

    def open_data_center_view(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("数据中心")
        dialog.resize(520, 360)
        layout = QVBoxLayout(dialog)
        title = QLabel("数据中心")
        title.setStyleSheet("font-size:20px;font-weight:900;")
        desc = QLabel("导入/导出本地 JSON、CSV、Excel，或打开本地数据目录。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#64748b;")
        layout.addWidget(title)
        layout.addWidget(desc)
        for label, handler in [
            ("导入网页版 JSON", self.import_json),
            ("导出完整 JSON", self.export_json),
            ("导出当前项目 CSV", self.export_csv),
            ("导出当前项目 Excel", self.export_excel),
            ("打开数据目录", self.open_data_dir),
        ]:
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, fn=handler, dlg=dialog: (dlg.accept(), fn()))
            layout.addWidget(button)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(dialog.reject)
        layout.addStretch()
        layout.addWidget(close)
        dialog.exec()

    def refresh(self) -> None:
        self.project_select.blockSignals(True)
        self.project_select.clear()
        for project in sorted_projects(self.workspace.projects):
            self.project_select.addItem(project.name, project.id)
        index = max(0, self.project_select.findData(self.workspace.selectedProjectId))
        self.project_select.setCurrentIndex(index)
        self.project_select.blockSignals(False)
        project = self.current_project()
        if not project:
            return
        planned, actual = project_progress(project)
        self.title.setText(project.name)
        self.summary.setText(project.summary)
        self.deadline_card["value"].setText(project.deadline[5:] if len(project.deadline) == 10 else project.deadline)
        self.deadline_card["note"].setText(self._deadline_note(project.deadline))
        self.actual_card["value"].setText(f"{actual}%")
        self.actual_card["value"].setStyleSheet(f"font-size:30px;font-weight:900;color:{'#dc2626' if actual < planned else '#0f766e'};")
        self.actual_card["note"].setText(f"落后计划 {max(0, planned - actual)}%" if actual < planned else "达到或领先计划")
        self.planned_card["value"].setText(f"{planned}%")
        self.planned_card["note"].setText("基于任务最新计划进度")
        overdue_value = overdue_count(project)
        lagging_value = self._lagging_count(project)
        self.overdue_card["value"].setText(str(overdue_value))
        self.overdue_card["note"].setText("需今日处理" if overdue_value else "暂无逾期")
        if hasattr(self, "sidebar"):
            self.sidebar.update_health(overdue_value, lagging_value)
        self.summary_card["body"].setText(project.summary or "暂无总结。")
        self.risk_card["body"].setText(project.topRisk or "暂无高风险描述。")
        self.next_card["body"].setText(project.nextStep or "暂无下一步计划。")
        self._render_focus(project)
        self.plan.set_project(project, self.workspace.selectedDate, self.selected_task_id)
        self.selected_date_label.setText(f"当前日期：{self.workspace.selectedDate} · 点击甘特图日期后自动切换")
        self._render_logs(project)
        self._render_detail(project)
        if not getattr(self, "_rebuilding_active_page", False):
            self._rebuilding_active_page = True
            try:
                self._rebuild_active_page()
            finally:
                self._rebuilding_active_page = False

    def _deadline_note(self, deadline: str) -> str:
        try:
            remain = days_between(today(), deadline)
        except Exception:
            return "关键交付节点"
        return f"剩余 {remain} 天" if remain >= 0 else f"已逾期 {abs(remain)} 天"

    def _lagging_count(self, project: Project) -> int:
        count = 0
        for task in project.tasks:
            entry = latest_entry(task)
            if entry.plannedProgress - entry.actualProgress >= 10 and task.status != "Closed":
                count += 1
        return count

    def _render_focus(self, project: Project) -> None:
        items = self._focus_items(project)
        for label, item in zip(self.focus_card["items"], items):
            label.setText(item)
        for label in self.focus_card["items"][len(items):]:
            label.setText("-")

    def _focus_items(self, project: Project) -> list[str]:
        current = today()
        overdue = [task for task in project.tasks if task.status != "Closed" and task_end_date(task) < current]
        high = [task for task in project.tasks if task.risk == "H" and task.status != "Closed"]
        lagging = []
        for task in project.tasks:
            entry = latest_entry(task)
            if entry.plannedProgress - entry.actualProgress >= 10 and task.status != "Closed":
                lagging.append(task)
        logged_today = {log.taskId for log in project.dailyLogs if log.date == self.workspace.selectedDate}
        missing_logs = [task for task in project.tasks if task.status == "Ongoing" and task.id not in logged_today]
        output = []
        if overdue:
            output.append(f"● {len(overdue)} 个逾期任务：结束日期已过且未关闭")
        if lagging:
            output.append(f"● {len(lagging)} 个进度落后：实际低于计划 ≥10%")
        if missing_logs:
            output.append(f"● {len(missing_logs)} 条日报缺失：进行中任务今日未更新")
        pending_inbox = [item for item in self.workspace.inboxTasks if item.status in ("待处理", "待归档")]
        if high and len(output) < 3:
            output.append(f"● {len(high)} 个高风险任务：需要重点跟踪")
        if pending_inbox and len(output) < 3:
            output.append(f"● {len(pending_inbox)} 条待归档任务需要处理")
        return output[:3] or ["● 今日暂无需要重点处理的异常"]

    def _render_logs(self, project: Project) -> None:
        task_names = {task.id: task.title for task in project.tasks}
        logs = [log for log in project.dailyLogs if log.date == self.workspace.selectedDate]
        logs.sort(key=lambda item: item.responsible)
        self.log_table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            values = [log.responsible, task_names.get(log.taskId, ""), log.planText, log.actualText, log.result, log.delayReason, log.date]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, log.id)
                item.setToolTip(str(value))
                if log.result == "延期":
                    item.setBackground(QColor("#fee2e2"))
                self.log_table.setItem(row, col, item)
            self.log_table.setRowHeight(row, 42)

    def _render_detail(self, project: Project) -> None:
        task = next((item for item in project.tasks if item.id == self.selected_task_id), None)
        if not task and project.tasks:
            task = project.tasks[0]
            self.selected_task_id = task.id
        if not task:
            self.detail_title.setText("未选择任务")
            self.detail_meta.setText("当前项目暂无任务")
            self.detail_progress.setValue(0)
            self.detail_gap.setText("")
            self.detail_note.setText("新增任务后，这里会显示任务备注、风险说明和进度差异。")
            return
        entry = latest_entry(task)
        self.detail_title.setText(task.title)
        self.detail_meta.setText(f"负责人：{task.responsible or '-'}     风险：{task.risk}     状态：{STATUS_LABELS.get(task.status, task.status)}")
        self.detail_progress.setValue(entry.actualProgress)
        gap = entry.plannedProgress - entry.actualProgress
        self.detail_gap.setText(f"计划 {entry.plannedProgress}% / 实际 {entry.actualProgress}%   ·   落后 {gap}%" if gap > 0 else f"计划 {entry.plannedProgress}% / 实际 {entry.actualProgress}%")
        self.detail_note.setText(task.note or "暂无备注。")

    def _select_project(self) -> None:
        self.workspace.selectedProjectId = self.project_select.currentData()
        self.selected_task_id = None
        save_workspace(self.workspace)
        self.refresh()

    def select_date(self, value: str) -> None:
        self.workspace.selectedDate = value
        save_workspace(self.workspace)
        self.refresh()
        if hasattr(self, "context_tabs"):
            self.context_tabs.setCurrentIndex(1)

    def select_task_by_id(self, task_id: str) -> None:
        self.selected_task_id = task_id
        self.plan.selected_task_id = task_id
        self.plan.viewport().update()
        project = self.current_project()
        if project:
            self._render_detail(project)
        if hasattr(self, "context_tabs"):
            self.context_tabs.setCurrentIndex(0)

    def edit_task_by_id(self, task_id: str) -> None:
        self.select_task_by_id(task_id)
        self.edit_task()

    def selected_task(self) -> Task | None:
        project = self.current_project()
        if not project or not self.selected_task_id:
            return None
        return next((task for task in project.tasks if task.id == self.selected_task_id), None)

    def selected_log(self) -> DailyLog | None:
        project = self.current_project()
        if project and self.selected_log_id:
            selected = next((log for log in project.dailyLogs if log.id == self.selected_log_id), None)
            if selected:
                return selected
        row = self.log_table.currentRow()
        if not project or row < 0:
            return None
        item = self.log_table.item(row, 0)
        log_id = item.data(Qt.UserRole) if item else None
        return next((log for log in project.dailyLogs if log.id == log_id), None)

    def persist(self) -> None:
        save_workspace(self.workspace)
        self.refresh()

    def add_project(self) -> None:
        dialog = ProjectDialog(parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        add_project_to_workspace(self.workspace, dialog.values())
        self.selected_task_id = None
        self.persist()

    def edit_project(self) -> None:
        project = self.current_project()
        if not project:
            return
        dialog = ProjectDialog(project, self)
        if dialog.exec() != QDialog.Accepted:
            return
        update_project(project, dialog.values())
        self.persist()

    def delete_project(self) -> None:
        project = self.current_project()
        if not project:
            return
        ok = QMessageBox.question(self, "确认删除", f"删除项目「{project.name}」会同时删除任务和日报，是否继续？")
        if ok != QMessageBox.Yes:
            return
        try:
            delete_project_from_workspace(self.workspace, project.id)
        except ValueError as exc:
            QMessageBox.warning(self, "不能删除", str(exc))
            return
        self.selected_task_id = None
        self.persist()

    def add_task(self) -> None:
        project = self.current_project()
        if not project:
            return
        dialog = TaskDialog(project, selected_date=self.workspace.selectedDate, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        task = add_task_to_project(project, self.workspace.selectedDate, values)
        self._sync_task_archive(project, task, values)
        self.selected_task_id = task.id
        self.persist()

    def edit_task(self) -> None:
        project = self.current_project()
        task = self.selected_task()
        if not project or not task:
            QMessageBox.information(self, "请选择任务", "请先在任务计划视图中选中一行。")
            return
        dialog = TaskDialog(project, task, self.workspace.selectedDate, self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        update_task(task, self.workspace.selectedDate, values)
        self._sync_task_archive(project, task, values)
        self.selected_task_id = task.id
        self.persist()

    def delete_task(self) -> None:
        project = self.current_project()
        task = self.selected_task()
        if not project or not task:
            QMessageBox.information(self, "请选择任务", "请先在任务计划视图中选中一行。")
            return
        ok = QMessageBox.question(self, "确认删除", f"删除任务「{task.title}」会同时删除它的子任务和相关日报，是否继续？")
        if ok != QMessageBox.Yes:
            return
        delete_task_from_project(project, task.id)
        self.selected_task_id = None
        self.persist()

    def add_daily(self) -> None:
        project = self.current_project()
        if not project:
            return
        if not project.tasks:
            QMessageBox.warning(self, "缺少任务", "请先新增任务，再填写日报。")
            return
        dialog = DailyDialog(project, selected_date=self.workspace.selectedDate, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._save_log_values(None, dialog.values())

    def edit_daily(self) -> None:
        project = self.current_project()
        log = self.selected_log()
        if not project or not log:
            QMessageBox.information(self, "请选择日报", "请先在日报记录中选中一行。")
            return
        dialog = DailyDialog(project, log, self.workspace.selectedDate, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._save_log_values(log, dialog.values())

    def delete_daily(self) -> None:
        project = self.current_project()
        log = self.selected_log()
        if not project or not log:
            QMessageBox.information(self, "请选择日报", "请先在日报记录中选中一行。")
            return
        ok = QMessageBox.question(self, "确认删除", "删除这条日报会同步移除对应日期的任务进度，是否继续？")
        if ok != QMessageBox.Yes:
            return
        delete_log_from_project(project, log.id)
        self.selected_log_id = None
        self.persist()

    def _save_log_values(self, log: DailyLog | None, values: dict) -> None:
        project = self.current_project()
        if not project:
            return
        try:
            saved = save_daily_log(self.workspace, project, log, values)
            self.selected_task_id = saved.taskId
            self.selected_log_id = saved.id
        except ValueError as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self.persist()

    def _sync_task_archive(self, project: Project, task: Task, values: dict) -> None:
        archive_path = values.get("archivePath", "").strip()
        if not archive_path:
            return
        archive_type = values.get("archiveType") or archive_type_from_text(f"{task.title} {task.note} {archive_path}")
        keywords = values.get("archiveKeywords", "")
        existing = next((item for item in project.archives if item.relatedTaskId == task.id and item.path == archive_path), None)
        payload = {
            "date": today(),
            "type": archive_type,
            "title": f"{task.title} - 任务归档",
            "owner": task.responsible,
            "keywords": keywords,
            "summary": task.note or f"由任务“{task.title}”详情编辑页添加的归档路径。",
            "path": archive_path,
            "relatedTaskId": task.id,
            "status": "已归档",
        }
        if existing:
            update_archive(existing, payload)
        else:
            add_archive(project, payload)

    def import_json(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "导入网页版 JSON", "", "JSON Files (*.json)")
        if not file_name:
            return
        try:
            workspace, diagnostics = load_workspace_json(Path(file_name))
            mode = self._confirm_import_mode(workspace, diagnostics)
            if mode == "cancel":
                return
            if mode == "replace":
                self.workspace = workspace
            else:
                merge_workspace(self.workspace, workspace)
            self.selected_task_id = None
            save_workspace(self.workspace)
            self.refresh()
            mode_text = "覆盖" if mode == "replace" else "合并"
            QMessageBox.information(self, "导入完成", "\n".join(diagnostics + [f"导入方式：{mode_text}"]))
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", str(exc))

    def _confirm_import_mode(self, workspace: Workspace, diagnostics: list[str]) -> str:
        project_count = len(workspace.projects)
        task_count = sum(len(project.tasks) for project in workspace.projects)
        log_count = sum(len(project.dailyLogs) for project in workspace.projects)
        message = QMessageBox(self)
        message.setWindowTitle("确认导入方式")
        message.setText(f"识别到 {project_count} 个项目、{task_count} 个任务、{log_count} 条日报。")
        message.setInformativeText("\n".join(diagnostics + ["请选择合并到当前数据，或覆盖当前全部本地数据。"]))
        merge_button = message.addButton("合并到当前数据", QMessageBox.AcceptRole)
        replace_button = message.addButton("覆盖当前数据", QMessageBox.DestructiveRole)
        message.addButton("取消", QMessageBox.RejectRole)
        message.exec()
        clicked = message.clickedButton()
        if clicked == merge_button:
            return "merge"
        if clicked == replace_button:
            return "replace"
        return "cancel"

    def export_json(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(self, "导出 JSON 备份", "project-desk-workspace.json", "JSON Files (*.json)")
        if file_name:
            dump_workspace_json(self.workspace, Path(file_name))

    def export_csv(self) -> None:
        project = self.current_project()
        if not project:
            return
        file_name, _ = QFileDialog.getSaveFileName(self, "导出任务 CSV", f"{project.name}-tasks.csv", "CSV Files (*.csv)")
        if file_name:
            export_tasks_csv(project, Path(file_name))

    def export_excel(self) -> None:
        project = self.current_project()
        if not project:
            return
        file_name, _ = QFileDialog.getSaveFileName(self, "导出 Excel 项目表", f"{project.name}-project-table.xlsx", "Excel Files (*.xlsx)")
        if file_name:
            export_project_excel(project, Path(file_name))

    def open_data_dir(self) -> None:
        path = data_dir()
        path.mkdir(parents=True, exist_ok=True)
        QMessageBox.information(self, "数据目录", f"这里保存本地数据 workspace.json 和自动备份文件。\n\n{path}")
        subprocess.Popen(["explorer", str(path)])


def main() -> int:
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(app_stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()
