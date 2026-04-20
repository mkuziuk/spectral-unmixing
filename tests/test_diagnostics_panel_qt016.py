"""QT-016 tests for Diagnostics panel rendering.

Covers:
  - Text population from diagnostics dict
  - Histogram + mask axes presence with valid rmse_map (horizontal 1x2 layout)
  - Graceful behavior with missing/invalid rmse_map
  - No stale artists after repeated updates
  - ObjectName stability
  - Horizontal subplot layout (histogram LEFT, quality mask RIGHT)
"""

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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp_instance():
    """Return a shared QApplication (or skip if PySide6 unavailable)."""
    pytest.importorskip("PySide6", reason="PySide6 is not installed; skipping Qt tests")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv or ["pytest"])
    return app


@pytest.fixture
def panel(qapp_instance):
    """Create a fresh DiagnosticsPanel instance."""
    from app.gui_qt.panels.diagnostics_panel import DiagnosticsPanel

    p = DiagnosticsPanel()
    qapp_instance.processEvents()
    yield p
    p._impl.close()
    qapp_instance.processEvents()


# ---------------------------------------------------------------------------
# Helper: full valid diagnostics payload
# ---------------------------------------------------------------------------

def _make_valid_diagnostics() -> dict:
    return {
        "global_rmse": 0.0312,
        "condition_number": 14.7,
        "n_nan_pixels": 12,
        "n_negative_reflectance": 3,
        "warnings": ["Low SNR in blue channel"],
    }


def _make_valid_rmse_map(h: int = 10, w: int = 10) -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.uniform(0.01, 0.08, size=(h, w)).astype(np.float64)


# ---------------------------------------------------------------------------
# Tests: text population
# ---------------------------------------------------------------------------

def test_text_population_with_full_diagnostics(panel, qapp_instance):
    """All known metric keys render correctly in the stats text."""
    diag = _make_valid_diagnostics()
    panel.show_diagnostics(diag)
    qapp_instance.processEvents()

    text = panel._stats_text.toPlainText()
    assert "Global RMSE: 0.0312" in text
    assert "Condition Number: 14.70" in text
    assert "NaN Pixels: 12" in text
    assert "Negative Reflectance Pixels: 3" in text
    assert "Warnings:" in text
    assert "Low SNR in blue channel" in text


def test_text_population_partial_diagnostics(panel, qapp_instance):
    """Missing keys show N/A placeholders."""
    panel.show_diagnostics({"global_rmse": 0.05})
    qapp_instance.processEvents()

    text = panel._stats_text.toPlainText()
    assert "Global RMSE: 0.0500" in text
    assert "Condition Number: N/A" in text
    assert "NaN Pixels: N/A" in text


def test_text_population_empty_diagnostics(panel, qapp_instance):
    """Empty dict shows placeholder text."""
    panel.show_diagnostics({})
    qapp_instance.processEvents()

    text = panel._stats_text.toPlainText()
    assert "No diagnostics data available." in text


def test_text_population_none_diagnostics(panel, qapp_instance):
    """None diagnostics shows placeholder text."""
    panel.show_diagnostics(None)
    qapp_instance.processEvents()

    text = panel._stats_text.toPlainText()
    assert "No diagnostics data available." in text


def test_text_population_invalid_values(panel, qapp_instance):
    """Non-numeric values are handled gracefully."""
    panel.show_diagnostics({
        "global_rmse": "not_a_number",
        "condition_number": None,
        "n_nan_pixels": "abc",
    })
    qapp_instance.processEvents()

    text = panel._stats_text.toPlainText()
    assert "Global RMSE: N/A" in text
    assert "Condition Number: N/A" in text
    assert "NaN Pixels: N/A" in text


# ---------------------------------------------------------------------------
# Tests: histogram + mask axes with valid data
# ---------------------------------------------------------------------------

