from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QComboBox,
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
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .import_export import dump_workspace_json, export_project_excel, export_tasks_csv, load_workspace_json
from .metrics import add_days, days_between, overdue_count, project_progress, task_end_date
from .models import DailyLog, ProgressEntry, Project, Task, Workspace, today
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
)
from .storage import data_dir, load_workspace, save_workspace


STATUS_LABELS = {"Open": "未开始", "Ongoing": "进行中", "Closed": "已关闭"}
RISK_COLORS = {"H": "#dc2626", "M": "#d97706", "L": "#0f766e"}
STATUS_COLORS = {"Open": "#64748b", "Ongoing": "#2563eb", "Closed": "#0f766e"}


QSS = """
QMainWindow { background: #f3f5f7; }
QWidget { font-family: "Microsoft YaHei", "Segoe UI", Arial; font-size: 13px; color: #111827; }
QPushButton, QToolButton {
  border: 1px solid #d7dee8; border-radius: 8px; padding: 8px 12px;
  background: #ffffff; color: #1f2937; font-weight: 700;
}
QPushButton:hover, QToolButton:hover { background: #f8fafc; border-color: #b8c3d1; }
QPushButton#primary { background: #1f2937; color: #fffdf9; border-color: #1f2937; }
QPushButton#alt { background: #0f766e; color: white; border-color: #0f766e; }
QComboBox, QLineEdit, QSpinBox {
  min-height: 30px; padding: 6px 10px; border: 1px solid #d7dee8; border-radius: 8px; background: white;
}
QTextEdit { border: 1px solid #d7dee8; border-radius: 8px; background: white; }
QFrame#topbar, QFrame#panel, QFrame#card, QFrame#actionGroup, QFrame#focusCard {
  background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
}
QFrame#actionGroup { background: #f8fafc; }
QFrame#focusCard { background: #111827; border-color: #111827; }
QTableWidget {
  background: #ffffff; border: 0; gridline-color: #e5e7eb;
  selection-background-color: #dbeafe; alternate-background-color: #f8fafc;
  font-size: 13px;
}
QHeaderView::section {
  background: #f1f5f9; color: #475569; padding: 9px 8px; border: 0;
  font-weight: 800; font-size: 13px;
}
QProgressBar {
  border: 0; border-radius: 5px; background: #e5e7eb; height: 8px; text-align: center;
}
QProgressBar::chunk { border-radius: 5px; background: #0f766e; }
QMenu { background: #ffffff; border: 1px solid #d7dee8; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 8px 18px; border-radius: 6px; }
QMenu::item:selected { background: #eaf4f1; color: #0f766e; }
"""


def ordered_tasks(tasks: list[Task]) -> list[tuple[Task, int]]:
    task_map = {task.id: {"task": task, "children": []} for task in tasks}
    roots = []
    for task in tasks:
        if task.parentId and task.parentId in task_map:
            task_map[task.parentId]["children"].append(task)
        else:
            roots.append(task)
    output: list[tuple[Task, int]] = []

    def walk(item: Task, depth: int) -> None:
        output.append((item, depth))
        for child in sorted(task_map[item.id]["children"], key=lambda value: value.startDate):
            walk(child, depth + 1)

    for task in sorted(roots, key=lambda value: value.startDate):
        walk(task, 0)
    return output


