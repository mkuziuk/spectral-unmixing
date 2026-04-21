"""QT-013 callback wiring tests for the Qt main window."""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import numpy as np
import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def qapp():
    pytest.importorskip("PySide6", reason="PySide6 is not installed")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv or ["pytest-qt013"])
    return app


@pytest.fixture(autouse=True)
def _stub_rawpy_module(monkeypatch):
    """Allow importing app.core.io in environments without rawpy."""
    if "rawpy" not in sys.modules:
        monkeypatch.setitem(sys.modules, "rawpy", types.ModuleType("rawpy"))


@pytest.fixture
def window(qapp):
    from app.gui_qt.main_window import SpectralUnmixingMainWindow

    w = SpectralUnmixingMainWindow()
    w._impl.show()
    qapp.processEvents()
    yield w
    w._impl.close()
    qapp.processEvents()


def _click_named_button(window, object_name: str) -> None:
    from PySide6.QtWidgets import QPushButton

    btn = window._impl.findChild(QPushButton, object_name)
    assert btn is not None
    btn.click()


def test_root_and_data_callbacks_invoke_backend_and_update_ui(window, monkeypatch, qapp):
    from PySide6.QtWidgets import QLabel, QTextEdit, QComboBox
    from app.gui_qt.main_window import (
        DATA_SOURCE_LABEL_OBJECT_NAME,
        FOLDER_INFO_TEXT_OBJECT_NAME,
        SAMPLE_COMBO_OBJECT_NAME,
        STATUS_LABEL_OBJECT_NAME,
    )

    calls: dict[str, list[str]] = {"detect": [], "validate": []}

    fake_info = {
        "samples": ["/root/s1", "/root/s2"],
        "sample_names": ["sample_1", "sample_2"],
        "ref_dir": "/root/ref",
        "dark_ref_dir": "/root/dark_ref",
        "wavelengths": [450, 550, 650],
    }

    def fake_get_dir(*_args, **_kwargs):
        return "/tmp/my_root"

    def fake_detect(path: str):
        calls["detect"].append(path)
        return fake_info

    def fake_validate(path: str):
        calls["validate"].append(path)

    def fake_spectra(_path: str):
        return {"Hb": (np.array([500.0]), np.array([1.0]))}

    monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getExistingDirectory", fake_get_dir)
    monkeypatch.setattr("app.core.io.detect_folders", fake_detect)
    monkeypatch.setattr("app.core.io.validate_data_directory", fake_validate)
    monkeypatch.setattr("app.core.io.load_chromophore_spectra", fake_spectra)

    _click_named_button(window, "select_root_btn")
    qapp.processEvents()

    assert calls["detect"] == ["/tmp/my_root"]

    folder_info = window._impl.findChild(QTextEdit, FOLDER_INFO_TEXT_OBJECT_NAME)
    assert folder_info is not None
    assert "Root: my_root" in folder_info.toPlainText()
    assert "sample_1" in folder_info.toPlainText()

    sample_combo = window._impl.findChild(QComboBox, SAMPLE_COMBO_OBJECT_NAME)
    assert sample_combo is not None
    assert sample_combo.isEnabled()
    assert [sample_combo.itemText(i) for i in range(sample_combo.count())] == ["sample_1", "sample_2"]

    status = window._impl.findChild(QLabel, STATUS_LABEL_OBJECT_NAME)
    assert status is not None
    assert "Loaded root" in status.text()

    # Now exercise Select Data.
    monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getExistingDirectory", lambda *_a, **_k: "/tmp/custom_data")
    _click_named_button(window, "select_data_btn")
    qapp.processEvents()

    assert calls["validate"] == ["/tmp/custom_data"]

    data_label = window._impl.findChild(QLabel, DATA_SOURCE_LABEL_OBJECT_NAME)
    assert data_label is not None
    assert data_label.text() == "Data: custom (custom_data)"


