import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[0]))

pytest.importorskip("PySide6")


class FakeDialog:
    queue = []

    def __init__(self, *args, **kwargs):
        self.item = self.queue.pop(0)

    def exec(self):
        from PySide6.QtWidgets import QDialog

        return QDialog.Accepted

    def values(self):
        return dict(self.item)


def app_window(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from local_desktop.src.app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    return app, window


def test_main_window_project_task_daily_workflow(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    import local_desktop.src.app as app_module

    app, window = app_window(tmp_path, monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

    FakeDialog.queue = [
        {"name": "项目 B", "deadline": "2026-06-30", "summary": "总结", "topRisk": "风险", "nextStep": "计划"},
        {"name": "项目 B2", "deadline": "2026-07-01", "summary": "总结2", "topRisk": "风险2", "nextStep": "计划2"},
    ]
    monkeypatch.setattr(app_module, "ProjectDialog", FakeDialog)
    window.add_project()
    project = window.current_project()
    assert project.name == "项目 B"
    window.edit_project()
    assert project.name == "项目 B2"

    FakeDialog.queue = [
        {
            "parentId": None,
            "risk": "H",
            "title": "任务 A",
            "responsible": "张三",
            "startDate": "2026-05-06",
            "duration": 4,
            "status": "Open",
            "completedDate": "",
            "note": "备注",
            "plannedProgress": 25,
            "actualProgress": 10,
        },
        {
            "parentId": None,
            "risk": "M",
            "title": "任务 A2",
            "responsible": "李四",
            "startDate": "2026-05-06",
            "duration": 5,
            "status": "Ongoing",
            "completedDate": "",
            "note": "更新",
            "plannedProgress": 50,
            "actualProgress": 30,
        },
    ]
    monkeypatch.setattr(app_module, "TaskDialog", FakeDialog)
    window.add_task()
    assert len(project.tasks) == 1
    assert len(window.plan.rows) == 1
    window.select_task_by_id(project.tasks[0].id)
    window.edit_task()
    assert project.tasks[0].title == "任务 A2"
    assert project.tasks[0].duration == 5

    FakeDialog.queue = [
        {
            "taskId": project.tasks[0].id,
            "date": "2026-05-08",
            "responsible": "李四",
            "planText": "计划",
            "actualText": "实际",
            "plannedProgress": 100,
            "actualProgress": 100,
            "result": "完成",
            "delayReason": "",
        },
        {
            "taskId": project.tasks[0].id,
            "date": "2026-05-09",
            "responsible": "李四",
            "planText": "计划2",
            "actualText": "实际2",
            "plannedProgress": 80,
            "actualProgress": 60,
            "result": "部分完成",
            "delayReason": "",
        },
    ]
    monkeypatch.setattr(app_module, "DailyDialog", FakeDialog)
    window.add_daily()
    assert len(project.dailyLogs) == 1
    assert project.tasks[0].status == "Closed"
    assert project.tasks[0].completedDate == "2026-05-08"
    window.log_table.selectRow(0)
    window.edit_daily()
    assert project.dailyLogs[0].date == "2026-05-09"
    assert project.tasks[0].status == "Ongoing"

    window.log_table.selectRow(0)
    window.delete_daily()
    assert project.dailyLogs == []
    window.select_task_by_id(project.tasks[0].id)
    window.delete_task()
    assert project.tasks == []
    window.delete_project()
    assert all(item.name != "项目 B2" for item in window.workspace.projects)
    window.close()
    app.quit()


def test_main_window_import_export_file_actions(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    import local_desktop.src.app as app_module

    app, window = app_window(tmp_path, monkeypatch)
    import_path = tmp_path / "import.json"
    import_path.write_text(
        """
        {
          "projects": [
            {
              "id": "p-in",
              "name": "导入项目",
              "deadline": "2026-08-01",
              "tasks": [
                {"id": "t-in", "title": "导入任务", "startDate": "2026-07-01", "duration": 3}
              ],
              "dailyLogs": []
            }
          ],
          "selectedProjectId": "p-in",
          "selectedDate": "2026-07-01"
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(import_path), "JSON Files (*.json)"))
    monkeypatch.setattr(app_module.MainWindow, "_confirm_import_mode", lambda self, workspace, diagnostics: "merge")
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    window.import_json()
    assert any(project.name == "导入项目" for project in window.workspace.projects)

    json_path = tmp_path / "out.json"
    csv_path = tmp_path / "out.csv"
    xlsx_path = tmp_path / "out.xlsx"
    save_paths = iter([
        (str(json_path), "JSON Files (*.json)"),
        (str(csv_path), "CSV Files (*.csv)"),
        (str(xlsx_path), "Excel Files (*.xlsx)"),
    ])
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: next(save_paths))
    window.export_json()
    window.export_csv()
    window.export_excel()
    assert json_path.exists() and "导入项目" in json_path.read_text(encoding="utf-8")
    assert csv_path.exists() and csv_path.stat().st_size > 0
    assert xlsx_path.exists() and xlsx_path.stat().st_size > 1000
    window.close()
    app.quit()
