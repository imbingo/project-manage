from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .import_export import dump_workspace_json, export_project_excel, export_tasks_csv, load_workspace_json
from .metrics import add_days, overdue_count, project_progress, task_end_date
from .models import DailyLog, ProgressEntry, Project, Task, Workspace, today
from .storage import data_dir, load_workspace, save_workspace


QSS = """
QMainWindow { background: #f6f2ea; }
QLabel { color: #1f2937; font-family: Microsoft YaHei; }
QPushButton {
  border: 1px solid #d7cfc2; border-radius: 8px; padding: 8px 12px;
  background: #fffdf9; color: #1f2937; font-weight: 700;
}
QPushButton#primary { background: #1f2937; color: #fffdf9; border-color: #1f2937; }
QPushButton#alt { background: #0f766e; color: white; border-color: #0f766e; }
QComboBox, QLineEdit, QSpinBox {
  padding: 7px 10px; border: 1px solid #d7cfc2; border-radius: 8px; background: white;
}
QTextEdit { border: 1px solid #d7cfc2; border-radius: 8px; background: white; }
QFrame#panel, QFrame#card {
  background: #fffdf9; border: 1px solid #e4dccf; border-radius: 10px;
}
QTableWidget {
  background: #fffdf9; border: 1px solid #e4dccf; gridline-color: #e5e7eb;
  selection-background-color: #dbeafe; alternate-background-color: #fbf7ef;
}
QHeaderView::section {
  background: #ece5d8; color: #374151; padding: 8px; border: 0;
  font-weight: 700;
}
"""


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
            text.setFixedHeight(70)

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
        self.note.setFixedHeight(70)
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
        self.plan_text.setFixedHeight(70)
        self.actual_text.setFixedHeight(70)
        self.planned = QSpinBox()
        self.planned.setRange(0, 100)
        self.planned.setValue(log.plannedProgress if log else 0)
        self.actual = QSpinBox()
        self.actual.setRange(0, 100)
        self.actual.setValue(log.actualProgress if log else 0)
        self.result = QComboBox()
        self.result.addItems(["完成", "部分完成", "延期"])
        self.delay_reason = QTextEdit(log.delayReason if log else "")
        self.delay_reason.setFixedHeight(60)
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.workspace: Workspace = load_workspace()
        self.setWindowTitle("Project Desk Local")
        self.resize(1480, 860)
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
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        top = QFrame(objectName="panel")
        top_layout = QHBoxLayout(top)
        title_box = QVBoxLayout()
        self.eyebrow = QLabel("Project Desk Local")
        self.eyebrow.setStyleSheet("color:#0f766e;font-weight:800;")
        self.title = QLabel()
        self.title.setStyleSheet("font-size:26px;font-weight:900;")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color:#6b7280;")
        title_box.addWidget(self.eyebrow)
        title_box.addWidget(self.title)
        title_box.addWidget(self.summary)
        top_layout.addLayout(title_box, 1)

        self.project_select = QComboBox()
        self.project_select.currentIndexChanged.connect(self._select_project)
        top_layout.addWidget(self.project_select)
        actions = [
            ("项目设置", self.edit_project, ""),
            ("新增项目", self.add_project, ""),
            ("删除项目", self.delete_project, ""),
            ("新增任务", self.add_task, "primary"),
            ("写日报", self.add_daily, "alt"),
            ("数据目录", self.open_data_dir, ""),
            ("导入 JSON", self.import_json, ""),
            ("导出 JSON", self.export_json, ""),
            ("导出 CSV", self.export_csv, ""),
            ("导出 Excel", self.export_excel, "primary"),
        ]
        for text, handler, name in actions:
            button = QPushButton(text)
            if name:
                button.setObjectName(name)
            if text == "数据目录":
                button.setToolTip("打开本地 workspace.json 和自动备份所在文件夹。")
            button.clicked.connect(handler)
            top_layout.addWidget(button)
        layout.addWidget(top)

        cards = QGridLayout()
        self.deadline_card = self._card("项目截止日")
        self.actual_card = self._card("项目实际进度")
        self.planned_card = self._card("计划应达进度")
        self.overdue_card = self._card("逾期任务")
        for index, card in enumerate([self.deadline_card, self.actual_card, self.planned_card, self.overdue_card]):
            cards.addWidget(card["frame"], 0, index)
        layout.addLayout(cards)

        briefs = QGridLayout()
        self.summary_card = self._brief("一句话总结")
        self.risk_card = self._brief("TOP 风险")
        self.next_card = self._brief("下一步计划")
        for index, card in enumerate([self.summary_card, self.risk_card, self.next_card]):
            briefs.addWidget(card["frame"], 0, index)
        layout.addLayout(briefs)

        main_grid = QGridLayout()
        self.task_table = QTableWidget()
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.task_table.setColumnCount(10)
        self.task_table.setHorizontalHeaderLabels(["风险", "任务", "负责人", "开始", "工期", "结束", "状态", "计划%", "实际%", "实际完成日"])
        self.gantt_table = QTableWidget()
        self.log_table = QTableWidget()
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.setColumnCount(7)
        self.log_table.setHorizontalHeaderLabels(["日期", "负责人", "任务", "计划", "实际", "结果", "延期原因"])
        main_grid.addWidget(self._panel("任务台账", self.task_table, [("编辑任务", self.edit_task), ("删除任务", self.delete_task)]), 0, 0, 2, 1)
        main_grid.addWidget(self._panel("甘特图", self.gantt_table), 0, 1)
        main_grid.addWidget(self._panel("日报记录", self.log_table, [("编辑日报", self.edit_daily), ("删除日报", self.delete_daily)]), 1, 1)
        main_grid.setColumnStretch(0, 3)
        main_grid.setColumnStretch(1, 2)
        layout.addLayout(main_grid, 1)
        self.setCentralWidget(root)

    def _card(self, label: str) -> dict:
        frame = QFrame(objectName="card")
        box = QVBoxLayout(frame)
        small = QLabel(label)
        small.setStyleSheet("color:#6b7280;font-weight:700;")
        value = QLabel("-")
        value.setStyleSheet("font-size:24px;font-weight:900;")
        note = QLabel("")
        note.setStyleSheet("color:#6b7280;")
        box.addWidget(small)
        box.addWidget(value)
        box.addWidget(note)
        return {"frame": frame, "value": value, "note": note}

    def _brief(self, title: str) -> dict:
        frame = QFrame(objectName="card")
        box = QVBoxLayout(frame)
        head = QLabel(title)
        head.setStyleSheet("font-size:15px;font-weight:900;")
        body = QLabel()
        body.setWordWrap(True)
        body.setStyleSheet("color:#374151;line-height:1.5;")
        box.addWidget(head)
        box.addWidget(body)
        return {"frame": frame, "body": body}

    def _panel(self, title: str, widget: QWidget, actions: list[tuple[str, object]] | None = None) -> QFrame:
        frame = QFrame(objectName="panel")
        box = QVBoxLayout(frame)
        head_row = QHBoxLayout()
        head = QLabel(title)
        head.setStyleSheet("font-size:17px;font-weight:900;")
        head_row.addWidget(head, 1)
        for text, handler in actions or []:
            button = QPushButton(text)
            button.clicked.connect(handler)
            head_row.addWidget(button)
        box.addLayout(head_row)
        box.addWidget(widget)
        return frame

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
        self.deadline_card["value"].setText(project.deadline)
        self.deadline_card["note"].setText("项目最关键的时间约束")
        self.actual_card["value"].setText(f"{actual}%")
        self.planned_card["value"].setText(f"{planned}%")
        self.overdue_card["value"].setText(str(overdue_count(project)))
        self.summary_card["body"].setText(project.summary)
        self.risk_card["body"].setText(project.topRisk)
        self.next_card["body"].setText(project.nextStep)
        self._render_tasks(project)
        self._render_gantt(project)
        self._render_logs(project)

    def _render_tasks(self, project: Project) -> None:
        self.task_table.setRowCount(len(project.tasks))
        for row, task in enumerate(project.tasks):
            entry = latest_entry(task)
            values = [task.risk, task.title, task.responsible, task.startDate, task.duration, task_end_date(task), task.status, entry.plannedProgress, entry.actualProgress, task.completedDate]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, task.id)
                self.task_table.setItem(row, col, item)
        self.task_table.resizeColumnsToContents()

    def _render_gantt(self, project: Project) -> None:
        dates = self._gantt_dates(project)
        self.gantt_table.setColumnCount(4 + len(dates))
        self.gantt_table.setHorizontalHeaderLabels(["任务", "负责人", "风险", "实际%", *[item[5:] for item in dates]])
        self.gantt_table.setRowCount(len(project.tasks))
        for row, task in enumerate(project.tasks):
            actual = latest_entry(task).actualProgress
            for col, value in enumerate([task.title, task.responsible, task.risk, f"{actual}%"]):
                self.gantt_table.setItem(row, col, QTableWidgetItem(str(value)))
            end = task_end_date(task)
            for offset, date_value in enumerate(dates, start=4):
                item = QTableWidgetItem("■" if task.startDate <= date_value <= end else "")
                if task.startDate <= date_value <= end:
                    item.setBackground(QColor("#86efac" if task.completedDate and date_value <= task.completedDate else "#bfdbfe"))
                    item.setTextAlignment(Qt.AlignCenter)
                self.gantt_table.setItem(row, offset, item)
        self.gantt_table.resizeColumnsToContents()

    def _render_logs(self, project: Project) -> None:
        task_names = {task.id: task.title for task in project.tasks}
        self.log_table.setRowCount(len(project.dailyLogs))
        for row, log in enumerate(project.dailyLogs):
            values = [log.date, log.responsible, task_names.get(log.taskId, ""), log.planText, log.actualText, log.result, log.delayReason]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, log.id)
                self.log_table.setItem(row, col, item)
        self.log_table.resizeColumnsToContents()

    def _gantt_dates(self, project: Project) -> list[str]:
        if not project.tasks:
            return []
        start = min(task.startDate for task in project.tasks)
        end = max(task_end_date(task) for task in project.tasks)
        from datetime import date
        total = min(max((date.fromisoformat(end) - date.fromisoformat(start)).days + 1, 14), 60)
        return [add_days(start, index) for index in range(total)]

    def _select_project(self) -> None:
        self.workspace.selectedProjectId = self.project_select.currentData()
        save_workspace(self.workspace)
        self.refresh()

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
        values = dialog.values()
        project = Project(**values)
        self.workspace.projects.append(project)
        self.workspace.selectedProjectId = project.id
        self.persist()

    def edit_project(self) -> None:
        project = self.current_project()
        if not project:
            return
        dialog = ProjectDialog(project, self)
        if dialog.exec() != QDialog.Accepted:
            return
        for key, value in dialog.values().items():
            setattr(project, key, value)
        self.persist()

    def delete_project(self) -> None:
        project = self.current_project()
        if not project:
            return
        if len(self.workspace.projects) <= 1:
            QMessageBox.warning(self, "不能删除", "至少需要保留一个项目。")
            return
        ok = QMessageBox.question(self, "确认删除", f"删除项目「{project.name}」会同时删除任务和日报，是否继续？")
        if ok != QMessageBox.Yes:
            return
        self.workspace.projects = [item for item in self.workspace.projects if item.id != project.id]
        self.workspace.selectedProjectId = self.workspace.projects[0].id
        self.persist()

    def add_task(self) -> None:
        project = self.current_project()
        if not project:
            return
        dialog = TaskDialog(project, selected_date=self.workspace.selectedDate, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        task = Task(
            parentId=values["parentId"],
            risk=values["risk"],
            title=values["title"],
            responsible=values["responsible"],
            startDate=values["startDate"],
            duration=values["duration"],
            status=values["status"],
            completedDate=values["completedDate"],
            note=values["note"],
        )
        upsert_progress(task, self.workspace.selectedDate, values["plannedProgress"], values["actualProgress"])
        project.tasks.append(task)
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
        values = dialog.values()
        for key in ["parentId", "risk", "title", "responsible", "startDate", "duration", "status", "completedDate", "note"]:
            setattr(task, key, values[key])
        upsert_progress(task, self.workspace.selectedDate, values["plannedProgress"], values["actualProgress"])
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
        ids = {task.id}
        changed = True
        while changed:
            changed = False
            for item in project.tasks:
                if item.parentId in ids and item.id not in ids:
                    ids.add(item.id)
                    changed = True
        project.tasks = [item for item in project.tasks if item.id not in ids]
        project.dailyLogs = [log for log in project.dailyLogs if log.taskId not in ids]
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
        self._save_log_values(DailyLog(), dialog.values())

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
        project.dailyLogs = [item for item in project.dailyLogs if item.id != log.id]
        task = next((item for item in project.tasks if item.id == log.taskId), None)
        if task:
            task.progressEntries = [entry for entry in task.progressEntries if entry.entryDate != log.date]
        self.persist()

    def _save_log_values(self, log: DailyLog, values: dict) -> None:
        project = self.current_project()
        if not project:
            return
        if values["result"] == "延期" and not values["delayReason"]:
            QMessageBox.warning(self, "缺少延期原因", "日报结果为延期时，必须填写延期原因。")
            return
        is_new = log.id not in {item.id for item in project.dailyLogs}
        old_task_id = log.taskId
        old_date = log.date
        for key, value in values.items():
            setattr(log, key, value)
        if is_new:
            project.dailyLogs.append(log)
        old_task = next((item for item in project.tasks if item.id == old_task_id), None)
        if old_task and (old_task_id != log.taskId or old_date != log.date):
            old_task.progressEntries = [entry for entry in old_task.progressEntries if entry.entryDate != old_date]
        task = next((item for item in project.tasks if item.id == log.taskId), None)
        if task:
            upsert_progress(task, log.date, log.plannedProgress, log.actualProgress)
            task.status = "Closed" if log.actualProgress == 100 else "Ongoing" if log.actualProgress > 0 else "Open"
            task.completedDate = log.date if log.actualProgress == 100 else ""
        self.workspace.selectedDate = log.date
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
                self._merge_workspace(workspace)
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

    def _merge_workspace(self, incoming: Workspace) -> None:
        first_new_project_id = None
        for project in incoming.projects:
            old_project_id = project.id
            project.id = str(uuid4())
            if first_new_project_id is None:
                first_new_project_id = project.id
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
            self.workspace.projects.append(project)
            if incoming.selectedProjectId == old_project_id:
                first_new_project_id = project.id
        if first_new_project_id:
            self.workspace.selectedProjectId = first_new_project_id
        self.workspace.selectedDate = incoming.selectedDate or self.workspace.selectedDate

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
    app.setStyleSheet(QSS)
    window = MainWindow()
    window.show()
    return app.exec()
