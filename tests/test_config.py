from pathlib import Path

from dandori.infrastructure.config import AppPaths, resolve_app_paths


def test_app_paths_build_expected_structure(tmp_path):
    paths = AppPaths.from_data_dir(tmp_path / "data")

    paths.ensure_directories()

    assert paths.database_file == (tmp_path / "data" / "tasks.db").resolve()
    assert paths.attachments_dir.is_dir()
    assert paths.migration_backup_dir.is_dir()


def test_explicit_data_dir_has_priority(tmp_path, monkeypatch):
    monkeypatch.setenv("TASK_MANAGER_DATA_DIR", str(tmp_path / "environment"))

    paths = resolve_app_paths(Path(tmp_path / "explicit"))

    assert paths.data_dir == (tmp_path / "explicit").resolve()
