"""Focused tests for Reflectance Stats panel shell (QT-011)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def qapp_instance():
    """Return a shared QApplication (or skip if PySide6 unavailable)."""
    pytest.importorskip("PySide6", reason="PySide6 is not installed; skipping Qt tests")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv or ["pytest"])
    return app


def test_stats_panel_shell_layout_and_defaults(qapp_instance):
    """Stats panel exposes required controls and canvas shell."""
    from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

    from app.gui_qt.panels.stats_panel import StatsPanel

    panel = StatsPanel()
    root = panel._impl
    qapp_instance.processEvents()

    label = root.findChild(QLabel, "stat_label")
    combo = root.findChild(QComboBox, "stat_combo")
    canvas = root.findChild(QWidget, "stat_canvas")

    assert label is not None
    assert combo is not None
    assert canvas is not None

    assert [combo.itemText(i) for i in range(combo.count())] == ["Mean", "Median"]
    assert combo.currentText() == "Median"
    assert not combo.isEditable()

    layout = root.layout()
    assert isinstance(layout, QVBoxLayout)
    assert layout.count() == 2
    assert layout.itemAt(0).layout() is not None
    assert layout.itemAt(1).widget() is canvas


def test_stats_panel_stub_methods_are_callable(qapp_instance):
    """Stats panel public methods remain callable with placeholder inputs."""
    from app.gui_qt.panels.stats_panel import StatsPanel

    panel = StatsPanel()

    panel.set_data({"placeholder": True})
    panel.refresh({"median": 0.0})


def test_stats_panel_mean_vs_median_toggle_updates_line_data(qapp_instance):
    """Changing stat_combo switches between nan-safe median and mean arrays."""
    from PySide6.QtWidgets import QComboBox

    from app.gui_qt.panels.stats_panel import StatsPanel

    panel = StatsPanel()
    root = panel._impl
    combo = root.findChild(QComboBox, "stat_combo")
    assert combo is not None

    reflectance = np.array(
        [
            [[1.0, 10.0, 1.0], [2.0, 20.0, np.nan]],
            [[np.nan, 30.0, 3.0], [4.0, 40.0, 5.0]],
        ],
        dtype=float,
    )
    res = {
        "wavelengths": np.array([450.0, 550.0, 650.0], dtype=float),
        "reflectance": reflectance,
    }

    expected_median = np.array([2.0, 25.0, 3.0], dtype=float)
    expected_mean = np.array([7.0 / 3.0, 25.0, 3.0], dtype=float)

    panel.set_data(res)
    qapp_instance.processEvents()

    fig = panel._stat_canvas.figure
    assert len(fig.axes) == 1
    median_ax = fig.axes[0]
    assert len(median_ax.lines) == 1
    np.testing.assert_allclose(
        median_ax.lines[0].get_xdata(),
        res["wavelengths"],
        rtol=0,
        atol=0,
    )
    np.testing.assert_allclose(
        median_ax.lines[0].get_ydata(),
        expected_median,
        rtol=1e-12,
        atol=1e-12,
        equal_nan=True,
    )

    combo.setCurrentText("Mean")
    qapp_instance.processEvents()

    assert len(fig.axes) == 1
    mean_ax = fig.axes[0]
    assert len(mean_ax.lines) == 1
    np.testing.assert_allclose(
        mean_ax.lines[0].get_ydata(),
        expected_mean,
        rtol=1e-12,
        atol=1e-12,
        equal_nan=True,
    )


def test_stats_panel_invalid_data_is_handled_gracefully(qapp_instance):
    """Invalid payloads do not raise and render a no-data view."""
    from app.gui_qt.panels.stats_panel import StatsPanel

    panel = StatsPanel()
    panel.set_data({"wavelengths": [500, 600], "reflectance": np.array([[1.0, 2.0]])})
    qapp_instance.processEvents()

    fig = panel._stat_canvas.figure
    assert len(fig.axes) == 1
    ax = fig.axes[0]
    assert len(ax.lines) == 0
    assert any("No valid reflectance data" in txt.get_text() for txt in ax.texts)
