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
        workspace, _ = normalize_workspace(json.loads(path.read_text(encoding="utf-8-sig"))["workspace"])
        return workspace
    except Exception:
        workspace, _ = normalize_workspace(json.loads(path.read_text(encoding="utf-8-sig")))
        return workspace


def save_workspace(workspace: Workspace) -> None:
    ensure_data_dir()
    path = workspace_path()
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, data_dir() / "backups" / f"workspace-{stamp}.json")
    workspace.version = APP_VERSION
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"version": APP_VERSION, "workspace": to_dict(workspace)}, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
