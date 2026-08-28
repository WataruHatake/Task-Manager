from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from dandori.app import run
from dandori.infrastructure.config import resolve_app_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local task manager")
    parser.add_argument("--data-dir", help="SQLiteと添付ファイルの保存先")
    parser.add_argument("--tray", action="store_true", help="画面を開かず通知領域で起動")
    parser.add_argument(
        "--mode",
        choices=("full", "tasks", "add", "tray"),
        default="full",
        help="起動時に開く画面",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        paths = resolve_app_paths(args.data_dir)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    application = QApplication(sys.argv[:1])
    application.setApplicationName("Task Manager")
    application.setOrganizationName("TaskManager")
    application.setQuitOnLastWindowClosed(False)
    start_mode = "tray" if args.tray else args.mode
    return run(application, paths.data_dir, start_mode=start_mode)


if __name__ == "__main__":
    raise SystemExit(main())
