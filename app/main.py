#!/usr/bin/env python3
"""
Spectral Unmixing Application — entry point.

Usage:
    python -m app.main
    # or
    python app/main.py

This release launches the PySide6 interface only.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import sys

# Ensure the project root is on the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args for application launch."""
    parser = argparse.ArgumentParser(description="Launch Spectral Unmixing desktop app")
    return parser.parse_args(argv)


def _build_missing_pyside6_message() -> str:
    return (
        "PySide6 is required to launch Spectral Unmixing.\n"
        "Install the project dependencies with `pip install -r requirements.txt`\n"
        "or install PySide6 directly with `pip install PySide6`."
    )


def run_qt() -> int:
    """Launch the PySide6 UI."""
    if importlib.util.find_spec("PySide6") is None:
        print(_build_missing_pyside6_message(), file=sys.stderr)
        return 2

    try:
        QApplication = importlib.import_module("PySide6.QtWidgets").QApplication
    except Exception:
        print(_build_missing_pyside6_message(), file=sys.stderr)
        return 2

    from app.gui_qt.main_window import SpectralUnmixingMainWindow

    qt_app = QApplication.instance()
    if qt_app is None:
        qt_app = QApplication(sys.argv or ["spectral-unmixing"])

    main_window = SpectralUnmixingMainWindow()
    main_window._impl.show()
    return int(qt_app.exec())


def main(argv: list[str] | None = None) -> int:
    parse_args(argv)
    return run_qt()


if __name__ == "__main__":
    raise SystemExit(main())
