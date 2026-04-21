"""QT-009 tests for Pixel Inspector layout shell."""

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


EXPECTED_OBJECT_NAMES = [
    "inspector_splitter",
    "inspector_click_label",
    "img_canvas",
    "spec_canvas",
    "conc_group",
    "conc_text",
]


def _find_object_by_name(root, object_name: str):
    from PySide6.QtCore import QObject

    if root.objectName() == object_name:
        return root

    for child in root.findChildren(QObject):
        if child.objectName() == object_name:
            return child

    return None


@pytest.fixture(scope="session")
def qapp_instance():
    pytest.importorskip("PySide6", reason="PySide6 is not installed; skipping QT-009 tests")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv or ["pytest"])
    return app


@pytest.fixture
def inspector_panel(qapp_instance, request):
    from app.gui_qt.panels.inspector_panel import InspectorPanel

    panel = InspectorPanel()
    widget = panel._impl

    try:
        qtbot = request.getfixturevalue("qtbot")
    except pytest.FixtureLookupError:
        qtbot = None

    if qtbot is not None:
        qtbot.addWidget(widget)

    widget.resize(900, 600)
    widget.show()
    qapp_instance.processEvents()

    yield panel

    widget.close()
    qapp_instance.processEvents()


def test_qt009_layout_object_names_present(inspector_panel):
    missing = [
        object_name
        for object_name in EXPECTED_OBJECT_NAMES
        if _find_object_by_name(inspector_panel._impl, object_name) is None
    ]
    assert not missing, f"Missing expected inspector objectNames: {missing}"


def test_qt009_splitter_orientation_and_ratio(inspector_panel, qapp_instance):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSplitter

    splitter = _find_object_by_name(inspector_panel._impl, "inspector_splitter")
    assert isinstance(splitter, QSplitter)
    assert splitter.orientation() == Qt.Orientation.Horizontal

    qapp_instance.processEvents()
    sizes = splitter.sizes()
    assert len(sizes) == 2
    assert sizes[0] > 0 and sizes[1] > 0
    ratio = sizes[1] / sizes[0]
    assert 1.5 <= ratio <= 2.5, f"Expected right:left near 2:1, got sizes={sizes}"


def test_qt009_concentrations_text_read_only(inspector_panel):
    from PySide6.QtWidgets import QTextEdit

    conc_text = _find_object_by_name(inspector_panel._impl, "conc_text")
    assert isinstance(conc_text, QTextEdit)
    assert conc_text.isReadOnly()


def test_qt009_api_stubs_are_placeholder_safe(inspector_panel):
    inspector_panel.set_data({"dummy": True})
    inspector_panel.refresh()
    inspector_panel.show_diagnostics({"ok": True})


def _make_mock_inspector_data() -> dict[str, object]:
    h, w, n_bands = 4, 5, 4
    n_components = 3
    sample_cube = np.arange(h * w * 2, dtype=float).reshape(h, w, 2)
    od_cube = np.arange(h * w * n_bands, dtype=float).reshape(h, w, n_bands) / 50.0
    fitted_od = od_cube * 0.9
    concentrations = np.arange(h * w * n_components, dtype=float).reshape(h, w, n_components) / 100.0
    rmse_map = np.linspace(0.01, 0.05, h * w, dtype=float).reshape(h, w)

    return {
        "sample_cube": sample_cube,
        "od_cube": od_cube,
        "fitted_od": fitted_od,
        "concentrations": concentrations,
        "rmse_map": rmse_map,
        "wavelengths": np.array([450, 500, 550, 600]),
        "chromophore_names": ["HbO2", "Hb"],
        "include_background": True,
    }


def test_qt015_click_updates_selected_pixel_and_text(inspector_panel, qapp_instance):
    inspector_panel.set_data(_make_mock_inspector_data())
    inspector_panel._handle_canvas_click(x=2.0, y=1.0)
    qapp_instance.processEvents()

    assert inspector_panel._selected_pixel == (1, 2)

    conc_text = _find_object_by_name(inspector_panel._impl, "conc_text")
    body = conc_text.toPlainText()
    assert "Pixel (1, 2)" in body
    assert "HbO2" in body
    assert "Hb" in body
    assert "RMSE" in body


def test_qt015_click_out_of_bounds_is_ignored(inspector_panel, qapp_instance):
    inspector_panel.set_data(_make_mock_inspector_data())
    inspector_panel._handle_canvas_click(x=1.0, y=1.0)
    qapp_instance.processEvents()
    assert inspector_panel._selected_pixel == (1, 1)

    inspector_panel._handle_canvas_click(x=999, y=999)
    qapp_instance.processEvents()
    assert inspector_panel._selected_pixel == (1, 1)


def test_qt015_click_renders_crosshair_and_spectra(inspector_panel, qapp_instance):
    pytest.importorskip("matplotlib", reason="matplotlib backend unavailable")

    inspector_panel.set_data(_make_mock_inspector_data())
    inspector_panel._handle_canvas_click(x=3.0, y=2.0)
    qapp_instance.processEvents()

    img_canvas = _find_object_by_name(inspector_panel._impl, "img_canvas")
    spec_canvas = _find_object_by_name(inspector_panel._impl, "spec_canvas")

    img_fig = getattr(img_canvas, "figure", None)
    spec_fig = getattr(spec_canvas, "figure", None)
    if img_fig is None or spec_fig is None:
        pytest.skip("Inspector canvas fallback active; matplotlib figure not present")

    assert len(img_fig.axes) == 1
    assert len(img_fig.axes[0].lines) >= 2

    assert len(spec_fig.axes) == 2
    # Top subplot: measured + fitted OD rendered as bar charts (not lines)
    assert len(spec_fig.axes[0].patches) >= 2, "Top subplot should have bar artists for measured/fitted OD"
    assert len(spec_fig.axes[0].lines) == 0, "Top subplot should NOT have line artists (use bar charts)"
    # Bottom subplot: residual bars
    assert len(spec_fig.axes[1].patches) > 0, "Bottom subplot should have bar artists for residual"


def test_qt015_spectra_bars_use_categorical_widths(inspector_panel, qapp_instance):
    pytest.importorskip("matplotlib", reason="matplotlib backend unavailable")

    inspector_panel.set_data(_make_mock_inspector_data())
    inspector_panel._handle_canvas_click(x=2.0, y=1.0)
    qapp_instance.processEvents()

    spec_canvas = _find_object_by_name(inspector_panel._impl, "spec_canvas")
    spec_fig = getattr(spec_canvas, "figure", None)
    if spec_fig is None:
        pytest.skip("Inspector canvas fallback active; matplotlib figure not present")

    top_ax, bottom_ax = spec_fig.axes
    top_widths = [patch.get_width() for patch in top_ax.patches]
    bottom_widths = [patch.get_width() for patch in bottom_ax.patches]

    assert top_widths
    assert bottom_widths
    assert min(top_widths) >= 0.35
    assert min(bottom_widths) >= 0.6
    assert [tick.get_text() for tick in bottom_ax.get_xticklabels()] == ["450", "500", "550", "600"]
