"""Focused tests for the chromophore bar-chart panel."""

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


def test_barcharts_panel_shell_layout(qapp_instance):
    """Panel exposes a single matplotlib canvas in a vertical layout."""
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from app.gui_qt.panels.chromophore_barcharts_panel import (
        BAR_CHARTS_CANVAS_OBJECT_NAME,
        ChromophoreBarChartsPanel,
    )

    panel = ChromophoreBarChartsPanel()
    root = panel._impl
    qapp_instance.processEvents()

    canvas = root.findChild(QWidget, BAR_CHARTS_CANVAS_OBJECT_NAME)

    assert canvas is not None
    layout = root.layout()
    assert isinstance(layout, QVBoxLayout)
    assert layout.count() == 1
    assert layout.itemAt(0).widget() is canvas


def test_barcharts_panel_renders_mean_and_median_per_sample(qapp_instance):
    """Each chromophore subplot renders side-by-side mean and median bars."""
    from app.gui_qt.panels.chromophore_barcharts_panel import ChromophoreBarChartsPanel

    panel = ChromophoreBarChartsPanel()
    panel.set_data(
        {
            "A1": {
                "chromophore_names": ["HbO2", "Hb"],
                "concentrations": np.array(
                    [
                        [[1.0, 4.0], [3.0, 8.0]],
                        [[5.0, 12.0], [7.0, 16.0]],
                    ],
                    dtype=float,
                ),
            },
            "A2": {
                "chromophore_names": ["HbO2", "Hb"],
                "concentrations": np.array(
                    [
                        [[2.0, 1.0], [2.0, 5.0]],
                        [[6.0, 9.0], [10.0, 13.0]],
                    ],
                    dtype=float,
                ),
            },
        }
    )
    qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes) == 2
    assert fig._suptitle is not None
    assert fig._suptitle.get_text() == "Chromophore Comparison Across Samples"

    first_ax = fig.axes[0]
    second_ax = fig.axes[1]

    assert first_ax.get_title() == "HbO2: Mean vs Median"
    assert second_ax.get_title() == "Hb: Mean vs Median"
    assert first_ax.get_xlabel() == "Samples"
    assert first_ax.get_ylabel() == "Concentration"
    assert [tick.get_text() for tick in first_ax.get_xticklabels()] == ["A1", "A2"]

    first_heights = [patch.get_height() for patch in first_ax.patches]
    second_heights = [patch.get_height() for patch in second_ax.patches]

    np.testing.assert_allclose(first_heights, [4.0, 5.0, 4.0, 4.0], rtol=0, atol=1e-12)
    np.testing.assert_allclose(second_heights, [10.0, 7.0, 10.0, 7.0], rtol=0, atol=1e-12)


def test_barcharts_panel_invalid_data_shows_placeholder(qapp_instance):
    """Invalid payloads render a no-data message instead of raising."""
    from app.gui_qt.panels.chromophore_barcharts_panel import ChromophoreBarChartsPanel

    panel = ChromophoreBarChartsPanel()
    panel.set_data({"sample": {"chromophore_names": ["Hb"], "concentrations": np.array([1.0, 2.0])}})
    qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes) == 1
    ax = fig.axes[0]
    assert any("No valid chromophore concentration data" in text.get_text() for text in ax.texts)