def test_sample_selection_triggers_panel_refresh(window, monkeypatch, qapp):
    from PySide6.QtWidgets import QTextEdit
    from app.gui_qt.main_window import WARNINGS_TEXT_OBJECT_NAME

    sample_a = {
        "concentrations": np.zeros((2, 2, 1)),
        "chromophore_names": ["Hb"],
        "derived": {},
        "rmse_map": np.zeros((2, 2)),
        "diagnostics": {"warnings": []},
        "wavelengths": [500],
        "reflectance": np.zeros((2, 2, 1)),
    }
    sample_b = {
        "concentrations": np.ones((2, 2, 1)),
        "chromophore_names": ["Hb"],
        "derived": {},
        "rmse_map": np.ones((2, 2)),
        "diagnostics": {"warnings": ["high RMSE"]},
        "wavelengths": [500],
        "reflectance": np.ones((2, 2, 1)),
    }

    window._results = {"A": sample_a, "B": sample_b}

    calls = {"maps": [], "inspector": [], "diag": [], "stats": []}
    monkeypatch.setattr(window._maps_panel, "show_results", lambda data: calls["maps"].append(data))
    monkeypatch.setattr(window._inspector_panel, "set_data", lambda data: calls["inspector"].append(data))
    monkeypatch.setattr(window._diagnostics_panel, "set_data", lambda data: calls["diag"].append(data))
    monkeypatch.setattr(window._stats_panel, "set_data", lambda data: calls["stats"].append(data))

    window.set_samples(["A", "B"])
    qapp.processEvents()

    # Ignore initial selection callback from set_samples, then select explicit sample.
    for key in calls:
        calls[key].clear()

    window.select_sample("B")
    qapp.processEvents()

    assert calls["maps"] == [sample_b]
    assert calls["inspector"] == [sample_b]
    assert calls["stats"] == [sample_b]
    assert calls["diag"][0]["diagnostics"]["warnings"] == ["high RMSE"]

    warnings_text = window._impl.findChild(QTextEdit, WARNINGS_TEXT_OBJECT_NAME)
    assert warnings_text is not None
    assert "high RMSE" in warnings_text.toPlainText()


def test_save_disabled_until_results_then_exports(window, monkeypatch, qapp):
    from PySide6.QtWidgets import QPushButton

    save_btn = window._impl.findChild(QPushButton, "save_btn")
    assert save_btn is not None
    assert not save_btn.isEnabled()

    sample = {
        "concentrations": np.ones((2, 2, 1)),
        "chromophore_names": ["Hb"],
        "derived": {"THb": np.ones((2, 2))},
        "rmse_map": np.ones((2, 2)),
        "diagnostics": {"warnings": []},
    }

    window._on_results_ready(
        {
            "samples": {"sample_1": sample},
            "chrom_scales": {},
            "derived_scales": {},
        }
    )
    qapp.processEvents()
    assert save_btn.isEnabled()

    exported: list[tuple[str, str]] = []
    monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getExistingDirectory", lambda *_a, **_k: "/tmp/out")
    monkeypatch.setattr(
        "app.core.export.save_results",
        lambda out_dir, sample_name, *_a, **_k: exported.append((out_dir, sample_name)),
    )

    save_btn.click()
    qapp.processEvents()

    assert exported == [("/tmp/out", "sample_1")]


def test_error_path_sets_status_and_no_crash(window, monkeypatch, qapp):
    from PySide6.QtWidgets import QLabel
    from app.gui_qt.main_window import STATUS_LABEL_OBJECT_NAME

    shown_errors: list[tuple[str, str]] = []
    monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getExistingDirectory", lambda *_a, **_k: "/tmp/bad_root")
    monkeypatch.setattr("app.core.io.detect_folders", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(window, "_show_error", lambda title, msg: shown_errors.append((title, msg)))

    _click_named_button(window, "select_root_btn")
    qapp.processEvents()

    status = window._impl.findChild(QLabel, STATUS_LABEL_OBJECT_NAME)
    assert status is not None
    assert status.text() == "Failed to load root folder"
    assert shown_errors
    assert "boom" in shown_errors[0][1]
    assert window._impl.isVisible()
