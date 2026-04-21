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


if __name__ == "__main__":
    unittest.main(verbosity=2)
