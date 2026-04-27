"""QT-018 smoke tests for the PySide6 main window shell.

These tests stay intentionally shallow (startup/layout discovery only)
and avoid interaction/integration behavior that belongs to QT-019.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


# Keep Qt test runs deterministic on headless CI unless user overrides it.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


EXPECTED_TAB_ORDER = [
    "Maps",
    "Pixel Inspector",
    "Diagnostics",
    "Reflectance Stats",
    "Chromophore Bar Charts",
]

CORE_TOOLBAR_OBJECT_NAMES = [
    "select_root_btn",
    "select_data_btn",
    "use_default_btn",
    "chromophore_menu",
    "solver_combo",
    "bg_model_combo",
    "bg_entry",
    "bg_exp_start_entry",
    "bg_exp_end_entry",
    "scattering_toolbar",
    "scattering_lambda0_entry",
    "scattering_mu_s_500_entry",
    "scattering_power_entry",
    "scattering_lipofundin_entry",
    "scattering_anisotropy_entry",
    "iterative_toolbar",
    "iterative_max_iter_entry",
    "iterative_tol_rel_entry",
    "iterative_tol_rmse_entry",
    "iterative_damping_entry",
    "iterative_initial_conc_entry",
    "iterative_reset_btn",
    "run_btn",
    "save_btn",
]



def _find_object_by_name(root, object_name: str):
    """Return first QObject descendant with matching objectName."""
    from PySide6.QtCore import QObject

    if root.objectName() == object_name:
        return root

    for child in root.findChildren(QObject):
        if child.objectName() == object_name:
            return child

    return None


@pytest.fixture(scope="session")
def qapp_instance():
    """Return a shared QApplication (or skip if PySide6 is unavailable)."""
    pytest.importorskip("PySide6", reason="PySide6 is not installed; skipping Qt smoke tests")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv or ["pytest"])
    return app


@pytest.fixture
def qtbot_or_none(request):
    """Use pytest-qt's qtbot when available, otherwise return None."""
    try:
        return request.getfixturevalue("qtbot")
    except pytest.FixtureLookupError:
        return None


@pytest.fixture
def main_window(qapp_instance, qtbot_or_none):
    """Create and show the Qt main window shell for smoke checks."""
    from app.gui_qt.main_window import SpectralUnmixingMainWindow

    window = SpectralUnmixingMainWindow()
    widget = window._impl

    if qtbot_or_none is not None:
        qtbot_or_none.addWidget(widget)

    widget.show()
    qapp_instance.processEvents()

    yield window

    widget.close()
    qapp_instance.processEvents()


def test_qt_main_window_instantiates_without_crash(main_window):
    """Main window object can be created and exposed as a QWidget."""
    assert main_window is not None
    assert main_window._impl is not None


def test_qt_main_window_has_expected_tab_order(main_window):
    """Main shell contains all five tabs in baseline order."""
    from PySide6.QtWidgets import QTabWidget

    tab_widget = main_window._impl.findChild(QTabWidget)
    assert tab_widget is not None, "Expected a QTabWidget in the main shell"

    actual_tab_order = [tab_widget.tabText(idx) for idx in range(tab_widget.count())]
    assert actual_tab_order == EXPECTED_TAB_ORDER


def test_qt_toolbar_core_widgets_discoverable_by_object_name(main_window):
    """Core toolbar controls are addressable via stable objectName values."""
    missing = [
        object_name
        for object_name in CORE_TOOLBAR_OBJECT_NAMES
        if _find_object_by_name(main_window._impl, object_name) is None
    ]

    assert not missing, f"Missing expected toolbar widget objectNames: {missing}"


def test_qt_run_and_save_buttons_start_disabled(main_window):
    """Run/Save must be disabled until required data pipeline state is ready."""
    from PySide6.QtWidgets import QPushButton

    run_btn = _find_object_by_name(main_window._impl, "run_btn")
    save_btn = _find_object_by_name(main_window._impl, "save_btn")

    assert run_btn is not None, "run_btn not found by objectName"
    assert save_btn is not None, "save_btn not found by objectName"
    assert isinstance(run_btn, QPushButton)
    assert isinstance(save_btn, QPushButton)
    assert not run_btn.isEnabled()
    assert not save_btn.isEnabled()
