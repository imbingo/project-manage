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
    assert window.gantt.rows
    assert window.gantt.dates
    window.close()
    app.quit()
