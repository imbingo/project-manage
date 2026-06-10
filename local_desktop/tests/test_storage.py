import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models import APP_VERSION, Project, Workspace
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
    backup_count = len(backups)
    save_workspace(reloaded)
    assert len(list((workspace_path().parent / "backups").glob("workspace-*.json"))) == backup_count


def test_load_workspace_recovers_from_latest_valid_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    workspace = Workspace(projects=[Project(name="可恢复项目")])
    workspace.selectedProjectId = workspace.projects[0].id
    save_workspace(workspace)
    loaded = load_workspace()
    loaded.projects[0].name = "备份版本"
    save_workspace(loaded)
    workspace_path().write_text("{broken", encoding="utf-8")
    recovered = load_workspace()
    assert recovered.projects[0].name == "可恢复项目"
    assert list(workspace_path().parent.glob("workspace-corrupt-*.json"))
    assert recovered.version == APP_VERSION


def test_backup_rotation_keeps_recent_50(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    workspace = Workspace(projects=[Project(name="项目 0")])
    workspace.selectedProjectId = workspace.projects[0].id
    save_workspace(workspace)
    for index in range(60):
        workspace.projects[0].name = f"项目 {index + 1}"
        save_workspace(workspace)
    backups = list((workspace_path().parent / "backups").glob("workspace-*.json"))
    assert len(backups) == 50
