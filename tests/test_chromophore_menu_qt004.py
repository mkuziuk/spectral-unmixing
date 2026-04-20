#!/usr/bin/env python3
"""QT-004 tests for checkable chromophore menu behavior."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# Keep Qt deterministic for headless CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication, QToolButton

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv or ["test"])


class TestQt004ChromophoreMenu(unittest.TestCase):
    """Unit tests for app.gui_qt.widgets.chromophore_menu.ChromophoreMenu."""

    def test_menu_item_creation_and_sorted_order(self):
        """Chromophore actions should be sorted and include Background."""
        from app.gui_qt.widgets.chromophore_menu import ChromophoreMenu

        menu = ChromophoreMenu()
        menu.set_chromophores(["Water", "Hb", "HbO2"])

        labels = [
            action.text()
            for action in menu._menu.actions()
            if not action.isSeparator()
        ]
        self.assertEqual(labels, ["Hb", "HbO2", "Water", "Background"])

    def test_background_action_default_checked(self):
        """Background action should always exist and start checked."""
        from app.gui_qt.widgets.chromophore_menu import ChromophoreMenu

        menu = ChromophoreMenu()
        self.assertIsNotNone(menu._background_action)
        self.assertTrue(menu._background_action.isCheckable())
        self.assertTrue(menu._background_action.isChecked())
        self.assertEqual(menu.get_selected(include_background=True), ["Background"])

    def test_toggle_actions_reflected_in_selected_output(self):
        """Checked state changes should propagate into get_selected output."""
        from app.gui_qt.widgets.chromophore_menu import ChromophoreMenu

        menu = ChromophoreMenu()
        menu.set_chromophores(["Melanin", "HbO2"])

        menu._chromophore_actions["HbO2"].setChecked(False)
        menu._background_action.setChecked(False)
        self.assertEqual(menu.get_selected(), ["Melanin"])
        self.assertEqual(menu.get_selected(include_background=True), ["Melanin"])

        menu._background_action.setChecked(True)
        self.assertEqual(
            menu.get_selected(include_background=True),
            ["Melanin", "Background"],
        )


class TestQt004ToolbarIntegration(unittest.TestCase):
    """Integration tests for chromophore menu in main toolbar."""

    def setUp(self):
        from app.gui_qt.main_window import SpectralUnmixingMainWindow

        self.window = SpectralUnmixingMainWindow()
        self.impl = self.window._impl

    def test_toolbar_contains_toolbutton_menu_with_background(self):
        """Toolbar chromophore control should be a QToolButton with menu."""
        from app.gui_qt.main_window import CHROMOPHORE_MENU_OBJECT_NAME

        chromo_btn = self.impl.findChild(QToolButton, CHROMOPHORE_MENU_OBJECT_NAME)
        self.assertIsNotNone(chromo_btn)
        self.assertIsNotNone(chromo_btn.menu())

        labels = [
            action.text()
            for action in chromo_btn.menu().actions()
            if not action.isSeparator()
        ]
        # Initial entries may include default-data chromophores when available,
        # but Background must always be present.
        self.assertIn("Background", labels)

    def test_main_window_hooks_set_chromophores_and_get_selection(self):
        """Main window should expose QT-004 menu integration hooks."""
        self.window.set_chromophores(["Water", "Hb"])
        self.assertEqual(self.window.get_selection(), ["Hb", "Water"])
        self.assertEqual(
            self.window.get_selection(include_background=True),
            ["Hb", "Water", "Background"],
        )

        chromo_btn = self.impl.findChild(QToolButton, "chromophore_menu")
        for action in chromo_btn.menu().actions():
            if action.text() == "Hb":
                action.setChecked(False)

        self.assertEqual(self.window.get_selection(), ["Water"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
