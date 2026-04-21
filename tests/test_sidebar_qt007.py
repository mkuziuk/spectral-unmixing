#!/usr/bin/env python3
"""Focused tests for QT-007 sidebar read-only setup and helper hooks."""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv or ["test"])


class TestSidebarQt007(unittest.TestCase):
    """Verify sidebar controls and UI-only update helper methods."""

    def setUp(self):
        from app.gui_qt.main_window import SpectralUnmixingMainWindow

        self.window = SpectralUnmixingMainWindow()
        self.impl = self.window._impl
        self.sidebar = self.impl.centralWidget().widget(0)

    def test_sidebar_widgets_readonly_contract(self):
        """Folder/Warn text must be read-only and Sample combo non-editable."""
        from PySide6.QtWidgets import QComboBox, QTextEdit
        from app.gui_qt.main_window import (
            FOLDER_INFO_TEXT_OBJECT_NAME,
            SAMPLE_COMBO_OBJECT_NAME,
            WARNINGS_TEXT_OBJECT_NAME,
        )

        folder_info = self.sidebar.findChild(QTextEdit, FOLDER_INFO_TEXT_OBJECT_NAME)
        sample_combo = self.sidebar.findChild(QComboBox, SAMPLE_COMBO_OBJECT_NAME)
        warnings = self.sidebar.findChild(QTextEdit, WARNINGS_TEXT_OBJECT_NAME)

        self.assertIsNotNone(folder_info)
        self.assertIsNotNone(sample_combo)
        self.assertIsNotNone(warnings)
        self.assertTrue(folder_info.isReadOnly())
        self.assertFalse(sample_combo.isEditable())
        self.assertTrue(warnings.isReadOnly())

    def test_set_folder_info_updates_text(self):
        """set_folder_info should replace the FolderInfoText contents."""
        from PySide6.QtWidgets import QTextEdit
        from app.gui_qt.main_window import FOLDER_INFO_TEXT_OBJECT_NAME

        self.window.set_folder_info("root=/tmp/data\nfiles=42")

        folder_info = self.sidebar.findChild(QTextEdit, FOLDER_INFO_TEXT_OBJECT_NAME)
        self.assertEqual(folder_info.toPlainText(), "root=/tmp/data\nfiles=42")

    def test_set_samples_populates_combo_and_enables(self):
        """set_samples should load provided names and select first by default."""
        from PySide6.QtWidgets import QComboBox
        from app.gui_qt.main_window import SAMPLE_COMBO_OBJECT_NAME

        self.window.set_samples(["sample_A", "sample_B", "sample_C"])

        combo = self.sidebar.findChild(QComboBox, SAMPLE_COMBO_OBJECT_NAME)
        self.assertEqual(combo.count(), 3)
        self.assertTrue(combo.isEnabled())
        self.assertEqual([combo.itemText(i) for i in range(combo.count())], ["sample_A", "sample_B", "sample_C"])
        self.assertEqual(combo.currentText(), "sample_A")

    def test_set_samples_empty_resets_placeholder(self):
        """set_samples([]) should reset to placeholder and disable combo."""
        from PySide6.QtWidgets import QComboBox
        from app.gui_qt.main_window import SAMPLE_COMBO_OBJECT_NAME

        self.window.set_samples(["sample_A"])
        self.window.set_samples([])

        combo = self.sidebar.findChild(QComboBox, SAMPLE_COMBO_OBJECT_NAME)
        self.assertEqual(combo.count(), 1)
        self.assertEqual(combo.itemText(0), "— none —")
        self.assertFalse(combo.isEnabled())

    def test_select_sample_selects_existing_name(self):
        """select_sample should move current selection when name exists."""
        from PySide6.QtWidgets import QComboBox
        from app.gui_qt.main_window import SAMPLE_COMBO_OBJECT_NAME

        self.window.set_samples(["sample_A", "sample_B", "sample_C"])
        self.window.select_sample("sample_B")

        combo = self.sidebar.findChild(QComboBox, SAMPLE_COMBO_OBJECT_NAME)
        self.assertEqual(combo.currentText(), "sample_B")

    def test_select_sample_ignores_unknown_name(self):
        """select_sample should keep current selection for unknown names."""
        from PySide6.QtWidgets import QComboBox
        from app.gui_qt.main_window import SAMPLE_COMBO_OBJECT_NAME

        self.window.set_samples(["sample_A", "sample_B"])
        self.window.select_sample("missing")

        combo = self.sidebar.findChild(QComboBox, SAMPLE_COMBO_OBJECT_NAME)
        self.assertEqual(combo.currentText(), "sample_A")


if __name__ == "__main__":
    unittest.main(verbosity=2)
