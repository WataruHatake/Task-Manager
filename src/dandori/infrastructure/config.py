from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path

APP_DIRECTORY_NAME = "TaskManager"
DEFAULT_WINDOWS_DATA_DIR = Path("D:/TaskManager/Data")


@dataclass(frozen=True)
class AppPaths:
    data_dir: Path
    database_file: Path
    attachments_dir: Path
    migration_backup_dir: Path

    @classmethod
    def from_data_dir(cls, data_dir: Path) -> AppPaths:
        normalized = data_dir.expanduser().resolve()
        return cls(
            data_dir=normalized,
            database_file=normalized / "tasks.db",
            attachments_dir=normalized / "attachments",
            migration_backup_dir=normalized / "migration_backup",
        )

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        self.migration_backup_dir.mkdir(parents=True, exist_ok=True)


def bootstrap_file() -> Path | None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None
    return Path(local_app_data) / APP_DIRECTORY_NAME / "bootstrap.json"


def read_bootstrap_data_dir() -> Path | None:
    path = bootstrap_file()
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    value = data.get("data_dir")
    return Path(value) if isinstance(value, str) and value.strip() else None


def resolve_app_paths(explicit_data_dir: str | Path | None = None) -> AppPaths:
    if explicit_data_dir:
        return AppPaths.from_data_dir(Path(explicit_data_dir))

    environment_dir = os.environ.get("TASK_MANAGER_DATA_DIR") or os.environ.get(
        "DANDORI_DATA_DIR"
    )
    if environment_dir:
        return AppPaths.from_data_dir(Path(environment_dir))

    configured_dir = read_bootstrap_data_dir()
    if configured_dir:
        return AppPaths.from_data_dir(configured_dir)

    if platform.system() == "Windows":
        if not Path("D:/").exists():
            raise RuntimeError(
                "Dドライブを確認できません。タスクデータの保存先を設定してください。"
            )
        return AppPaths.from_data_dir(DEFAULT_WINDOWS_DATA_DIR)

    project_root = Path(__file__).resolve().parents[3]
    return AppPaths.from_data_dir(project_root / ".dandori-data")


def write_bootstrap(data_dir: Path) -> Path:
    path = bootstrap_file()
    if path is None:
        raise RuntimeError("LOCALAPPDATAが設定されていません。")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"data_dir": str(data_dir)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