def test_histogram_and_mask_axes_with_valid_rmse_map(panel, qapp_instance):
    """Valid rmse_map produces two axes with actual plot content."""
    panel.set_data({
        "diagnostics": _make_valid_diagnostics(),
        "rmse_map": _make_valid_rmse_map(),
    })
    qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes) == 2

    # Left axis: histogram
    hist_ax = fig.axes[0]
    assert "RMSE Histogram" in hist_ax.get_title()
    assert len(hist_ax.patches) > 0  # histogram bars
    assert len(hist_ax.lines) >= 2   # median + threshold lines

    # Right axis: quality mask
    mask_ax = fig.axes[1]
    assert "Quality Mask" in mask_ax.get_title()
    assert len(mask_ax.images) > 0   # imshow output


def test_horizontal_subplot_layout(panel, qapp_instance):
    """Subplots are arranged 1x2 (horizontal), not 2x1 (vertical)."""
    panel.set_data({
        "diagnostics": _make_valid_diagnostics(),
        "rmse_map": _make_valid_rmse_map(),
    })
    qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes) == 2

    hist_ax = fig.axes[0]
    mask_ax = fig.axes[1]

    hist_pos = hist_ax.get_position()
    mask_pos = mask_ax.get_position()

    # In a 1x2 layout: left axis x0 < right axis x0, and each axis occupies
    # roughly half the figure width. In a 2x1 layout both would span ~full width.
    assert hist_pos.x0 < mask_pos.x0, "Histogram should be on the left"
    # Each axis width should be < 0.6 of figure width (side-by-side, not full-width)
    assert hist_pos.width < 0.6, "Histogram axis should not span full width"
    assert mask_pos.width < 0.6, "Mask axis should not span full width"
    # Y-centers should be approximately aligned (same row)
    hist_y_center = (hist_pos.y0 + hist_pos.y1) / 2
    mask_y_center = (mask_pos.y0 + mask_pos.y1) / 2
    assert abs(hist_y_center - mask_y_center) < 0.05, "Axes should share the same row"
    # Each axis width should be < 0.6 of figure width (side-by-side, not full-width)
    assert hist_pos.width < 0.6, "Histogram axis should not span full width"
    assert mask_pos.width < 0.6, "Mask axis should not span full width"


def test_set_data_flat_dict_with_rmse_map(panel, qapp_instance):
    """Flat dict (no 'diagnostics' nesting) still works."""
    flat = _make_valid_diagnostics()
    flat["rmse_map"] = _make_valid_rmse_map()
    panel.set_data(flat)
    qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes) == 2
    assert len(fig.axes[0].patches) > 0
    assert len(fig.axes[1].images) > 0


def test_show_diagnostics_without_rmse_map(panel, qapp_instance):
    """show_diagnostics alone (no rmse_map) renders placeholder axes."""
    panel.show_diagnostics(_make_valid_diagnostics())
    qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes) == 2
    # Both axes should contain placeholder text, not real plots
    for ax in fig.axes:
        assert len(ax.patches) == 0
        assert len(ax.images) == 0


# ---------------------------------------------------------------------------
# Tests: graceful behavior with missing/invalid rmse_map
# ---------------------------------------------------------------------------

def test_missing_rmse_map_shows_placeholder(panel, qapp_instance):
    """No rmse_map -> placeholder text on both axes, no crash."""
    panel.set_data({"diagnostics": _make_valid_diagnostics()})
    qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes) == 2
    for ax in fig.axes:
        texts = [t.get_text() for t in ax.texts]
        assert any("no data" in t.lower() for t in texts), f"Expected placeholder in {ax.get_title()}"


def test_none_rmse_map(panel, qapp_instance):
    """Explicit None rmse_map is treated as missing."""
    panel.set_data({"diagnostics": _make_valid_diagnostics(), "rmse_map": None})
    qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes) == 2


def test_empty_rmse_map(panel, qapp_instance):
    """Zero-size array is treated as invalid."""
    panel.set_data({
        "diagnostics": _make_valid_diagnostics(),
        "rmse_map": np.array([]).reshape(0, 0),
    })
    qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes) == 2