class ProjectDialog(QDialog):
    def __init__(self, project: Project | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("项目设置" if project else "新增项目")
        self.name = QLineEdit(project.name if project else "")
        self.deadline = QLineEdit(project.deadline if project else today())
        self.summary = QTextEdit(project.summary if project else "")
        self.top_risk = QTextEdit(project.topRisk if project else "")
        self.next_step = QTextEdit(project.nextStep if project else "")
        for text in [self.summary, self.top_risk, self.next_step]:
            text.setFixedHeight(76)

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

    def values(self) -> dict:
        return {
            "name": self.name.text().strip() or "未命名项目",
            "deadline": self.deadline.text().strip() or today(),
            "summary": self.summary.toPlainText().strip(),
            "topRisk": self.top_risk.toPlainText().strip(),
            "nextStep": self.next_step.toPlainText().strip(),
        }


class TaskDialog(QDialog):
    def __init__(self, project: Project, task: Task | None = None, selected_date: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑任务" if task else "新增任务")
        self.parent_task = QComboBox()
        self.parent_task.addItem("无父任务", "")
        for item in project.tasks:
            if not task or item.id != task.id:
                self.parent_task.addItem(item.title, item.id)
        self.risk = QComboBox()
        self.risk.addItems(["H", "M", "L"])
        self.title = QLineEdit(task.title if task else "")
        self.responsible = QLineEdit(task.responsible if task else "")
        self.start = QLineEdit(task.startDate if task else (selected_date or today()))
        self.duration = QSpinBox()
        self.duration.setRange(1, 999)
        self.duration.setValue(task.duration if task else 3)
        self.status = QComboBox()
        self.status.addItems(["Open", "Ongoing", "Closed"])
        self.completed = QLineEdit(task.completedDate if task else "")
        self.note = QTextEdit(task.note if task else "")
        self.note.setFixedHeight(76)
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
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        return {
            "parentId": self.parent_task.currentData() or None,
            "risk": self.risk.currentText(),
            "title": self.title.text().strip() or "未命名任务",
            "responsible": self.responsible.text().strip(),
            "startDate": self.start.text().strip() or today(),
            "duration": self.duration.value(),
            "status": self.status.currentText(),
            "completedDate": self.completed.text().strip(),
            "note": self.note.toPlainText().strip(),
            "plannedProgress": self.planned.value(),
            "actualProgress": self.actual.value(),
        }


class DailyDialog(QDialog):
    def __init__(self, project: Project, log: DailyLog | None = None, selected_date: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑日报" if log else "新增日报")
        self.task = QComboBox()
        for item in project.tasks:
            self.task.addItem(item.title, item.id)
        self.date = QLineEdit(log.date if log else (selected_date or today()))
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
        self.delay_reason.setFixedHeight(64)
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
            "date": self.date.text().strip() or today(),
            "responsible": self.responsible.text().strip(),
            "planText": self.plan_text.toPlainText().strip(),
            "actualText": self.actual_text.toPlainText().strip(),
            "plannedProgress": self.planned.value(),
            "actualProgress": self.actual.value(),
            "result": self.result.currentText(),
            "delayReason": self.delay_reason.toPlainText().strip(),
        }


class GanttTaskInfoWidget(QWidget):
    def __init__(self, owner: "GanttChartWidget") -> None:
        super().__init__(owner)
        self.owner = owner
        self.setMouseTracking(True)
        self.setFixedWidth(owner.left_width)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    def paintEvent(self, event) -> None:
        owner = self.owner
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        vy = owner.verticalScrollBar().value()
        painter.fillRect(rect, QColor("#ffffff"))
        painter.fillRect(QRectF(0, 0, rect.width(), owner.header_height), QColor("#f1f5f9"))
        headers = [("风险", 16, 46), ("任务", 58, 166), ("负责人", 226, 78), ("状态", 306, 68), ("实际", 374, 58)]
        for label, x, w in headers:
            owner.draw_elided_text(painter, QRectF(x, 0, w, owner.header_height), label, Qt.AlignVCenter | Qt.AlignLeft, "#374151", True)
        for row, (task, depth) in enumerate(owner.rows):
            y = owner.header_height + row * owner.row_height - vy
            if y + owner.row_height < owner.header_height or y > rect.height():
                continue
            selected = task.id == owner.selected_task_id
            painter.fillRect(QRectF(0, y, rect.width(), owner.row_height), QColor("#eaf4f1") if selected else QColor("#ffffff" if row % 2 == 0 else "#f8fafc"))
            painter.setPen(QColor("#e5e7eb"))
            painter.drawLine(0, int(y + owner.row_height - 1), rect.width(), int(y + owner.row_height - 1))
            self._paint_task_info(painter, task, depth, y)
        painter.setPen(QColor("#e5e7eb"))
        painter.drawLine(0, owner.header_height - 1, rect.width(), owner.header_height - 1)
        painter.drawLine(rect.width() - 1, 0, rect.width() - 1, rect.height())

    def _paint_task_info(self, painter: QPainter, task: Task, depth: int, y: float) -> None:
        owner = self.owner
        entry = latest_entry(task)
        risk_color = QColor(RISK_COLORS.get(task.risk, "#64748b"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(risk_color)
        painter.drawRoundedRect(QRectF(14, y + 13, 30, 22), 11, 11)
        owner.draw_elided_text(painter, QRectF(14, y + 13, 30, 22), task.risk, Qt.AlignCenter, "#ffffff", True)
        title_x = 58 + depth * 16
        title_width = max(48, 166 - depth * 16)
        owner.draw_elided_text(painter, QRectF(title_x, y, title_width, owner.row_height), task.title, Qt.AlignVCenter | Qt.AlignLeft, "#111827", owner.has_children(task))
        owner.draw_elided_text(painter, QRectF(226, y, 78, owner.row_height), task.responsible, Qt.AlignVCenter | Qt.AlignLeft, "#6b7280")
        owner.paint_pill(painter, QRectF(306, y + 13, 58, 22), STATUS_LABELS.get(task.status, task.status), STATUS_COLORS.get(task.status, "#64748b"))
        owner.draw_elided_text(painter, QRectF(374, y, 58, owner.row_height), f"{entry.actualProgress}%", Qt.AlignVCenter | Qt.AlignRight, "#374151")

    def _hit_row(self, point: QPoint) -> int | None:
        return self.owner.hit_row(point.y())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.owner.select_row(self._hit_row(event.pos()))

    def mouseDoubleClickEvent(self, event) -> None:
        self.owner.edit_row(self._hit_row(event.pos()))

    def mouseMoveEvent(self, event) -> None:
        self.setToolTip(self.owner.tooltip_for_row(self._hit_row(event.pos())))


class GanttTimelineWidget(QAbstractScrollArea):
    def __init__(self, owner: "GanttChartWidget") -> None:
        super().__init__(owner)
        self.owner = owner
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.verticalScrollBar().valueChanged.connect(lambda _value: owner.left_view.update())
        self.horizontalScrollBar().valueChanged.connect(lambda _value: self.viewport().update())

    def sizeHint(self) -> QSize:
        return QSize(520, 420)

    def minimumSizeHint(self) -> QSize:
        return QSize(280, 320)

    def update_scrollbars(self) -> None:
        owner = self.owner
        time_width = len(owner.dates) * owner.day_width
        body_height = len(owner.rows) * owner.row_height
        self.horizontalScrollBar().setRange(0, max(0, time_width - max(1, self.viewport().width())))
        self.horizontalScrollBar().setPageStep(max(1, self.viewport().width()))
        self.verticalScrollBar().setRange(0, max(0, body_height - max(1, self.viewport().height() - owner.header_height)))
        self.verticalScrollBar().setPageStep(max(1, self.viewport().height() - owner.header_height))

    def resizeEvent(self, event) -> None:
        self.update_scrollbars()
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        owner = self.owner
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.viewport().rect()
        painter.fillRect(rect, QColor("#ffffff"))
        hx = self.horizontalScrollBar().value()
        vy = self.verticalScrollBar().value()
        self._paint_header(painter, rect, hx)
        self._paint_rows(painter, rect, hx, vy)
        self._paint_today_line(painter, rect, hx)

    def _paint_header(self, painter: QPainter, rect, hx: int) -> None:
        owner = self.owner
        painter.fillRect(QRectF(0, 0, rect.width(), owner.header_height), QColor("#f1f5f9"))
        for index, date_value in enumerate(owner.dates):
            x = index * owner.day_width - hx
            if x + owner.day_width < 0 or x > rect.width():
                continue
            fill = QColor("#e2e8f0") if owner.is_weekend(date_value) else QColor("#f1f5f9")
            painter.fillRect(QRectF(x, 0, owner.day_width, owner.header_height), fill)
            date_text = date_value[5:] if owner.day_width >= 46 else date_value[8:]
            owner.draw_elided_text(painter, QRectF(x, 6, owner.day_width, 20), date_text, Qt.AlignCenter, "#374151", True)
            owner.draw_elided_text(painter, QRectF(x, 29, owner.day_width, 18), owner.weekday_label(date_value), Qt.AlignCenter, "#6b7280")
        painter.setPen(QColor("#e5e7eb"))
        painter.drawLine(0, owner.header_height - 1, rect.width(), owner.header_height - 1)

    def _paint_rows(self, painter: QPainter, rect, hx: int, vy: int) -> None:
        owner = self.owner
        today_value = today()
        for row, (task, _depth) in enumerate(owner.rows):
            y = owner.header_height + row * owner.row_height - vy
            if y + owner.row_height < owner.header_height or y > rect.height():
                continue
            selected = task.id == owner.selected_task_id
            painter.fillRect(QRectF(0, y, rect.width(), owner.row_height), QColor("#eaf4f1") if selected else QColor("#ffffff" if row % 2 == 0 else "#f8fafc"))
            for index, date_value in enumerate(owner.dates):
                x = index * owner.day_width - hx
                if x + owner.day_width < 0 or x > rect.width():
                    continue
                if owner.is_weekend(date_value):
                    painter.fillRect(QRectF(x, y, owner.day_width, owner.row_height), QColor(243, 244, 246, 145))
                if date_value == owner.selected_date:
                    painter.fillRect(QRectF(x, y, owner.day_width, owner.row_height), QColor(219, 234, 254, 120))
            painter.setPen(QColor("#e5e7eb"))
            painter.drawLine(0, int(y + owner.row_height - 1), rect.width(), int(y + owner.row_height - 1))
            self._paint_task_bar(painter, task, y, hx, today_value)

    def _paint_task_bar(self, painter: QPainter, task: Task, y: float, hx: int, today_value: str) -> None:
        owner = self.owner
        if task.startDate not in owner.dates:
            return
        start_index = owner.dates.index(task.startDate)
        x = start_index * owner.day_width - hx + 6
        width = max(14, task.duration * owner.day_width - 12)
        if x + width < 0 or x > self.viewport().width():
            return
        painter.save()
        painter.setClipRect(QRectF(0, owner.header_height, self.viewport().width(), max(0, self.viewport().height() - owner.header_height)).toRect())
        entry = latest_entry(task)
        is_parent = owner.has_children(task)
        overdue = task.status != "Closed" and task_end_date(task) < today_value
        base_color = QColor("#dbeafe")
        fill_color = QColor("#1f2937")
        if task.status == "Closed":
            base_color = QColor("#d1fae5")
            fill_color = QColor("#0f766e")
        elif overdue:
            base_color = QColor("#fee2e2")
            fill_color = QColor("#dc2626")
        bar_h = 22 if is_parent else 18
        bar_y = y + (owner.row_height - bar_h) / 2
        painter.setPen(QPen(QColor("#dc2626") if overdue else QColor("#cbd5e1"), 2 if overdue else 1))
        painter.setBrush(base_color)
        painter.drawRoundedRect(QRectF(x, bar_y, width, bar_h), 8, 8)
        actual_progress = max(0, min(100, int(entry.actualProgress)))
        actual_w = max(0, min(width, width * actual_progress / 100))
        if actual_w > 0:
            painter.setPen(Qt.NoPen)
            painter.setBrush(fill_color)
            painter.drawRoundedRect(QRectF(x, bar_y, actual_w, bar_h), 8, 8)
        if entry.plannedProgress > entry.actualProgress:
            planned_w = max(0, min(width, width * max(0, min(100, int(entry.plannedProgress))) / 100))
            painter.setPen(QPen(QColor("#64748b"), 2, Qt.DashLine))
            painter.drawLine(int(x), int(bar_y + bar_h + 4), int(x + planned_w), int(bar_y + bar_h + 4))
        progress_text = f"{actual_progress}%"
        if width >= max(52, painter.fontMetrics().horizontalAdvance(progress_text) + 12):
            text_color = "#ffffff" if actual_progress > 24 else "#111827"
            owner.draw_elided_text(painter, QRectF(x, bar_y, width, bar_h), progress_text, Qt.AlignCenter, text_color, True)
        painter.restore()

    def _paint_today_line(self, painter: QPainter, rect, hx: int) -> None:
        owner = self.owner
        today_value = today()
        if today_value not in owner.dates:
            return
        x = owner.dates.index(today_value) * owner.day_width - hx + owner.day_width / 2
        if 0 <= x <= rect.width():
            painter.setPen(QPen(QColor("#bf5d35"), 2))
            painter.drawLine(int(x), owner.header_height, int(x), rect.height())
            label_left = max(0.0, float(x - 22))
            label_width = min(44.0, float(rect.width()) - label_left)
            if label_width >= 18:
                owner.draw_elided_text(painter, QRectF(label_left, 0, label_width, 18), "今日", Qt.AlignCenter, "#bf5d35", True)

    def _hit_date(self, point: QPoint) -> str | None:
        owner = self.owner
        index = int((point.x() + self.horizontalScrollBar().value()) / owner.day_width)
        return owner.dates[index] if 0 <= index < len(owner.dates) else None

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        if event.pos().y() >= self.owner.header_height:
            self.owner.select_date(self._hit_date(event.pos()))
        self.owner.select_row(self.owner.hit_row(event.pos().y()))

    def mouseDoubleClickEvent(self, event) -> None:
        self.owner.edit_row(self.owner.hit_row(event.pos().y()))

    def mouseMoveEvent(self, event) -> None:
        self.setToolTip(self.owner.tooltip_for_row(self.owner.hit_row(event.pos().y())))


class GanttChartWidget(QWidget):
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
        self.left_width = 480
        self.header_height = 54
        self.row_height = 48
        self.day_width = 48
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.left_view = GanttTaskInfoWidget(self)
        self.timeline = GanttTimelineWidget(self)
        layout.addWidget(self.left_view)
        layout.addWidget(self.timeline, 1)

    def sizeHint(self) -> QSize:
        return QSize(920, 420)

    def minimumSizeHint(self) -> QSize:
        return QSize(760, 320)

    def horizontalScrollBar(self):
        return self.timeline.horizontalScrollBar()

    def verticalScrollBar(self):
        return self.timeline.verticalScrollBar()

    def viewport(self):
        return self.timeline.viewport()

    def set_project(self, project: Project | None, selected_date: str, selected_task_id: str | None = None) -> None:
        self.project = project
        self.rows = ordered_tasks(project.tasks) if project else []
        self.selected_date = selected_date or today()
        self.selected_task_id = selected_task_id
        self.dates = self._date_range()
        self.refresh_views()

    def set_selected_task(self, task_id: str | None) -> None:
        self.selected_task_id = task_id
        self.refresh_views(update_scrollbars=False)

    def refresh_views(self, update_scrollbars: bool = True) -> None:
        if update_scrollbars:
            self.timeline.update_scrollbars()
        self.left_view.update()
        self.timeline.viewport().update()

    def _date_range(self) -> list[str]:
        if not self.project or not self.project.tasks:
            return [add_days(self.selected_date, index) for index in range(30)]
        starts = [task.startDate for task in self.project.tasks] + [self.selected_date, today()]
        ends = [task_end_date(task) for task in self.project.tasks] + [self.selected_date, today()]
        start = min(starts)
        end = max(ends)
        start = add_days(start, -2)
        end = add_days(end, 6)
        total = min(max(days_between(start, end) + 1, 30), 180)
        return [add_days(start, index) for index in range(total)]

    def draw_elided_text(self, painter: QPainter, rect: QRectF, text: object, flags: Qt.AlignmentFlag | Qt.Alignment, color: str | None = None, bold: bool = False) -> None:
        painter.save()
        painter.setClipRect(rect.toRect())
        if color:
            painter.setPen(QColor(color))
        font = painter.font()
        font.setBold(bold)
        painter.setFont(font)
        text_rect = rect.adjusted(4, 0, -4, 0)
        width = max(0, int(text_rect.width()))
        elided = painter.fontMetrics().elidedText(str(text), Qt.ElideRight, width)
        painter.drawText(text_rect, flags, elided)
        painter.restore()

    def paint_pill(self, painter: QPainter, rect: QRectF, text: str, color: str) -> None:
        qcolor = QColor(color)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(qcolor.red(), qcolor.green(), qcolor.blue(), 32))
        painter.drawRoundedRect(rect, 10, 10)
        self.draw_elided_text(painter, rect, text, Qt.AlignCenter, color, True)

    def hit_row(self, y: int) -> int | None:
        if y < self.header_height:
            return None
        row = int((y - self.header_height + self.verticalScrollBar().value()) / self.row_height)
        return row if 0 <= row < len(self.rows) else None

    def select_row(self, row: int | None) -> None:
        if row is None:
            return
        task = self.rows[row][0]
        self.selected_task_id = task.id
        if self.on_task_selected:
            self.on_task_selected(task.id)
        self.refresh_views(update_scrollbars=False)

    def edit_row(self, row: int | None) -> None:
        if row is not None and self.on_task_edit:
            self.on_task_edit(self.rows[row][0].id)

    def select_date(self, value: str | None) -> None:
        if not value:
            return
        self.selected_date = value
        if self.on_date_selected:
            self.on_date_selected(value)
        self.refresh_views(update_scrollbars=False)

    def tooltip_for_row(self, row: int | None) -> str:
        if row is None:
            return ""
        task = self.rows[row][0]
        entry = latest_entry(task)
        return (
            f"{task.title}\n负责人：{task.responsible}\n开始：{task.startDate}\n结束：{task_end_date(task)}\n"
            f"工期：{task.duration} 天\n计划：{entry.plannedProgress}%\n实际：{entry.actualProgress}%\n"
            f"状态：{STATUS_LABELS.get(task.status, task.status)}\n备注：{task.note}"
        )

    def is_weekend(self, value: str) -> bool:
        return date.fromisoformat(value).weekday() >= 5

    def weekday_label(self, value: str) -> str:
        return "一二三四五六日"[date.fromisoformat(value).weekday()]

    def has_children(self, task: Task) -> bool:
        return bool(self.project and any(item.parentId == task.id for item in self.project.tasks))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        QApplication.instance().setFont(QFont("Microsoft YaHei UI", 10))
        self.workspace: Workspace = load_workspace()
        self.selected_task_id: str | None = None
        self.setWindowTitle("Project Desk Local")
        self.resize(1560, 900)
        self.setMinimumSize(1180, 720)
        self._build_ui()
        self.refresh()

    def current_project(self) -> Project | None:
        for project in self.workspace.projects:
            if project.id == self.workspace.selectedProjectId:
                return project
        return self.workspace.projects[0] if self.workspace.projects else None

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(self._build_topbar())
        layout.addLayout(self._build_cards())
        layout.addLayout(self._build_briefs())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.task_table = QTableWidget()
        self._configure_task_table()
        self.gantt = GanttChartWidget()
        self.gantt.on_task_selected = self.select_task_by_id
        self.gantt.on_task_edit = self.edit_task_by_id
        self.gantt.on_date_selected = self.select_date
        self.log_table = QTableWidget()
        self._configure_log_table()
        self.selected_date_label = QLabel()
        self.selected_date_label.setStyleSheet("color:#6b7280;font-weight:700;")

        left_panel = self._panel("任务台账", self.task_table, [("编辑任务", self.edit_task), ("删除任务", self.delete_task)])
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setChildrenCollapsible(False)
        right_splitter.addWidget(self._panel("甘特图", self.gantt))
        right_splitter.addWidget(self._panel("日报记录", self.log_table, [("编辑日报", self.edit_daily), ("删除日报", self.delete_daily)], self.selected_date_label))
        right_splitter.setSizes([560, 220])
        splitter.addWidget(left_panel)
        splitter.addWidget(right_splitter)
        splitter.setSizes([560, 1000])
        layout.addWidget(splitter, 1)
        self.setCentralWidget(root)

    def _build_topbar(self) -> QFrame:
        top = QFrame(objectName="topbar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(22, 16, 22, 16)
        top_layout.setSpacing(14)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        eyebrow = QLabel("Project Desk Local")
        eyebrow.setStyleSheet("color:#2563eb;font-weight:900;font-size:12px;")
        self.title = QLabel()
        self.title.setMinimumWidth(260)
        self.title.setStyleSheet("font-size:25px;font-weight:900;color:#0f172a;")
        self.summary = QLabel()
        self.summary.setMinimumWidth(260)
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color:#64748b;")
        title_box.addWidget(eyebrow)
        title_box.addWidget(self.title)
        title_box.addWidget(self.summary)
        top_layout.addLayout(title_box, 1)

        self.project_select = QComboBox()
        self.project_select.setMinimumWidth(180)
        self.project_select.setMaximumWidth(260)
        self.project_select.currentIndexChanged.connect(self._select_project)
        task_group = self._action_group("任务", [
            ("新增任务", self.add_task, "primary"),
            ("写日报", self.add_daily, "alt"),
        ])
        project_button = QToolButton()
        project_button.setText("项目")
        project_button.setPopupMode(QToolButton.InstantPopup)
        project_menu = QMenu(project_button)
        for text, handler in [
            ("项目设置", self.edit_project),
            ("新增项目", self.add_project),
            ("删除项目", self.delete_project),
        ]:
            action = QAction(text, self)
            action.triggered.connect(handler)
            project_menu.addAction(action)
        project_button.setMenu(project_menu)
        data_button = QToolButton()
        data_button.setText("数据")
        data_button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(data_button)
        for text, handler in [
            ("导入 JSON", self.import_json),
            ("导出 JSON", self.export_json),
            ("导出 CSV", self.export_csv),
            ("导出 Excel", self.export_excel),
            ("数据目录", self.open_data_dir),
        ]:
            action = QAction(text, self)
            action.triggered.connect(handler)
            menu.addAction(action)
        data_button.setMenu(menu)
        picker_box = QVBoxLayout()
        picker_box.setSpacing(4)
        picker_label = QLabel("当前项目")
        picker_label.setStyleSheet("color:#64748b;font-weight:800;font-size:12px;")
        picker_box.addWidget(picker_label)
        picker_box.addWidget(self.project_select)
        top_layout.addLayout(picker_box)
        top_layout.addWidget(task_group)
        top_layout.addWidget(project_button)
        top_layout.addWidget(data_button)
        return top

    def _action_group(self, title: str, actions: list[tuple[str, object, str]]) -> QFrame:
        frame = QFrame(objectName="actionGroup")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        label = QLabel(title)
        label.setStyleSheet("color:#6b7280;font-weight:900;font-size:12px;")
        layout.addWidget(label)
        for text, handler, name in actions:
            button = QPushButton(text)
            if name:
                button.setObjectName(name)
            button.clicked.connect(handler)
            layout.addWidget(button)
        return frame

    def _build_cards(self) -> QGridLayout:
        cards = QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        self.status_card = self._card("项目状态", focus=True)
        self.deadline_card = self._card("Deadline")
        self.actual_card = self._card("实际进度", accent="#0f766e")
        self.planned_card = self._card("计划进度")
        self.overdue_card = self._card("逾期任务")
        for index, card in enumerate([self.status_card, self.deadline_card, self.actual_card, self.planned_card, self.overdue_card]):
            cards.addWidget(card["frame"], 0, index)
        return cards

    def _build_briefs(self) -> QGridLayout:
        briefs = QGridLayout()
        briefs.setHorizontalSpacing(12)
        briefs.setVerticalSpacing(12)
        self.summary_card = self._brief("一句话总结", "#2563eb")
        self.risk_card = self._brief("TOP 风险", "#dc2626")
        self.next_card = self._brief("下一步计划", "#0f766e")
        for index, card in enumerate([self.summary_card, self.risk_card, self.next_card]):
            briefs.addWidget(card["frame"], 0, index)
        return briefs

    def _card(self, label: str, focus: bool = False, accent: str = "#0f172a") -> dict:
        frame = QFrame(objectName="focusCard" if focus else "card")
        frame.setMinimumHeight(104)
        self._add_shadow(frame)
        box = QVBoxLayout(frame)
        box.setContentsMargins(18, 14, 18, 14)
        box.setSpacing(4)
        small = QLabel(label)
        small.setStyleSheet(("color:#cbd5e1;" if focus else "color:#64748b;") + "font-weight:800;")
        value = QLabel("-")
        value.setStyleSheet(("color:#ffffff;" if focus else f"color:{accent};") + "font-size:28px;font-weight:900;")
        note = QLabel("")
        note.setStyleSheet("color:#fbbf24;font-weight:800;" if focus else "color:#64748b;")
        box.addWidget(small)
        box.addWidget(value)
        box.addWidget(note)
        return {"frame": frame, "value": value, "note": note}

    def _brief(self, title: str, accent: str) -> dict:
        frame = QFrame(objectName="card")
        frame.setMinimumHeight(112)
        self._add_shadow(frame)
        box = QVBoxLayout(frame)
        box.setContentsMargins(18, 14, 18, 14)
        box.setSpacing(8)
        head = QLabel(title)
        head.setStyleSheet(f"font-size:15px;font-weight:900;color:#0f172a;border-left:4px solid {accent};padding-left:10px;")
        body = QLabel()
        body.setWordWrap(True)
        body.setStyleSheet("color:#334155;line-height:1.45;")
        box.addWidget(head)
        box.addWidget(body)
        return {"frame": frame, "body": body}

    def _panel(self, title: str, widget: QWidget, actions: list[tuple[str, object]] | None = None, extra: QWidget | None = None) -> QFrame:
        frame = QFrame(objectName="panel")
        self._add_shadow(frame)
        box = QVBoxLayout(frame)
        box.setContentsMargins(14, 12, 14, 14)
        head_row = QHBoxLayout()
        head = QLabel(title)
        head.setStyleSheet("font-size:17px;font-weight:900;")
        head_row.addWidget(head, 1)
        if extra:
            head_row.addWidget(extra)
        for text, handler in actions or []:
            button = QPushButton(text)
            button.clicked.connect(handler)
            head_row.addWidget(button)
        box.addLayout(head_row)
        box.addWidget(widget, 1)
        return frame

    def _add_shadow(self, widget: QWidget) -> None:
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(14)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(15, 23, 42, 22))
        widget.setGraphicsEffect(shadow)

    def _configure_task_table(self) -> None:
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.task_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.task_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.task_table.setTextElideMode(Qt.ElideRight)
        self.task_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.task_table.setMinimumHeight(320)
        self.task_table.setColumnCount(10)
        self.task_table.setHorizontalHeaderLabels(["风险", "任务", "负责人", "开始", "工期", "结束", "状态", "计划", "实际", "备注"])
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.verticalHeader().setDefaultSectionSize(38)
        header = self.task_table.horizontalHeader()
        header.setMinimumSectionSize(58)
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setStretchLastSection(False)
        self.task_table.setColumnWidth(0, 62)
        self.task_table.setColumnWidth(1, 260)
        self.task_table.setColumnWidth(2, 90)
        self.task_table.setColumnWidth(3, 92)
        self.task_table.setColumnWidth(4, 58)
        self.task_table.setColumnWidth(5, 92)
        self.task_table.setColumnWidth(6, 86)
        self.task_table.setColumnWidth(7, 112)
        self.task_table.setColumnWidth(8, 112)
        self.task_table.setColumnWidth(9, 160)
        self.task_table.itemDoubleClicked.connect(lambda _item: self.edit_task())

    def _configure_log_table(self) -> None:
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_table.setTextElideMode(Qt.ElideRight)
        self.log_table.setColumnCount(7)
        self.log_table.setHorizontalHeaderLabels(["日期", "负责人", "任务", "计划", "实际", "结果", "延期原因"])
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.verticalHeader().setDefaultSectionSize(38)
        self.log_table.horizontalHeader().setStretchLastSection(True)
        self.log_table.itemDoubleClicked.connect(lambda _item: self.edit_daily())

    def refresh(self) -> None:
        self.project_select.blockSignals(True)
        self.project_select.clear()
        for project in self.workspace.projects:
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
        overdue_tasks = overdue_count(project)
        self.status_card["value"].setText("注意" if overdue_tasks else "正常")
        self.status_card["note"].setText(f"{overdue_tasks}项逾期" if overdue_tasks else "按计划推进")
        self.deadline_card["value"].setText(project.deadline)
        self.deadline_card["note"].setText("项目最关键的时间约束")
        self.actual_card["value"].setText(f"{actual}%")
        self.planned_card["value"].setText(f"{planned}%")
        self.overdue_card["value"].setText(str(overdue_tasks))
        self.summary_card["body"].setText(project.summary)
        self.risk_card["body"].setText(project.topRisk)
        self.next_card["body"].setText(project.nextStep)
        self.selected_date_label.setText(f"当前日期：{self.workspace.selectedDate}")
        self._render_tasks(project)
        self.gantt.set_project(project, self.workspace.selectedDate, self.selected_task_id)
        self._render_logs(project)

    def _render_tasks(self, project: Project) -> None:
        rows = ordered_tasks(project.tasks)
        self.task_table.setRowCount(len(rows))
        for row, (task, depth) in enumerate(rows):
            entry = latest_entry(task)
            values = [task.risk, f"{'  ' * depth}{task.title}", task.responsible, task.startDate, task.duration, task_end_date(task), task.status, entry.plannedProgress, entry.actualProgress, task.note]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, task.id)
                item.setToolTip(task.note if col == 9 else str(value))
                self.task_table.setItem(row, col, item)
            self.task_table.setCellWidget(row, 0, self._pill(task.risk, RISK_COLORS.get(task.risk, "#64748b")))
            self.task_table.setCellWidget(row, 6, self._pill(STATUS_LABELS.get(task.status, task.status), STATUS_COLORS.get(task.status, "#64748b")))
            self.task_table.setCellWidget(row, 7, self._progress(entry.plannedProgress, "#64748b"))
            self.task_table.setCellWidget(row, 8, self._progress(entry.actualProgress, "#0f766e"))
            self.task_table.setRowHeight(row, 38)
            if task.id == self.selected_task_id:
                self.task_table.selectRow(row)

    def _pill(self, text: str, color: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        q = QColor(color)
        label.setStyleSheet(
            f"QLabel {{ color: {color}; background: rgba({q.red()}, {q.green()}, {q.blue()}, 0.14); "
            "border-radius: 10px; padding: 3px 8px; font-weight: 800; }}"
        )
        return label

    def _progress(self, value: int, color: str) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 5, 0, 5)
        bar = QProgressBar()
        bar.setMinimumWidth(96)
        bar.setFixedHeight(16)
        bar.setRange(0, 100)
        bar.setValue(int(value))
        bar.setFormat(f"{int(value)}%")
        bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; }}")
        layout.addWidget(bar)
        return box

    def _render_logs(self, project: Project) -> None:
        task_names = {task.id: task.title for task in project.tasks}
        self.log_table.setRowCount(len(project.dailyLogs))
        for row, log in enumerate(sorted(project.dailyLogs, key=lambda item: item.date, reverse=True)):
            values = [log.date, log.responsible, task_names.get(log.taskId, ""), log.planText, log.actualText, log.result, log.delayReason]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, log.id)
                item.setToolTip(str(value))
                if log.result == "延期":
                    item.setBackground(QColor("#fee2e2"))
                elif log.date == self.workspace.selectedDate:
                    item.setBackground(QColor("#eaf4f1"))
                self.log_table.setItem(row, col, item)
            self.log_table.setRowHeight(row, 38)

    def _select_project(self) -> None:
        self.workspace.selectedProjectId = self.project_select.currentData()
        self.selected_task_id = None
        save_workspace(self.workspace)
        self.refresh()

    def select_date(self, value: str) -> None:
        self.workspace.selectedDate = value
        save_workspace(self.workspace)
        self.refresh()

    def select_task_by_id(self, task_id: str) -> None:
        self.selected_task_id = task_id
        for row in range(self.task_table.rowCount()):
            item = self.task_table.item(row, 0)
            if item and item.data(Qt.UserRole) == task_id:
                self.task_table.selectRow(row)
                break
        self.gantt.set_selected_task(task_id)

    def edit_task_by_id(self, task_id: str) -> None:
        self.select_task_by_id(task_id)
        self.edit_task()

    def selected_task(self) -> Task | None:
        project = self.current_project()
        row = self.task_table.currentRow()
        if not project or row < 0:
            return None
        item = self.task_table.item(row, 0)
        task_id = item.data(Qt.UserRole) if item else None
        return next((task for task in project.tasks if task.id == task_id), None)

    def selected_log(self) -> DailyLog | None:
        project = self.current_project()
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
        task = add_task_to_project(project, self.workspace.selectedDate, dialog.values())
        self.selected_task_id = task.id
        self.persist()

    def edit_task(self) -> None:
        project = self.current_project()
        task = self.selected_task()
        if not project or not task:
            QMessageBox.information(self, "请选择任务", "请先在任务台账中选中一行。")
            return
        dialog = TaskDialog(project, task, self.workspace.selectedDate, self)
        if dialog.exec() != QDialog.Accepted:
            return
        update_task(task, self.workspace.selectedDate, dialog.values())
        self.selected_task_id = task.id
        self.persist()

    def delete_task(self) -> None:
        project = self.current_project()
        task = self.selected_task()
        if not project or not task:
            QMessageBox.information(self, "请选择任务", "请先在任务台账中选中一行。")
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
        self.persist()

    def _save_log_values(self, log: DailyLog | None, values: dict) -> None:
        project = self.current_project()
        if not project:
            return
        try:
            saved = save_daily_log(self.workspace, project, log, values)
            self.selected_task_id = saved.taskId
        except ValueError as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self.persist()

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
    app.setStyleSheet(QSS)
    window = MainWindow()
    window.show()
    return app.exec()
