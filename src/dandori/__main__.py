from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from dandori.app import run
from dandori.infrastructure.config import resolve_app_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DANDORI local task manager")
    parser.add_argument("--data-dir", help="SQLiteと添付ファイルの保存先")
    parser.add_argument("--tray", action="store_true", help="画面を開かず通知領域で起動")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        paths = resolve_app_paths(args.data_dir)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    application = QApplication(sys.argv[:1])
    application.setApplicationName("DANDORI")
    application.setOrganizationName("DANDORI")
    application.setQuitOnLastWindowClosed(False)
    return run(application, paths.data_dir, start_in_tray=args.tray)


if __name__ == "__main__":
    raise SystemExit(main())