def test_1d_rmse_map_is_rejected(panel, qapp_instance):
    """1-D array is not a valid map."""
    panel.set_data({
        "diagnostics": _make_valid_diagnostics(),
        "rmse_map": np.array([0.1, 0.2, 0.3]),
    })
    qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes) == 2
    for ax in fig.axes:
        assert len(ax.images) == 0


def test_non_numeric_rmse_map(panel, qapp_instance):
    """Non-numeric data is handled gracefully."""
    panel.set_data({
        "diagnostics": _make_valid_diagnostics(),
        "rmse_map": "not_an_array",
    })
    qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes) == 2


def test_set_data_non_dict(panel, qapp_instance):
    """Non-dict input resets state without crash."""
    panel.set_data("garbage")
    qapp_instance.processEvents()

    text = panel._stats_text.toPlainText()
    assert "No diagnostics data available." in text


# ---------------------------------------------------------------------------
# Tests: no stale artists after repeated updates
# ---------------------------------------------------------------------------

def test_no_stale_artists_after_repeated_updates(panel, qapp_instance):
    """Each update clears the figure; no duplicate axes accumulate."""
    rmse_map = _make_valid_rmse_map()
    diag = _make_valid_diagnostics()

    for _ in range(5):
        panel.set_data({"diagnostics": diag, "rmse_map": rmse_map})
        qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes) == 2, f"Expected 2 axes after repeated updates, got {len(fig.axes)}"


def test_transition_valid_to_invalid_clears_artists(panel, qapp_instance):
    """Going from valid data to no data clears histogram bars and images."""
    # First: valid data
    panel.set_data({
        "diagnostics": _make_valid_diagnostics(),
        "rmse_map": _make_valid_rmse_map(),
    })
    qapp_instance.processEvents()

    fig = panel._canvas.figure
    assert len(fig.axes[0].patches) > 0
    assert len(fig.axes[1].images) > 0

    # Then: no rmse_map
    panel.set_data({"diagnostics": _make_valid_diagnostics()})
    qapp_instance.processEvents()

    assert len(fig.axes) == 2
    assert len(fig.axes[0].patches) == 0
    assert len(fig.axes[1].images) == 0


# ---------------------------------------------------------------------------
# Tests: objectName stability
# ---------------------------------------------------------------------------

def test_object_names_unchanged(panel):
    """All stable objectNames are present and correct."""
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QGroupBox, QTextEdit, QWidget

    root = panel._impl
    assert root.objectName() == "DiagnosticsPanel"

    stats_frame = root.findChild(QGroupBox, "stats_frame")
    assert stats_frame is not None

    stats_text = root.findChild(QTextEdit, "stats_text")
    assert stats_text is not None

    canvas_widget = root.findChild(QWidget, "diag_canvas")
    assert canvas_widget is not None


# ---------------------------------------------------------------------------
# Tests: refresh() standalone
# ---------------------------------------------------------------------------

def test_refresh_with_no_prior_data(panel, qapp_instance):
    """Calling refresh() on a fresh panel does not crash."""
    panel.refresh()
    qapp_instance.processEvents()

    text = panel._stats_text.toPlainText()
    assert "No diagnostics data available." in text

    fig = panel._canvas.figure
    assert len(fig.axes) == 2


def test_refresh_after_set_data(panel, qapp_instance):
    """refresh() re-renders with previously set data."""
    panel.set_data({
        "diagnostics": _make_valid_diagnostics(),
        "rmse_map": _make_valid_rmse_map(),
    })
    qapp_instance.processEvents()

    # Mutate the text widget to simulate stale state
    panel._stats_text.setPlainText("STALE")

    panel.refresh()
    qapp_instance.processEvents()

    text = panel._stats_text.toPlainText()
    assert "STALE" not in text
    assert "Global RMSE: 0.0312" in text
