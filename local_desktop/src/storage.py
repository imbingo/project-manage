from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .import_export import normalize_workspace
from .models import APP_VERSION, Workspace, sample_workspace, to_dict


def data_dir() -> Path:
    root = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
    return root / "ProjectDeskLocal"


def workspace_path() -> Path:
    return data_dir() / "workspace.json"


def ensure_data_dir() -> Path:
    path = data_dir()
    path.mkdir(parents=True, exist_ok=True)
    (path / "backups").mkdir(exist_ok=True)
    return path


def load_workspace() -> Workspace:
    ensure_data_dir()
    path = workspace_path()
    if not path.exists():
        workspace = sample_workspace()
        save_workspace(workspace)
        return workspace
    try:
        return _load_workspace_file(path)
    except Exception:
        corrupt_path = data_dir() / f"workspace-corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json"
        shutil.copy2(path, corrupt_path)
        for backup in _backup_files():
            try:
                workspace = _load_workspace_file(backup)
                save_workspace(workspace)
                return workspace
            except Exception:
                continue
        workspace = sample_workspace()
        save_workspace(workspace)
        return workspace


def _load_workspace_file(path: Path) -> Workspace:
    try:
        workspace, _ = normalize_workspace(json.loads(path.read_text(encoding="utf-8-sig"))["workspace"])
        return workspace
    except Exception:
        workspace, _ = normalize_workspace(json.loads(path.read_text(encoding="utf-8-sig")))
        return workspace


def _backup_files() -> list[Path]:
    backup_dir = data_dir() / "backups"
    if not backup_dir.exists():
        return []
    return sorted(backup_dir.glob("workspace-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)


def _payload_text(workspace: Workspace) -> str:
    workspace.version = APP_VERSION
    payload = {"version": APP_VERSION, "workspace": to_dict(workspace)}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _prune_backups(keep: int = 50) -> None:
    for old_backup in _backup_files()[keep:]:
        old_backup.unlink(missing_ok=True)


def save_workspace(workspace: Workspace) -> None:
    ensure_data_dir()
    path = workspace_path()
    payload_text = _payload_text(workspace)
    if path.exists() and path.read_text(encoding="utf-8") == payload_text:
        return
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(path, data_dir() / "backups" / f"workspace-{stamp}.json")
    temp = path.with_suffix(".tmp")
    temp.write_text(payload_text, encoding="utf-8")
    temp.replace(path)
    _prune_backups()
