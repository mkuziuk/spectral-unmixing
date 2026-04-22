#!/usr/bin/env python3
"""
Tests for SpectralUnmixingMainWindow.

Covers:
  - Window title
  - Initial size and minimum size
  - Object name
  - Central widget presence
  - Import-safe instantiation
  - Splitter shell (QT-006):
      * QSplitter as central widget
      * Two-pane structure (sidebar + QTabWidget)
      * Sidebar placeholder widgets exist
      * Tabs exist in correct order
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Need QApplication before importing any QWidget-dependent code
from PySide6.QtWidgets import QApplication

# Create QApplication if not already created
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv or ["test"])


class TestSpectralUnmixingMainWindow(unittest.TestCase):
    """Tests for app.gui_qt.main_window.SpectralUnmixingMainWindow."""

    def test_import_safe(self):
        """Importing the module should not trigger PySide6 import."""
        # Force reimport to verify
        import importlib
        import app.gui_qt.main_window
        importlib.reload(app.gui_qt.main_window)
        # If we got here without PySide6, we're good
        self.assertTrue(True)

    def test_window_title(self):
        """Window title should be exactly 'Spectral Unmixing'."""
        from app.gui_qt.main_window import SpectralUnmixingMainWindow
        window = SpectralUnmixingMainWindow()
        self.assertEqual(window._impl.windowTitle(), "Spectral Unmixing")

    def test_window_size(self):
        """Initial size should be 1400x900."""
        from app.gui_qt.main_window import SpectralUnmixingMainWindow
        window = SpectralUnmixingMainWindow()
        self.assertEqual(window._impl.width(), 1400)
        self.assertEqual(window._impl.height(), 900)

    def test_window_minimum_size(self):
        """Minimum size should be 1000x700."""
        from app.gui_qt.main_window import SpectralUnmixingMainWindow
        window = SpectralUnmixingMainWindow()
        self.assertEqual(window._impl.minimumWidth(), 1000)
        self.assertEqual(window._impl.minimumHeight(), 700)

    def test_object_name(self):
        """Object name should match plan."""
        from app.gui_qt.main_window import OBJECT_NAME, SpectralUnmixingMainWindow
        self.assertEqual(OBJECT_NAME, "SpectralUnmixingMainWindow")
        window = SpectralUnmixingMainWindow()
        self.assertEqual(window._impl.objectName(), OBJECT_NAME)

    def test_central_widget_exists(self):
        """Central widget placeholder should be set."""
        from app.gui_qt.main_window import SpectralUnmixingMainWindow
        window = SpectralUnmixingMainWindow()
        self.assertIsNotNone(window._impl.centralWidget())

    def test_self_check_passes(self):
        """_check_invariants should return True for a valid window."""
        from app.gui_qt.main_window import SpectralUnmixingMainWindow
        window = SpectralUnmixingMainWindow()
        self.assertTrue(window._check_invariants())


# ---------------------------------------------------------------------------
# QT-006: Splitter shell tests
# ---------------------------------------------------------------------------

class TestSplitterShell(unittest.TestCase):
    """Verify the two-pane splitter shell structure (QT-006)."""

    def setUp(self):
        from app.gui_qt.main_window import SpectralUnmixingMainWindow
        self.window = SpectralUnmixingMainWindow()
        self.impl = self.window._impl

    # -- splitter existence -------------------------------------------------

    def test_central_widget_is_splitter(self):
        """Central widget must be a QSplitter."""
        from PySide6.QtWidgets import QSplitter
        central = self.impl.centralWidget()
        self.assertIsInstance(central, QSplitter)

    def test_splitter_object_name(self):
        """Splitter must have a stable objectName."""
        from app.gui_qt.main_window import SPLITTER_OBJECT_NAME
        central = self.impl.centralWidget()
        self.assertEqual(central.objectName(), SPLITTER_OBJECT_NAME)

    def test_splitter_orientation_horizontal(self):
        """Splitter must be horizontal (left | right)."""
        from PySide6.QtCore import Qt
        central = self.impl.centralWidget()
        self.assertEqual(central.orientation(), Qt.Orientation.Horizontal)

    # -- two-pane structure -------------------------------------------------

    def test_splitter_has_two_panes(self):
        """Splitter must contain exactly two top-level widgets."""
        central = self.impl.centralWidget()
        self.assertEqual(central.count(), 2)

    def test_splitter_initial_sizes(self):
        """Splitter should have baseline initial sizes after being shown.

        The left pane must match INITIAL_SPLITTER_SIZES[0] exactly.
        The right pane fills the remaining width (minus splitter handle).
        """
        from app.gui_qt.main_window import INITIAL_SPLITTER_SIZES
        # Qt only applies splitter sizes after the widget is shown.
        self.impl.show()
        # Process pending events so the layout settles.
        from PySide6.QtTest import QTest
        QTest.qWait(50)
        central = self.impl.centralWidget()
        sizes = central.sizes()
        # Left pane must match the baseline exactly.
        self.assertEqual(sizes[0], INITIAL_SPLITTER_SIZES[0])
        # Right pane should be close to the target (handle width may subtract a few px).
        self.assertGreaterEqual(sizes[1], INITIAL_SPLITTER_SIZES[1] - 10)
        self.impl.hide()

    # -- left sidebar -------------------------------------------------------

    def test_left_pane_is_sidebar_frame(self):
        """First pane must be a QFrame with sidebar objectName."""
        from PySide6.QtWidgets import QFrame
        from app.gui_qt.main_window import SIDEBAR_OBJECT_NAME
        central = self.impl.centralWidget()
        sidebar = central.widget(0)
        self.assertIsInstance(sidebar, QFrame)
        self.assertEqual(sidebar.objectName(), SIDEBAR_OBJECT_NAME)

    def test_sidebar_folder_info_text(self):
        """Sidebar must contain a read-only FolderInfoText QTextEdit."""
        from PySide6.QtWidgets import QTextEdit
        from app.gui_qt.main_window import FOLDER_INFO_TEXT_OBJECT_NAME
        sidebar = self.impl.centralWidget().widget(0)
        widget = sidebar.findChild(QTextEdit, FOLDER_INFO_TEXT_OBJECT_NAME)
        self.assertIsNotNone(widget)
        self.assertTrue(widget.isReadOnly())

    def test_sidebar_sample_combo(self):
        """Sidebar must contain a disabled SampleCombo QComboBox."""
        from PySide6.QtWidgets import QComboBox
        from app.gui_qt.main_window import SAMPLE_COMBO_OBJECT_NAME
        sidebar = self.impl.centralWidget().widget(0)
        widget = sidebar.findChild(QComboBox, SAMPLE_COMBO_OBJECT_NAME)
        self.assertIsNotNone(widget)
        self.assertFalse(widget.isEnabled())

    def test_sidebar_warnings_text(self):
        """Sidebar must contain a read-only red WarningsText QTextEdit."""
        from PySide6.QtWidgets import QTextEdit
        from app.gui_qt.main_window import WARNINGS_TEXT_OBJECT_NAME
        sidebar = self.impl.centralWidget().widget(0)
        widget = sidebar.findChild(QTextEdit, WARNINGS_TEXT_OBJECT_NAME)
        self.assertIsNotNone(widget)
        self.assertTrue(widget.isReadOnly())

    def test_sidebar_warnings_red_style(self):
        """WarningsText must have red text style."""
        from PySide6.QtWidgets import QTextEdit
        from app.gui_qt.main_window import WARNINGS_TEXT_OBJECT_NAME
        sidebar = self.impl.centralWidget().widget(0)
        widget = sidebar.findChild(QTextEdit, WARNINGS_TEXT_OBJECT_NAME)
        self.assertIsNotNone(widget)
        style = widget.styleSheet()
        self.assertIn("color: red", style)

    # -- right tab widget ---------------------------------------------------

    def test_right_pane_is_tab_widget(self):
        """Second pane must be a QTabWidget."""
        from PySide6.QtWidgets import QTabWidget
        from app.gui_qt.main_window import TAB_WIDGET_OBJECT_NAME
        central = self.impl.centralWidget()
        tabs = central.widget(1)
        self.assertIsInstance(tabs, QTabWidget)
        self.assertEqual(tabs.objectName(), TAB_WIDGET_OBJECT_NAME)

    def test_tab_count(self):
        """Tab widget must have exactly five tabs."""
        from app.gui_qt.main_window import SpectralUnmixingMainWindow
        window = SpectralUnmixingMainWindow()
        central = window._impl.centralWidget()
        tabs = central.widget(1)
        self.assertEqual(tabs.count(), 5)

    def test_tab_order(self):
        """Tab labels must be in the exact required order."""
        from app.gui_qt.main_window import (
            BAR_CHARTS_TAB_LABEL,
            DIAGNOSTICS_TAB_LABEL,
            INSPECTOR_TAB_LABEL,
            MAPS_TAB_LABEL,
            STATS_TAB_LABEL,
        )
        central = self.impl.centralWidget()
        tabs = central.widget(1)
        expected = [
            MAPS_TAB_LABEL,
            INSPECTOR_TAB_LABEL,
            DIAGNOSTICS_TAB_LABEL,
            STATS_TAB_LABEL,
            BAR_CHARTS_TAB_LABEL,
        ]
        actual = [tabs.tabText(i) for i in range(tabs.count())]
        self.assertEqual(actual, expected)

    def test_tab_object_names(self):
        """Each tab widget must have its stable objectName."""
        from app.gui_qt.main_window import (
            BAR_CHARTS_TAB_OBJECT_NAME,
            DIAGNOSTICS_TAB_OBJECT_NAME,
            INSPECTOR_TAB_OBJECT_NAME,
            MAPS_TAB_OBJECT_NAME,
            STATS_TAB_OBJECT_NAME,
        )
        central = self.impl.centralWidget()
        tabs = central.widget(1)
        expected_names = [
            MAPS_TAB_OBJECT_NAME,
            INSPECTOR_TAB_OBJECT_NAME,
            DIAGNOSTICS_TAB_OBJECT_NAME,
            STATS_TAB_OBJECT_NAME,
            BAR_CHARTS_TAB_OBJECT_NAME,
        ]
        for i, expected_name in enumerate(expected_names):
            child = tabs.widget(i)
            self.assertEqual(child.objectName(), expected_name)


# ---------------------------------------------------------------------------
# QT-010: Diagnostics panel layout tests
# ---------------------------------------------------------------------------

class TestQt010DiagnosticsPanel(unittest.TestCase):
    """Verify QT-010 diagnostics panel layout and objectNames."""

    def setUp(self):
        from app.gui_qt.main_window import SpectralUnmixingMainWindow
        self.window = SpectralUnmixingMainWindow()
        self.impl = self.window._impl
        # Navigate to the Diagnostics tab (index 2)
        central = self.impl.centralWidget()
        tabs = central.widget(1)
        self.diagnostics_tab = tabs.widget(2)

    def test_stats_frame_exists(self):
        """Diagnostics tab must contain a QGroupBox 'Quality Metrics'."""
        from PySide6.QtWidgets import QGroupBox
        from app.gui_qt.panels.diagnostics_panel import STATS_FRAME_OBJECT_NAME

        frame = self.diagnostics_tab.findChild(QGroupBox, STATS_FRAME_OBJECT_NAME)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.title(), "Quality Metrics")

    def test_stats_text_exists_and_read_only(self):
        """Stats text area must exist and be read-only."""
        from PySide6.QtWidgets import QTextEdit
        from app.gui_qt.panels.diagnostics_panel import STATS_TEXT_OBJECT_NAME

        text = self.diagnostics_tab.findChild(QTextEdit, STATS_TEXT_OBJECT_NAME)
        self.assertIsNotNone(text)
        self.assertTrue(text.isReadOnly())

    def test_diag_canvas_exists(self):
        """Diagnostics tab must contain the matplotlib canvas."""
        from app.gui_qt.panels.diagnostics_panel import DIAG_CANVAS_OBJECT_NAME

        canvas = self.diagnostics_tab.findChild(
            object, DIAG_CANVAS_OBJECT_NAME
        )
        self.assertIsNotNone(canvas)

    def test_canvas_has_two_subplots(self):
        """Canvas figure must have exactly two axes (placeholder subplots)."""
        from app.gui_qt.panels.diagnostics_panel import DIAG_CANVAS_OBJECT_NAME

        canvas_widget = self.diagnostics_tab.findChild(
            object, DIAG_CANVAS_OBJECT_NAME
        )
        self.assertIsNotNone(canvas_widget)
        axes = canvas_widget.figure.get_axes()
        self.assertEqual(len(axes), 2)

    def test_api_stubs_exist(self):
        """DiagnosticsPanel must expose the required API stubs."""
        from app.gui_qt.panels.diagnostics_panel import DiagnosticsPanel

        self.assertTrue(callable(getattr(DiagnosticsPanel, "show_diagnostics", None)))
        self.assertTrue(callable(getattr(DiagnosticsPanel, "set_data", None)))
        self.assertTrue(callable(getattr(DiagnosticsPanel, "refresh", None)))


# ---------------------------------------------------------------------------
# QT-003: Toolbar layout parity tests
# ---------------------------------------------------------------------------

class TestQt003Toolbar(unittest.TestCase):
    """Verify QT-003 toolbar control order, names, and initial states."""

    def setUp(self):
        from app.gui_qt.main_window import SpectralUnmixingMainWindow

        self.window = SpectralUnmixingMainWindow()
        self.impl = self.window._impl

    def test_toolbar_control_order_and_object_names(self):
        """Toolbar widgets must appear in exact left-to-right order."""
        from PySide6.QtWidgets import QToolBar

        expected_order = [
            "select_root_btn",
            "select_data_btn",
            "use_default_btn",
            "chromophore_menu",
            "solver_label",
            "solver_combo",
            "background_label",
            "bg_entry",
            "run_btn",
            "save_btn",
            "progress_bar",
            "data_source_label",
            "status_label",
        ]

        toolbar = self.impl.findChild(QToolBar, "main_toolbar")
        self.assertIsNotNone(toolbar)

        actual_order = []
        for action in toolbar.actions():
            widget = toolbar.widgetForAction(action)
            if widget is None:
                continue
            name = widget.objectName()
            if name:
                actual_order.append(name)

        self.assertEqual(actual_order, expected_order)

    def test_run_and_save_start_disabled(self):
        """Run/Save buttons must be disabled at startup."""
        from PySide6.QtWidgets import QPushButton

        run_btn = self.impl.findChild(QPushButton, "run_btn")
        save_btn = self.impl.findChild(QPushButton, "save_btn")

        self.assertIsNotNone(run_btn)
        self.assertIsNotNone(save_btn)
        self.assertFalse(run_btn.isEnabled())
        self.assertFalse(save_btn.isEnabled())

    def test_solver_combo_readonly(self):
        """Solver combo must be non-editable (readonly)."""
        from PySide6.QtWidgets import QComboBox
        from app.gui_qt.main_window import SOLVER_COMBO_OBJECT_NAME

        solver_combo = self.impl.findChild(QComboBox, SOLVER_COMBO_OBJECT_NAME)
        self.assertIsNotNone(solver_combo)
        self.assertFalse(solver_combo.isEditable())

    def test_solver_combo_options_order(self):
        """Solver combo options must be exactly ['ls', 'nnls', 'mu_a', 'iterative'] in order."""
        from PySide6.QtWidgets import QComboBox
        from app.gui_qt.main_window import SOLVER_COMBO_OBJECT_NAME

        solver_combo = self.impl.findChild(QComboBox, SOLVER_COMBO_OBJECT_NAME)
        self.assertIsNotNone(solver_combo)

        expected = ["ls", "nnls", "mu_a", "iterative"]
        actual = [solver_combo.itemText(i) for i in range(solver_combo.count())]
        self.assertEqual(actual, expected)

    def test_solver_combo_default_selection(self):
        """Solver combo default selection must be 'ls'."""
        from PySide6.QtWidgets import QComboBox
        from app.gui_qt.main_window import SOLVER_COMBO_OBJECT_NAME

        solver_combo = self.impl.findChild(QComboBox, SOLVER_COMBO_OBJECT_NAME)
        self.assertIsNotNone(solver_combo)
        self.assertEqual(solver_combo.currentText(), "ls")

    def test_scattering_toolbar_hidden_by_default(self):
        """Fixed-scattering controls must start hidden until a fixed-scattering solver is selected."""
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QToolBar
        from app.gui_qt.main_window import SCATTERING_TOOLBAR_OBJECT_NAME

        self.impl.show()
        QTest.qWait(10)
        scattering_toolbar = self.impl.findChild(QToolBar, SCATTERING_TOOLBAR_OBJECT_NAME)
        self.assertIsNotNone(scattering_toolbar)
        self.assertFalse(scattering_toolbar.isVisible())

    def test_mu_a_selection_shows_scattering_and_hides_background(self):
        """Choosing mu_a should show fixed-scattering controls and hide background."""
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QComboBox, QLineEdit, QLabel, QToolBar
        from app.gui_qt.main_window import (
            BACKGROUND_LABEL_OBJECT_NAME,
            BG_ENTRY_OBJECT_NAME,
            SCATTERING_TOOLBAR_OBJECT_NAME,
            SOLVER_COMBO_OBJECT_NAME,
        )

        self.impl.show()
        QTest.qWait(10)
        solver_combo = self.impl.findChild(QComboBox, SOLVER_COMBO_OBJECT_NAME)
        background_label = self.impl.findChild(QLabel, BACKGROUND_LABEL_OBJECT_NAME)
        bg_entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        scattering_toolbar = self.impl.findChild(QToolBar, SCATTERING_TOOLBAR_OBJECT_NAME)

        solver_combo.setCurrentText("mu_a")
        QTest.qWait(10)

        self.assertFalse(background_label.isVisible())
        self.assertFalse(bg_entry.isVisible())
        self.assertTrue(scattering_toolbar.isVisible())

    def test_iterative_selection_shows_scattering_and_hides_background(self):
        """Choosing iterative should show fixed-scattering controls and hide background."""
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QComboBox, QLineEdit, QLabel, QToolBar
        from app.gui_qt.main_window import (
            BACKGROUND_LABEL_OBJECT_NAME,
            BG_ENTRY_OBJECT_NAME,
            SCATTERING_TOOLBAR_OBJECT_NAME,
            SOLVER_COMBO_OBJECT_NAME,
        )

        self.impl.show()
        QTest.qWait(10)
        solver_combo = self.impl.findChild(QComboBox, SOLVER_COMBO_OBJECT_NAME)
        background_label = self.impl.findChild(QLabel, BACKGROUND_LABEL_OBJECT_NAME)
        bg_entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        scattering_toolbar = self.impl.findChild(QToolBar, SCATTERING_TOOLBAR_OBJECT_NAME)

        solver_combo.setCurrentText("iterative")
        QTest.qWait(10)

        self.assertFalse(background_label.isVisible())
        self.assertFalse(bg_entry.isVisible())
        self.assertTrue(scattering_toolbar.isVisible())

    def test_switching_back_from_mu_a_restores_background_controls(self):
        """Leaving mu_a should hide scattering controls and restore background."""
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QComboBox, QLineEdit, QLabel, QToolBar
        from app.gui_qt.main_window import (
            BACKGROUND_LABEL_OBJECT_NAME,
            BG_ENTRY_OBJECT_NAME,
            SCATTERING_TOOLBAR_OBJECT_NAME,
            SOLVER_COMBO_OBJECT_NAME,
        )

        self.impl.show()
        QTest.qWait(10)
        solver_combo = self.impl.findChild(QComboBox, SOLVER_COMBO_OBJECT_NAME)
        background_label = self.impl.findChild(QLabel, BACKGROUND_LABEL_OBJECT_NAME)
        bg_entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        scattering_toolbar = self.impl.findChild(QToolBar, SCATTERING_TOOLBAR_OBJECT_NAME)

        solver_combo.setCurrentText("mu_a")
        QTest.qWait(10)
        solver_combo.setCurrentText("ls")
        QTest.qWait(10)

        self.assertTrue(background_label.isVisible())
        self.assertTrue(bg_entry.isVisible())
        self.assertFalse(scattering_toolbar.isVisible())

    def test_mu_a_snapshot_captures_scattering_parameters(self):
        """Run snapshot should include validated fixed-scattering parameters."""
        from PySide6.QtWidgets import QComboBox, QLineEdit
        from app.gui_qt.main_window import (
            SCATTERING_ANISOTROPY_ENTRY_OBJECT_NAME,
            SCATTERING_LAMBDA0_ENTRY_OBJECT_NAME,
            SCATTERING_LIPOFUNDIN_ENTRY_OBJECT_NAME,
            SCATTERING_MU_S_500_ENTRY_OBJECT_NAME,
            SCATTERING_POWER_ENTRY_OBJECT_NAME,
            SOLVER_COMBO_OBJECT_NAME,
        )

        self.window.root_dir = "/tmp/root"
        self.window.data_dir = "/tmp/data"
        self.window.folder_info = {"wavelengths": [500, 550]}
        self.window.set_chromophores(["Hb"])

        solver_combo = self.impl.findChild(QComboBox, SOLVER_COMBO_OBJECT_NAME)
        solver_combo.setCurrentText("mu_a")

        entry_values = {
            SCATTERING_LAMBDA0_ENTRY_OBJECT_NAME: "510",
            SCATTERING_MU_S_500_ENTRY_OBJECT_NAME: "130",
            SCATTERING_POWER_ENTRY_OBJECT_NAME: "1.2",
            SCATTERING_LIPOFUNDIN_ENTRY_OBJECT_NAME: "0.35",
            SCATTERING_ANISOTROPY_ENTRY_OBJECT_NAME: "0.78",
        }
        for object_name, value in entry_values.items():
            entry = self.impl.findChild(QLineEdit, object_name)
            self.assertIsNotNone(entry)
            entry.setText(value)

        snapshot = self.window._build_config_snapshot()

        self.assertEqual(snapshot["solver_method"], "mu_a")
        self.assertFalse(snapshot["include_background"])
        self.assertEqual(
            snapshot["scattering_parameters"],
            {
                "lambda0_nm": 510.0,
                "mu_s_500_cm1": 130.0,
                "power_b": 1.2,
                "lipofundin_fraction": 0.35,
                "anisotropy_g": 0.78,
            },
        )

    def test_iterative_snapshot_captures_scattering_parameters(self):
        """Iterative snapshot should include validated fixed-scattering parameters."""
        from PySide6.QtWidgets import QComboBox, QLineEdit
        from app.gui_qt.main_window import (
            SCATTERING_ANISOTROPY_ENTRY_OBJECT_NAME,
            SCATTERING_LAMBDA0_ENTRY_OBJECT_NAME,
            SCATTERING_LIPOFUNDIN_ENTRY_OBJECT_NAME,
            SCATTERING_MU_S_500_ENTRY_OBJECT_NAME,
            SCATTERING_POWER_ENTRY_OBJECT_NAME,
            SOLVER_COMBO_OBJECT_NAME,
        )

        self.window.root_dir = "/tmp/root"
        self.window.data_dir = "/tmp/data"
        self.window.folder_info = {"wavelengths": [500, 550]}
        self.window.set_chromophores(["Hb"])

        solver_combo = self.impl.findChild(QComboBox, SOLVER_COMBO_OBJECT_NAME)
        solver_combo.setCurrentText("iterative")

        entry_values = {
            SCATTERING_LAMBDA0_ENTRY_OBJECT_NAME: "505",
            SCATTERING_MU_S_500_ENTRY_OBJECT_NAME: "125",
            SCATTERING_POWER_ENTRY_OBJECT_NAME: "1.1",
            SCATTERING_LIPOFUNDIN_ENTRY_OBJECT_NAME: "0.30",
            SCATTERING_ANISOTROPY_ENTRY_OBJECT_NAME: "0.79",
        }
        for object_name, value in entry_values.items():
            entry = self.impl.findChild(QLineEdit, object_name)
            self.assertIsNotNone(entry)
            entry.setText(value)

        snapshot = self.window._build_config_snapshot()

        self.assertEqual(snapshot["solver_method"], "iterative")
        self.assertFalse(snapshot["include_background"])
        self.assertEqual(
            snapshot["scattering_parameters"],
            {
                "lambda0_nm": 505.0,
                "mu_s_500_cm1": 125.0,
                "power_b": 1.1,
                "lipofundin_fraction": 0.30,
                "anisotropy_g": 0.79,
            },
        )


# ---------------------------------------------------------------------------
# QT-025: Warnings sidebar tests
# ---------------------------------------------------------------------------

class TestQt025WarningsSidebar(unittest.TestCase):
    """Verify QT-025 warnings sidebar population and clearing."""

    def setUp(self):
        from app.gui_qt.main_window import SpectralUnmixingMainWindow
        self.window = SpectralUnmixingMainWindow()
        self.impl = self.window._impl

    def test_update_warnings_with_non_empty_list(self):
        """update_warnings should populate warnings text from non-empty list."""
        from PySide6.QtWidgets import QTextEdit

        warnings = ["Low signal detected", "Possible saturation in channel 3"]
        self.window.update_warnings(warnings)

        from app.gui_qt.main_window import WARNINGS_TEXT_OBJECT_NAME
        widget = self.impl.findChild(QTextEdit, WARNINGS_TEXT_OBJECT_NAME)
        self.assertIsNotNone(widget)
        expected_text = "Low signal detected\nPossible saturation in channel 3"
        self.assertEqual(widget.toPlainText(), expected_text)

    def test_update_warnings_with_empty_list(self):
        """update_warnings should show 'No warnings ✓' for empty list."""
        from PySide6.QtWidgets import QTextEdit

        self.window.update_warnings([])

        from app.gui_qt.main_window import WARNINGS_TEXT_OBJECT_NAME
        widget = self.impl.findChild(QTextEdit, WARNINGS_TEXT_OBJECT_NAME)
        self.assertIsNotNone(widget)
        self.assertEqual(widget.toPlainText(), "No warnings ✓")

    def test_update_warnings_with_none(self):
        """update_warnings should show 'No warnings ✓' for None."""
        from PySide6.QtWidgets import QTextEdit

        self.window.update_warnings(None)

        from app.gui_qt.main_window import WARNINGS_TEXT_OBJECT_NAME
        widget = self.impl.findChild(QTextEdit, WARNINGS_TEXT_OBJECT_NAME)
        self.assertIsNotNone(widget)
        self.assertEqual(widget.toPlainText(), "No warnings ✓")

    def test_update_warnings_single_warning(self):
        """update_warnings should handle single warning string."""
        from PySide6.QtWidgets import QTextEdit

        self.window.update_warnings(["Single warning"])

        from app.gui_qt.main_window import WARNINGS_TEXT_OBJECT_NAME
        widget = self.impl.findChild(QTextEdit, WARNINGS_TEXT_OBJECT_NAME)
        self.assertIsNotNone(widget)
        self.assertEqual(widget.toPlainText(), "Single warning")


if __name__ == '__main__':
    unittest.main(verbosity=2)
