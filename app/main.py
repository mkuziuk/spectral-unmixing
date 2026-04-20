#!/usr/bin/env python3
"""
Spectral Unmixing Application — entry point.

Usage:
    python -m app.main
    # or
    python app/main.py

Default launch mode starts the PySide6 UI.
Use ``--legacy-tk`` (or ``SPECTRAL_UNMIXING_LEGACY_TK=1``)
to launch the legacy tkinter UI for rollback.
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


LEGACY_TK_ENV_VAR = "SPECTRAL_UNMIXING_LEGACY_TK"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args for UI mode selection."""
    parser = argparse.ArgumentParser(description="Launch Spectral Unmixing desktop app")
    parser.add_argument(
        "--legacy-tk",
        action="store_true",
        help="Launch legacy tkinter UI instead of default PySide6 UI",
    )
    return parser.parse_args(argv)


def _is_truthy_env(value: str | None) -> bool:
    """Return True when an env var should enable legacy mode."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def should_use_legacy_tk(
    args: argparse.Namespace,
    environ: dict[str, str] | None = None,
) -> bool:
    """Resolve launch mode from CLI args + environment."""
    env = os.environ if environ is None else environ
    return bool(args.legacy_tk) or _is_truthy_env(env.get(LEGACY_TK_ENV_VAR))


def run_legacy_tk() -> int:
    """Launch the rollback tkinter UI path.

    DEPRECATED: The legacy tkinter UI is retained only as a compatibility shim.
    The default PySide6 UI (``app.gui_qt``) should be used for all new deployments.
    This path may be removed in a future release.
    """
    import warnings
    warnings.warn(
        "Legacy tkinter UI (--legacy-tk) is deprecated. "
        "Migrate to the default PySide6 UI.",
        DeprecationWarning,
        stacklevel=2,
    )
    from app.gui.app_window import SpectralUnmixingApp

    app = SpectralUnmixingApp()
    app.mainloop()
    return 0


def _build_missing_pyside6_message() -> str:
    return (
        "PySide6 is required for the default Qt UI but is not installed.\n"
        "Install it (for example: `pip install PySide6`) or launch rollback mode via\n"
        f"`--legacy-tk` or {LEGACY_TK_ENV_VAR}=1."
    )


def run_qt() -> int:
    """Launch the default PySide6 UI path."""
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


def main(argv: list[str] | None = None, environ: dict[str, str] | None = None) -> int:
    args = parse_args(argv)

    if should_use_legacy_tk(args, environ=environ):
        return run_legacy_tk()
    return run_qt()


if __name__ == "__main__":
    raise SystemExit(main())
