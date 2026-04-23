"""Tests for QT-021 entrypoint routing for the Qt-only launcher."""

from __future__ import annotations

import pytest
import sys
import types
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_parse_args_accepts_no_flags():
    from app.main import parse_args

    args = parse_args([])
    assert vars(args) == {}


def test_parse_args_rejects_removed_legacy_flag():
    from app.main import parse_args

    with pytest.raises(SystemExit) as excinfo:
        parse_args(["--legacy-tk"])

    assert excinfo.value.code == 2


def test_main_default_routes_to_qt_runner():
    from app import main as entrypoint

    with mock.patch.object(entrypoint, "run_qt", return_value=0) as run_qt:
        code = entrypoint.main([])

    assert code == 0
    run_qt.assert_called_once_with()


def test_run_qt_creates_qapplication_and_shows_main_window():
    from app.main import run_qt
    import importlib
    from app.gui_qt import main_window as main_window_module

    class FakeQApplication:
        _instance = None

        def __init__(self, argv):
            self.argv = argv
            self.exec_called = False
            FakeQApplication._instance = self

        @classmethod
        def instance(cls):
            return None

        def exec(self):
            self.exec_called = True
            return 0

    fake_qtwidgets = types.SimpleNamespace(QApplication=FakeQApplication)
    fake_window = mock.Mock()
    fake_window._impl = mock.Mock()

    real_import_module = importlib.import_module

    def _import_module_side_effect(name: str):
        if name == "PySide6.QtWidgets":
            return fake_qtwidgets
        return real_import_module(name)

    with (
        mock.patch("app.main.importlib.util.find_spec", return_value=object()),
        mock.patch("app.main.importlib.import_module", side_effect=_import_module_side_effect),
        mock.patch.object(main_window_module, "SpectralUnmixingMainWindow", return_value=fake_window),
    ):
        code = run_qt()

    assert code == 0
    fake_window._impl.show.assert_called_once_with()


def test_run_qt_reports_missing_pyside6(capsys):
    from app.main import run_qt

    with mock.patch("app.main.importlib.util.find_spec", return_value=None):
        code = run_qt()

    captured = capsys.readouterr()
    assert code == 2
    assert "PySide6 is required" in captured.err
    assert "pip install PySide6" in captured.err
