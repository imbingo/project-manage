import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models import Project, Workspace
from src.storage import load_workspace, save_workspace, workspace_path


def test_save_load_workspace_and_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    workspace = Workspace(projects=[Project(name="项目 A")])
    workspace.selectedProjectId = workspace.projects[0].id
    save_workspace(workspace)
    loaded = load_workspace()
    assert loaded.projects[0].name == "项目 A"
    loaded.projects[0].name = "项目 B"
    save_workspace(loaded)
    reloaded = load_workspace()
    assert reloaded.projects[0].name == "项目 B"
    backups = list((workspace_path().parent / "backups").glob("workspace-*.json"))
    assert backups
