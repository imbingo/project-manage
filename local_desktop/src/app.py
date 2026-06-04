from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .import_export import dump_workspace_json, export_project_excel, export_tasks_csv, load_workspace_json
from .metrics import overdue_count, project_progress, task_end_date
from .models import Workspace
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
QComboBox { padding: 7px 10px; border: 1px solid #d7cfc2; border-radius: 8px; background: white; }
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.workspace: Workspace = load_workspace()
        self.setWindowTitle("Project Desk Local")
        self.resize(1360, 840)
        self._build_ui()
        self.refresh()

    def current_project(self):
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
        for text, handler, name in [
            ("打开数据目录", self.open_data_dir, ""),
            ("导入 JSON", self.import_json, ""),
            ("导出 JSON", self.export_json, ""),
            ("导出 CSV", self.export_csv, ""),
            ("导出 Excel", self.export_excel, "primary"),
        ]:
            button = QPushButton(text)
            if name:
                button.setObjectName(name)
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
        self.task_table.setColumnCount(10)
        self.task_table.setHorizontalHeaderLabels(["风险", "任务", "负责人", "开始", "工期", "结束", "状态", "计划%", "实际%", "实际完成日"])
        self.gantt_table = QTableWidget()
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(7)
        self.log_table.setHorizontalHeaderLabels(["日期", "负责人", "任务", "计划", "实际", "结果", "延期原因"])
        main_grid.addWidget(self._panel("任务台账", self.task_table), 0, 0, 2, 1)
        main_grid.addWidget(self._panel("甘特图", self.gantt_table), 0, 1)
        main_grid.addWidget(self._panel("日报记录", self.log_table), 1, 1)
        main_grid.setColumnStretch(0, 3)
        main_grid.setColumnStretch(1, 2)
        layout.addLayout(main_grid, 1)

        self.setCentralWidget(root)
        self._build_menu()

    def _build_menu(self) -> None:
        backup_action = QAction("另存为备份", self)
        backup_action.triggered.connect(self.export_json)
        self.menuBar().addAction(backup_action)

    def _card(self, label: str):
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

    def _brief(self, title: str):
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

    def _panel(self, title: str, widget: QWidget) -> QFrame:
        frame = QFrame(objectName="panel")
        box = QVBoxLayout(frame)
        head = QLabel(title)
        head.setStyleSheet("font-size:17px;font-weight:900;")
        box.addWidget(head)
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

    def _render_tasks(self, project) -> None:
        self.task_table.setRowCount(len(project.tasks))
        for row, task in enumerate(project.tasks):
            planned = actual = 0
            if task.progressEntries:
                latest = sorted(task.progressEntries, key=lambda item: item.entryDate)[-1]
                planned, actual = latest.plannedProgress, latest.actualProgress
            values = [task.risk, task.title, task.responsible, task.startDate, task.duration, task_end_date(task), task.status, planned, actual, task.completedDate]
            for col, value in enumerate(values):
                self.task_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.task_table.resizeColumnsToContents()

    def _render_gantt(self, project) -> None:
        dates = self._gantt_dates(project)
        self.gantt_table.setColumnCount(4 + len(dates))
        self.gantt_table.setHorizontalHeaderLabels(["任务", "负责人", "风险", "实际%", *[item[5:] for item in dates]])
        self.gantt_table.setRowCount(len(project.tasks))
        for row, task in enumerate(project.tasks):
            actual = sorted(task.progressEntries, key=lambda item: item.entryDate)[-1].actualProgress if task.progressEntries else 0
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

    def _render_logs(self, project) -> None:
        task_names = {task.id: task.title for task in project.tasks}
        self.log_table.setRowCount(len(project.dailyLogs))
        for row, log in enumerate(project.dailyLogs):
            values = [log.date, log.responsible, task_names.get(log.taskId, ""), log.planText, log.actualText, log.result, log.delayReason]
            for col, value in enumerate(values):
                self.log_table.setItem(row, col, QTableWidgetItem(str(value)))
        self.log_table.resizeColumnsToContents()

    def _gantt_dates(self, project) -> list[str]:
        if not project.tasks:
            return []
        start = min(task.startDate for task in project.tasks)
        end = max(task_end_date(task) for task in project.tasks)
        from datetime import date
        total = min(max((date.fromisoformat(end) - date.fromisoformat(start)).days + 1, 14), 60)
        from .metrics import add_days
        return [add_days(start, index) for index in range(total)]

    def _select_project(self) -> None:
        self.workspace.selectedProjectId = self.project_select.currentData()
        save_workspace(self.workspace)
        self.refresh()

    def import_json(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "导入网页版 JSON", "", "JSON Files (*.json)")
        if not file_name:
            return
        try:
            workspace, diagnostics = load_workspace_json(Path(file_name))
            self.workspace = workspace
            save_workspace(self.workspace)
            self.refresh()
            QMessageBox.information(self, "导入完成", "\n".join(diagnostics))
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", str(exc))

    def export_json(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(self, "导出 JSON", "project-desk-workspace.json", "JSON Files (*.json)")
        if file_name:
            dump_workspace_json(self.workspace, Path(file_name))

    def export_csv(self) -> None:
        project = self.current_project()
        file_name, _ = QFileDialog.getSaveFileName(self, "导出任务 CSV", f"{project.name}-tasks.csv", "CSV Files (*.csv)")
        if file_name:
            export_tasks_csv(project, Path(file_name))

    def export_excel(self) -> None:
        project = self.current_project()
        file_name, _ = QFileDialog.getSaveFileName(self, "导出 Excel 项目表", f"{project.name}-project-table.xlsx", "Excel Files (*.xlsx)")
        if file_name:
            export_project_excel(project, Path(file_name))

    def open_data_dir(self) -> None:
        path = data_dir()
        path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(path)])


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    window = MainWindow()
    window.show()
    return app.exec()
