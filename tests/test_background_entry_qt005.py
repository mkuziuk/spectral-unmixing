#!/usr/bin/env python3
"""Tests for QT-005: Background entry parsing/validation.

Covers:
  - Default value on startup is 2500.0
  - Valid number accepted and state updated
  - Invalid value reverts text and state unchanged
  - Status label updated with concise validation message
  - Getter returns the last validated value
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv or ["test"])


class TestBackgroundEntryQT005(unittest.TestCase):
    """Verify background entry default, parsing, and validation."""

    def setUp(self):
        from app.gui_qt.main_window import SpectralUnmixingMainWindow

        self.window = SpectralUnmixingMainWindow()
        self.impl = self.window._impl

    # ------------------------------------------------------------------
    # Default value
    # ------------------------------------------------------------------

    def test_default_text_is_2500_0(self):
        """Background entry should display '2500.0' at startup."""
        from PySide6.QtWidgets import QLineEdit
        from app.gui_qt.main_window import BG_ENTRY_OBJECT_NAME

        entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.text(), "2500.0")

    def test_default_background_model_and_exponential_parameters(self):
        """Background model should start constant with exponential defaults ready."""
        from PySide6.QtWidgets import QComboBox, QLineEdit
        from app.gui_qt.main_window import (
            BG_EXP_END_ENTRY_OBJECT_NAME,
            BG_EXP_OFFSET_ENTRY_OBJECT_NAME,
            BG_EXP_SHAPE_ENTRY_OBJECT_NAME,
            BG_EXP_START_ENTRY_OBJECT_NAME,
            BG_MODEL_COMBO_OBJECT_NAME,
        )

        model_combo = self.impl.findChild(QComboBox, BG_MODEL_COMBO_OBJECT_NAME)
        exp_start = self.impl.findChild(QLineEdit, BG_EXP_START_ENTRY_OBJECT_NAME)
        exp_end = self.impl.findChild(QLineEdit, BG_EXP_END_ENTRY_OBJECT_NAME)
        exp_shape = self.impl.findChild(QLineEdit, BG_EXP_SHAPE_ENTRY_OBJECT_NAME)
        exp_offset = self.impl.findChild(QLineEdit, BG_EXP_OFFSET_ENTRY_OBJECT_NAME)

        self.assertIsNotNone(model_combo)
        self.assertIsNotNone(exp_start)
        self.assertIsNotNone(exp_end)
        self.assertIsNotNone(exp_shape)
        self.assertIsNotNone(exp_offset)
        self.assertEqual(model_combo.currentText(), "constant")
        self.assertEqual(exp_start.text(), "1.0")
        self.assertEqual(exp_end.text(), "0.1")
        self.assertEqual(exp_shape.text(), "1.0")
        self.assertEqual(exp_offset.text(), "0.0")

    def test_default_getter_returns_2500_0(self):
        """get_background_value() should return 2500.0 at startup."""
        self.assertEqual(self.window.get_background_value(), 2500.0)

    # ------------------------------------------------------------------
    # Valid input
    # ------------------------------------------------------------------

    def test_valid_number_accepted(self):
        """Entering a valid float should update internal state."""
        from PySide6.QtWidgets import QLineEdit
        from app.gui_qt.main_window import BG_ENTRY_OBJECT_NAME

        entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        entry.clear()
        entry.insert("3000.5")
        entry.editingFinished.emit()
        QTest.qWait(10)

        self.assertEqual(self.window.get_background_value(), 3000.5)

    def test_valid_integer_accepted(self):
        """Entering an integer string should be accepted as float."""
        from PySide6.QtWidgets import QLineEdit
        from app.gui_qt.main_window import BG_ENTRY_OBJECT_NAME

        entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        entry.clear()
        entry.insert("100")
        entry.editingFinished.emit()
        QTest.qWait(10)

        self.assertEqual(self.window.get_background_value(), 100.0)

    def test_valid_negative_accepted(self):
        """Negative numbers should be accepted."""
        from PySide6.QtWidgets import QLineEdit
        from app.gui_qt.main_window import BG_ENTRY_OBJECT_NAME

        entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        entry.clear()
        entry.insert("-50.0")
        entry.editingFinished.emit()
        QTest.qWait(10)

        self.assertEqual(self.window.get_background_value(), -50.0)

    def test_status_label_on_valid_input(self):
        """Status label should show a concise confirmation on valid input."""
        from PySide6.QtWidgets import QLineEdit, QLabel
        from app.gui_qt.main_window import BG_ENTRY_OBJECT_NAME, STATUS_LABEL_OBJECT_NAME

        entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        status = self.impl.findChild(QLabel, STATUS_LABEL_OBJECT_NAME)
        entry.clear()
        entry.insert("4200")
        entry.editingFinished.emit()
        QTest.qWait(10)

        self.assertIn("4200", status.text())

    # ------------------------------------------------------------------
    # Invalid input
    # ------------------------------------------------------------------

    def test_invalid_text_reverts(self):
        """Non-numeric text should revert to last valid value."""
        from PySide6.QtWidgets import QLineEdit
        from app.gui_qt.main_window import BG_ENTRY_OBJECT_NAME

        entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        entry.clear()
        entry.insert("not_a_number")
        entry.editingFinished.emit()
        QTest.qWait(10)

        # State unchanged
        self.assertEqual(self.window.get_background_value(), 2500.0)
        # Text reverted
        self.assertEqual(entry.text(), "2500.0")

    def test_invalid_text_status_message(self):
        """Status label should show an error message for invalid input."""
        from PySide6.QtWidgets import QLineEdit, QLabel
        from app.gui_qt.main_window import BG_ENTRY_OBJECT_NAME, STATUS_LABEL_OBJECT_NAME

        entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        status = self.impl.findChild(QLabel, STATUS_LABEL_OBJECT_NAME)
        entry.clear()
        entry.insert("abc")
        entry.editingFinished.emit()
        QTest.qWait(10)

        self.assertIn("Invalid", status.text())

    def test_empty_string_reverts(self):
        """Empty input should revert to last valid value."""
        from PySide6.QtWidgets import QLineEdit
        from app.gui_qt.main_window import BG_ENTRY_OBJECT_NAME

        entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        entry.clear()
        entry.editingFinished.emit()
        QTest.qWait(10)

        self.assertEqual(self.window.get_background_value(), 2500.0)
        self.assertEqual(entry.text(), "2500.0")

    def test_state_unchanged_after_invalid_then_valid(self):
        """After an invalid entry, the next valid entry should update state."""
        from PySide6.QtWidgets import QLineEdit
        from app.gui_qt.main_window import BG_ENTRY_OBJECT_NAME

        entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)

        # First: invalid
        entry.clear()
        entry.insert("xyz")
        entry.editingFinished.emit()
        QTest.qWait(10)
        self.assertEqual(self.window.get_background_value(), 2500.0)

        # Then: valid
        entry.clear()
        entry.insert("5000.0")
        entry.editingFinished.emit()
        QTest.qWait(10)
        self.assertEqual(self.window.get_background_value(), 5000.0)

    def test_exponential_model_shows_exp_entries_and_hides_constant_entry(self):
        """Choosing exponential should reveal start/end controls and hide constant value."""
        from PySide6.QtWidgets import QComboBox, QLineEdit
        from app.gui_qt.main_window import (
            BG_ENTRY_OBJECT_NAME,
            BG_EXP_END_ENTRY_OBJECT_NAME,
            BG_EXP_OFFSET_ENTRY_OBJECT_NAME,
            BG_EXP_SHAPE_ENTRY_OBJECT_NAME,
            BG_EXP_START_ENTRY_OBJECT_NAME,
            BG_MODEL_COMBO_OBJECT_NAME,
        )

        self.impl.show()
        QTest.qWait(10)

        model_combo = self.impl.findChild(QComboBox, BG_MODEL_COMBO_OBJECT_NAME)
        bg_entry = self.impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        exp_start = self.impl.findChild(QLineEdit, BG_EXP_START_ENTRY_OBJECT_NAME)
        exp_end = self.impl.findChild(QLineEdit, BG_EXP_END_ENTRY_OBJECT_NAME)
        exp_shape = self.impl.findChild(QLineEdit, BG_EXP_SHAPE_ENTRY_OBJECT_NAME)
        exp_offset = self.impl.findChild(QLineEdit, BG_EXP_OFFSET_ENTRY_OBJECT_NAME)

        model_combo.setCurrentText("exponential")
        QTest.qWait(10)

        self.assertFalse(bg_entry.isVisible())
        self.assertTrue(exp_start.isVisible())
        self.assertTrue(exp_end.isVisible())
        self.assertTrue(exp_shape.isVisible())
        self.assertTrue(exp_offset.isVisible())

    def test_exponential_snapshot_captures_background_parameters(self):
        """Run snapshot should capture exponential background model parameters."""
        from PySide6.QtWidgets import QComboBox, QLineEdit
        from app.gui_qt.main_window import (
            BG_EXP_END_ENTRY_OBJECT_NAME,
            BG_EXP_OFFSET_ENTRY_OBJECT_NAME,
            BG_EXP_SHAPE_ENTRY_OBJECT_NAME,
            BG_EXP_START_ENTRY_OBJECT_NAME,
            BG_MODEL_COMBO_OBJECT_NAME,
        )

        self.window.root_dir = "/tmp/root"
        self.window.data_dir = "/tmp/data"
        self.window.folder_info = {"wavelengths": [500, 600, 700]}
        self.window.set_chromophores(["Hb"])

        model_combo = self.impl.findChild(QComboBox, BG_MODEL_COMBO_OBJECT_NAME)
        exp_start = self.impl.findChild(QLineEdit, BG_EXP_START_ENTRY_OBJECT_NAME)
        exp_end = self.impl.findChild(QLineEdit, BG_EXP_END_ENTRY_OBJECT_NAME)
        exp_shape = self.impl.findChild(QLineEdit, BG_EXP_SHAPE_ENTRY_OBJECT_NAME)
        exp_offset = self.impl.findChild(QLineEdit, BG_EXP_OFFSET_ENTRY_OBJECT_NAME)

        model_combo.setCurrentText("exponential")
        exp_start.setText("1.0")
        exp_end.setText("0.1")
        exp_shape.setText("1.5")
        exp_offset.setText("0.02")

        snapshot = self.window._build_config_snapshot()

        self.assertEqual(
            snapshot["background_parameters"],
            {
                "model": "exponential",
                "value": 2500.0,
                "exp_start": 1.0,
                "exp_end": 0.1,
                "exp_shape": 1.5,
                "exp_offset": 0.02,
            },
        )

    def test_background_parameter_help_tooltips_exist(self):
        """Background controls should have '?' help markers with tooltips."""
        from PySide6.QtWidgets import QLabel
        from app.gui_qt.main_window import (
            BACKGROUND_LABEL_OBJECT_NAME,
            BG_ENTRY_OBJECT_NAME,
            BG_EXP_END_LABEL_OBJECT_NAME,
            BG_EXP_OFFSET_LABEL_OBJECT_NAME,
            BG_EXP_SHAPE_LABEL_OBJECT_NAME,
            BG_EXP_START_LABEL_OBJECT_NAME,
            BG_MODEL_COMBO_OBJECT_NAME,
        )

        names = [
            BACKGROUND_LABEL_OBJECT_NAME,
            BG_MODEL_COMBO_OBJECT_NAME,
            BG_ENTRY_OBJECT_NAME,
            BG_EXP_START_LABEL_OBJECT_NAME,
            BG_EXP_END_LABEL_OBJECT_NAME,
            BG_EXP_SHAPE_LABEL_OBJECT_NAME,
            BG_EXP_OFFSET_LABEL_OBJECT_NAME,
        ]
        for object_name in names:
            with self.subTest(object_name=object_name):
                help_label = self.impl.findChild(QLabel, f"{object_name}_help")
                self.assertIsNotNone(help_label)
                self.assertEqual(help_label.text(), "?")
                self.assertTrue(help_label.toolTip())


if __name__ == "__main__":
    unittest.main(verbosity=2)
