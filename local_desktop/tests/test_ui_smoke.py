import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[0]))

pytest.importorskip("PySide6")


def test_main_window_initializes(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from local_desktop.src.app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert window.windowTitle() == "Project Desk Local"
    assert window.project_select.count() >= 1
    assert window.plan.rows
    assert window.plan.dates
    assert len(window.plan.dates) >= 28
    assert window.plan.day_width >= 44
    assert window.plan.left_width >= 420
    assert window.plan.viewport().width() > window.plan.left_width
    assert window.main_stack.currentWidget() is window.task_page
    assert window.context_tabs.count() == 2
    assert window.project_select.minimumWidth() >= 180
    assert window.project_select.maximumWidth() <= 280
    assert window.plan.horizontalScrollBar().maximum() > 0
    for width, height in [(1366, 768), (1600, 900), (1920, 1080)]:
        window.resize(width, height)
        app.processEvents()
        assert window.plan.day_width >= 44
        assert window.plan.horizontalScrollBar().pageStep() >= 1
        assert window.plan.viewport().width() > window.plan.left_width
    window.close()
    app.quit()
