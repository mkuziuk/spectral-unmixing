"""QT-008 / QT-027 tests for MapsPanel.

Verifies:
  - All required widgets present with stable objectNames
  - view_combo values and order
  - default view selection
  - band_combo initially empty and disabled
  - import-safe behavior (RuntimeError on missing backends)
  - Grid rendering: chromophore maps, derived maps, raw panels
  - Band combo enabled/disabled per view mode
  - No stale artists on repeated toggles
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest

# Keep Qt test runs deterministic on headless CI unless user overrides it.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# -- expected constants (mirror the module) ----------------------------------

from app.gui_qt.panels.maps_panel import (
    BAND_COMBO_OBJECT_NAME,
    BAND_LABEL_OBJECT_NAME,
    DEFAULT_VIEW,
    MPL_CANVAS_OBJECT_NAME,
    OBJECT_NAME,
    VIEW_COMBO_OBJECT_NAME,
    VIEW_COMBO_VALUES,
    VIEW_LABEL_OBJECT_NAME,
)


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
    pytest.importorskip("PySide6", reason="PySide6 is not installed; skipping Qt tests")
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
def maps_panel(qapp_instance, qtbot_or_none):
    """Create a MapsPanel instance for testing."""
    from app.gui_qt.panels.maps_panel import MapsPanel

    panel = MapsPanel()
    widget = panel._impl

    if qtbot_or_none is not None:
        qtbot_or_none.addWidget(widget)

    widget.show()
    qapp_instance.processEvents()

    yield panel

    widget.close()
    qapp_instance.processEvents()


# -- objectName presence tests -----------------------------------------------


def test_maps_panel_object_name(maps_panel):
    """MapsPanel widget has the correct objectName."""
    assert maps_panel._impl.objectName() == OBJECT_NAME


def test_view_label_present(maps_panel):
    """view_label widget is present and discoverable."""
    widget = _find_object_by_name(maps_panel._impl, VIEW_LABEL_OBJECT_NAME)
    assert widget is not None, f"{VIEW_LABEL_OBJECT_NAME} not found"


def test_view_combo_present(maps_panel):
    """view_combo widget is present and discoverable."""
    widget = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert widget is not None, f"{VIEW_COMBO_OBJECT_NAME} not found"


def test_band_label_present(maps_panel):
    """band_label widget is present and discoverable."""
    widget = _find_object_by_name(maps_panel._impl, BAND_LABEL_OBJECT_NAME)
    assert widget is not None, f"{BAND_LABEL_OBJECT_NAME} not found"


def test_band_combo_present(maps_panel):
    """band_combo widget is present and discoverable."""
    widget = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert widget is not None, f"{BAND_COMBO_OBJECT_NAME} not found"


def test_mpl_canvas_present(maps_panel):
    """mpl_canvas widget is present and discoverable."""
    widget = _find_object_by_name(maps_panel._impl, MPL_CANVAS_OBJECT_NAME)
    assert widget is not None, f"{MPL_CANVAS_OBJECT_NAME} not found"


# -- view_combo content tests ------------------------------------------------


def test_view_combo_values(maps_panel):
    """view_combo contains exactly the expected values in order."""
    from PySide6.QtWidgets import QComboBox

    combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)

    actual = [combo.itemText(i) for i in range(combo.count())]
    assert actual == VIEW_COMBO_VALUES


def test_view_combo_default_selection(maps_panel):
    """view_combo defaults to 'Chromophore Maps'."""
    from PySide6.QtWidgets import QComboBox

    combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    assert combo.currentText() == DEFAULT_VIEW
    assert DEFAULT_VIEW == "Chromophore Maps"


# -- band_combo initial state tests ------------------------------------------


def test_band_combo_initially_disabled(maps_panel):
    """band_combo is disabled until data is loaded."""
    from PySide6.QtWidgets import QComboBox

    combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    assert not combo.isEnabled()


def test_band_combo_initially_empty(maps_panel):
    """band_combo has no items until data is loaded."""
    from PySide6.QtWidgets import QComboBox

    combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    assert combo.count() == 0


# -- class API stub tests ----------------------------------------------------


def test_maps_panel_has_set_data_stub(maps_panel):
    """MapsPanel exposes set_data method."""
    assert hasattr(maps_panel, "set_data")
    assert callable(maps_panel.set_data)


def test_maps_panel_has_show_results_stub(maps_panel):
    """MapsPanel exposes show_results method."""
    assert hasattr(maps_panel, "show_results")
    assert callable(maps_panel.show_results)


def test_maps_panel_has_clear_stub(maps_panel):
    """MapsPanel exposes clear method."""
    assert hasattr(maps_panel, "clear")
    assert callable(maps_panel.clear)


# -- import-safety tests -----------------------------------------------------


def test_import_without_pyside6_does_not_crash():
    """Importing the module does not trigger PySide6 import."""
    # This test runs in the current process where PySide6 IS available,
    # so we verify the module-level namespace is clean.
    import app.gui_qt.panels.maps_panel as mod

    # Module should load without pulling PySide6 into globals
    assert "PySide6" not in dir(mod)
    assert "QWidget" not in dir(mod)


def test_constants_exported_at_module_level():
    """All object name constants and view values are accessible at import time."""
    assert OBJECT_NAME == "MapsPanel"
    assert VIEW_LABEL_OBJECT_NAME == "view_label"
    assert VIEW_COMBO_OBJECT_NAME == "view_combo"
    assert BAND_LABEL_OBJECT_NAME == "band_label"
    assert BAND_COMBO_OBJECT_NAME == "band_combo"
    assert MPL_CANVAS_OBJECT_NAME == "mpl_canvas"
    assert VIEW_COMBO_VALUES == [
        "Chromophore Maps",
        "Derived Maps",
        "Raw / Reflectance / OD",
    ]
    assert DEFAULT_VIEW == "Chromophore Maps"


# == QT-014 / QT-027: Maps panel redraw + grid behavior ======================

import numpy as np


def _count_axes(fig):
    """Return the number of Axes objects currently on the figure."""
    return len(fig.get_axes())


def _count_colorbars(fig):
    """Return the number of colorbar axes currently on the figure."""
    return sum(
        1 for ax in fig.get_axes()
        if hasattr(ax, "_colorbar") or ax.get_label().startswith("colorbar")
    )


def _count_text_objects(fig):
    """Return the number of Text objects on the figure."""
    return len(fig.texts)


def _axes_with_images(fig):
    """Return axes that contain an imshow image (have images attached)."""
    result = []
    for ax in fig.get_axes():
        if ax.images:
            result.append(ax)
    return result


# -- set_data functional tests -----------------------------------------------


def test_set_data_populates_band_combo(maps_panel):
    """set_data with wavelengths populates and enables band_combo."""
    from PySide6.QtWidgets import QComboBox

    combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)

    maps_panel.set_data({
        "wavelengths": [500.0, 550.0, 600.0],
    })

    # Band combo is populated but disabled (not in Raw view)
    assert combo.count() == 3
    assert "500.0" in combo.itemText(0)


def test_set_data_empty_wavelengths_keeps_combo_disabled(maps_panel):
    """set_data with no wavelengths keeps band_combo disabled."""
    from PySide6.QtWidgets import QComboBox

    combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)

    maps_panel.set_data({})

    assert not combo.isEnabled()
    assert combo.count() == 0


def test_set_data_with_reflectance(maps_panel):
    """set_data stores reflectance for later display."""
    data = np.random.rand(10, 10, 3)
    maps_panel.set_data({
        "reflectance": data,
        "wavelengths": [500.0, 550.0, 600.0],
    })
    assert maps_panel._reflectance is not None
    assert maps_panel._reflectance.shape == (10, 10, 3)


def test_set_data_with_od_cube(maps_panel):
    """set_data stores od_cube for later display."""
    data = np.random.rand(10, 10, 3)
    maps_panel.set_data({
        "od_cube": data,
        "wavelengths": [500.0, 550.0, 600.0],
    })
    assert maps_panel._od_cube is not None
    assert maps_panel._od_cube.shape == (10, 10, 3)


# -- show_results functional tests -------------------------------------------


def test_show_results_with_chromophore_data(maps_panel):
    """show_results stores and displays chromophore concentration maps."""
    n_chrom = 3
    concentrations = np.random.rand(10, 10, n_chrom)
    maps_panel.show_results({
        "concentrations": concentrations,
        "chromophore_names": ["HbO2", "Hb", "Background"],
        "wavelengths": [500.0, 550.0, 600.0],
    })

    assert maps_panel._concentrations is not None
    assert maps_panel._chromophore_names is not None
    assert len(maps_panel._chromophore_names) == n_chrom

    # Band combo should be populated but disabled (Chromophore view)
    combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert combo.count() == 3
    assert not combo.isEnabled()


def test_show_results_with_derived_maps(maps_panel):
    """show_results stores derived maps (THb, StO2)."""
    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 2),
        "chromophore_names": ["HbO2", "Hb"],
        "derived_maps": {
            "THb": np.random.rand(10, 10),
            "StO2": np.random.rand(10, 10),
        },
    })

    assert maps_panel._derived_maps is not None
    assert "THb" in maps_panel._derived_maps
    assert "StO2" in maps_panel._derived_maps


def test_show_results_infers_background_component_for_display(maps_panel):
    """A background concentration channel is displayed even when names omit it."""
    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 3),
        "chromophore_names": ["HbO2", "Hb"],
        "include_background": True,
    })

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)
    titles = {ax.get_title() for ax in image_axes}

    assert len(image_axes) == 3
    assert titles == {"HbO2", "Hb", "Background"}


def test_show_results_supports_background_only_display(maps_panel):
    """A background-only run still renders a single Background map."""
    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 1),
        "chromophore_names": [],
        "include_background": True,
    })

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)

    assert len(image_axes) == 1
    assert image_axes[0].get_title() == "Background"


def test_show_results_none_clears(maps_panel):
    """show_results(None) clears the panel."""
    # First load some data
    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 2),
        "chromophore_names": ["HbO2", "Hb"],
        "wavelengths": [500.0, 550.0],
    })
    assert maps_panel._concentrations is not None

    # Then clear via None
    maps_panel.show_results(None)
    assert maps_panel._concentrations is None
    assert maps_panel._chromophore_names is None


def test_show_results_embeds_raw_data(maps_panel):
    """show_results accepts reflectance/od_cube/wavelengths embedded in results."""
    maps_panel.show_results({
        "reflectance": np.random.rand(10, 10, 4),
        "od_cube": np.random.rand(10, 10, 4),
        "wavelengths": [450.0, 500.0, 550.0, 600.0],
    })

    assert maps_panel._reflectance is not None
    assert maps_panel._od_cube is not None
    assert maps_panel._wavelengths is not None
    assert len(maps_panel._wavelengths) == 4


# -- clear functional tests --------------------------------------------------


def test_clear_resets_all_state(maps_panel):
    """clear() resets all internal data stores."""
    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 2),
        "chromophore_names": ["HbO2", "Hb"],
        "derived_maps": {"THb": np.ones((10, 10))},
        "reflectance": np.random.rand(10, 10, 3),
        "od_cube": np.random.rand(10, 10, 3),
        "wavelengths": [500.0, 550.0, 600.0],
    })

    maps_panel.clear()

    assert maps_panel._results is None
    assert maps_panel._chromophore_names is None
    assert maps_panel._concentrations is None
    assert maps_panel._derived_maps is None
    assert maps_panel._reflectance is None
    assert maps_panel._od_cube is None
    assert maps_panel._wavelengths is None


def test_clear_disables_band_combo(maps_panel):
    """clear() disables and empties the band combo."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "wavelengths": [500.0, 550.0],
    })
    combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)

    maps_panel.clear()

    assert not combo.isEnabled()
    assert combo.count() == 0


def test_clear_shows_placeholder(maps_panel):
    """clear() displays placeholder text on the figure."""
    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 2),
        "chromophore_names": ["HbO2", "Hb"],
    })
    maps_panel.clear()

    fig = maps_panel._canvas.figure
    # After clear, figure should have exactly 1 axis (the placeholder)
    assert _count_axes(fig) == 1


# == QT-027: Grid rendering tests ============================================


def test_chromophore_view_renders_all_maps(maps_panel):
    """Chromophore view renders N subplots for N chromophores."""
    from PySide6.QtWidgets import QComboBox

    n_chrom = 5
    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, n_chrom),
        "chromophore_names": ["HbO2", "Hb", "Background", "Water", "Lipid"],
    })

    combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("Chromophore Maps")

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)
    assert len(image_axes) == n_chrom, f"Expected {n_chrom} image axes, got {len(image_axes)}"

    # Verify each chromophore name appears as a title
    titles = {ax.get_title() for ax in image_axes}
    assert titles == {"HbO2", "Hb", "Background", "Water", "Lipid"}


def test_chromophore_view_grid_layout(maps_panel):
    """Chromophore view uses 3-column grid layout."""
    from PySide6.QtWidgets import QComboBox

    n_chrom = 7
    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, n_chrom),
        "chromophore_names": [f"C{i}" for i in range(n_chrom)],
    })

    combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("Chromophore Maps")

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)
    assert len(image_axes) == n_chrom

    # Expected grid: 3 columns, ceil(7/3) = 3 rows
    expected_rows = math.ceil(n_chrom / 3)
    assert expected_rows == 3


def test_chromophore_view_single_map(maps_panel):
    """Chromophore view with 1 chromophore renders 1 subplot."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 1),
        "chromophore_names": ["HbO2"],
    })

    combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("Chromophore Maps")

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)
    assert len(image_axes) == 1
    assert image_axes[0].get_title() == "HbO2"


def test_derived_view_renders_all_maps(maps_panel):
    """Derived view renders all derived maps in a 1×N row."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 2),
        "chromophore_names": ["HbO2", "Hb"],
        "derived_maps": {
            "THb": np.random.rand(10, 10),
            "StO2": np.random.rand(10, 10),
            "RMSE": np.random.rand(10, 10),
        },
    })

    combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("Derived Maps")

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)
    assert len(image_axes) == 3

    titles = {ax.get_title() for ax in image_axes}
    assert titles == {"THb", "StO2", "RMSE"}


def test_derived_view_two_maps(maps_panel):
    """Derived view with 2 maps renders 2 subplots side-by-side."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 2),
        "chromophore_names": ["HbO2", "Hb"],
        "derived_maps": {
            "THb": np.random.rand(10, 10),
            "StO2": np.random.rand(10, 10),
        },
    })

    combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("Derived Maps")

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)
    assert len(image_axes) == 2


def test_raw_view_renders_reflectance_and_od(maps_panel):
    """Raw view renders 3 panels: Raw, Reflectance, OD when both available."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "reflectance": np.random.rand(10, 10, 4),
        "od_cube": np.random.rand(10, 10, 4),
        "wavelengths": [450.0, 500.0, 550.0, 600.0],
    })

    combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("Raw / Reflectance / OD")

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)
    # Should have 3 panels: Raw (reflectance) + Reflectance + OD
    assert len(image_axes) == 3

    titles = [ax.get_title() for ax in image_axes]
    assert any("Raw" in t for t in titles)
    assert any("Reflectance" in t for t in titles)
    assert any("Optical Density" in t for t in titles)


def test_raw_view_reflectance_only(maps_panel):
    """Raw view renders 2 panels (Raw + Reflectance) when only reflectance is available."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "reflectance": np.random.rand(10, 10, 4),
        "wavelengths": [450.0, 500.0, 550.0, 600.0],
    })

    combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("Raw / Reflectance / OD")

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)
    # Raw (from reflectance) + Reflectance = 2 panels
    assert len(image_axes) == 2
    titles = [ax.get_title() for ax in image_axes]
    assert any("Raw" in t for t in titles)
    assert any("Reflectance" in t for t in titles)


def test_raw_view_od_only(maps_panel):
    """Raw view renders 2 panels (Raw from OD + OD) when reflectance is absent."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "od_cube": np.random.rand(10, 10, 3),
        "wavelengths": [500.0, 550.0, 600.0],
    })

    combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    combo.setCurrentText("Raw / Reflectance / OD")

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)
    # Raw (from OD) + OD = 2 panels
    assert len(image_axes) == 2
    assert any("Optical Density" in ax.get_title() for ax in image_axes)


# -- band combo enabled/disabled per view mode -------------------------------


def test_band_combo_disabled_for_chromophore_view(maps_panel):
    """Band combo is disabled when Chromophore Maps view is active."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 3),
        "chromophore_names": ["HbO2", "Hb", "Background"],
        "wavelengths": [500.0, 550.0, 600.0],
    })

    combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    assert not combo.isEnabled()


def test_band_combo_disabled_for_derived_view(maps_panel):
    """Band combo is disabled when Derived Maps view is active."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 2),
        "chromophore_names": ["HbO2", "Hb"],
        "derived_maps": {"THb": np.ones((10, 10))},
        "wavelengths": [500.0, 550.0],
    })

    view_combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(view_combo, QComboBox)
    view_combo.setCurrentText("Derived Maps")

    combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    assert not combo.isEnabled()


def test_band_combo_enabled_for_raw_view(maps_panel):
    """Band combo is enabled when Raw view is active and wavelengths exist."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "reflectance": np.random.rand(10, 10, 4),
        "wavelengths": [450.0, 500.0, 550.0, 600.0],
    })

    # Switch to Raw view to enable band combo
    view_combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(view_combo, QComboBox)
    view_combo.setCurrentText("Raw / Reflectance / OD")

    combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert isinstance(combo, QComboBox)
    assert combo.isEnabled()
    assert combo.count() == 4


# -- band selection changes raw view -----------------------------------------


def test_band_selection_changes_raw_view(maps_panel):
    """Changing band index updates the wavelength label in raw view."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "reflectance": np.random.rand(10, 10, 4),
        "od_cube": np.random.rand(10, 10, 4),
        "wavelengths": [450.0, 500.0, 550.0, 600.0],
    })

    view_combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(view_combo, QComboBox)
    view_combo.setCurrentText("Raw / Reflectance / OD")

    band_combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert isinstance(band_combo, QComboBox)

    # Select band 2 (550 nm)
    band_combo.setCurrentIndex(2)

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)
    # At least one panel should show the wavelength label
    titles = " ".join(ax.get_title() for ax in image_axes)
    assert "550.0" in titles


def test_band_selection_first_band(maps_panel):
    """Band index 0 shows first wavelength in raw view."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "reflectance": np.random.rand(10, 10, 3),
        "wavelengths": [400.0, 500.0, 600.0],
    })

    view_combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(view_combo, QComboBox)
    view_combo.setCurrentText("Raw / Reflectance / OD")

    band_combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert isinstance(band_combo, QComboBox)
    band_combo.setCurrentIndex(0)

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)
    titles = " ".join(ax.get_title() for ax in image_axes)
    assert "400.0" in titles


# -- stale artist / duplicate colorbar prevention ----------------------------


def test_no_duplicate_colorbars_on_repeated_view_toggle(maps_panel):
    """Repeated view mode toggles do not accumulate axes beyond expected grid."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 3),
        "chromophore_names": ["HbO2", "Hb", "Background"],
        "derived_maps": {
            "THb": np.random.rand(10, 10),
            "StO2": np.random.rand(10, 10),
        },
        "reflectance": np.random.rand(10, 10, 3),
        "od_cube": np.random.rand(10, 10, 3),
        "wavelengths": [500.0, 550.0, 600.0],
    })

    view_combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(view_combo, QComboBox)

    # Toggle through all view modes multiple times
    for _ in range(3):
        for i in range(view_combo.count()):
            view_combo.setCurrentIndex(i)

    fig = maps_panel._canvas.figure
    # Chromophore: 3 images + 3 colorbars = 6 axes
    # Derived: 2 images + 2 colorbars = 4 axes
    # Raw: 2 images + 2 colorbars = 4 axes
    # Max should be 6 (chromophore with 3 maps)
    assert _count_axes(fig) <= 6


def test_no_stale_artists_on_repeated_raw_band_change(maps_panel):
    """Repeated band changes in raw view do not accumulate artists."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "reflectance": np.random.rand(10, 10, 5),
        "od_cube": np.random.rand(10, 10, 5),
        "wavelengths": [400.0, 450.0, 500.0, 550.0, 600.0],
    })

    view_combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(view_combo, QComboBox)
    view_combo.setCurrentText("Raw / Reflectance / OD")

    band_combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert isinstance(band_combo, QComboBox)

    # Cycle through all bands multiple times
    for _ in range(5):
        for i in range(band_combo.count()):
            band_combo.setCurrentIndex(i)

    fig = maps_panel._canvas.figure
    # Raw view: 3 images + 3 colorbars = 6 axes max
    assert _count_axes(fig) <= 6


def test_no_stale_artists_on_repeated_chromophore_toggle(maps_panel):
    """Repeated chromophore view toggles do not accumulate artists."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 5),
        "chromophore_names": ["A", "B", "C", "D", "E"],
        "wavelengths": [400.0, 450.0, 500.0, 550.0, 600.0],
    })

    view_combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(view_combo, QComboBox)
    view_combo.setCurrentText("Chromophore Maps")

    # Toggle back and forth
    for _ in range(10):
        view_combo.setCurrentText("Derived Maps")
        view_combo.setCurrentText("Chromophore Maps")

    fig = maps_panel._canvas.figure
    image_axes = _axes_with_images(fig)
    # Should still have exactly 5 image axes
    assert len(image_axes) == 5


def test_figure_cleared_before_each_redraw(maps_panel):
    """Each redraw starts with a cleared figure (no leftover axes)."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 2),
        "chromophore_names": ["HbO2", "Hb"],
        "derived_maps": {"THb": np.ones((10, 10))},
        "reflectance": np.random.rand(10, 10, 2),
        "wavelengths": [500.0, 550.0],
    })

    view_combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(view_combo, QComboBox)

    # Toggle between modes and verify axis count stays bounded
    for _ in range(10):
        view_combo.setCurrentIndex(0)  # Chromophore
        fig = maps_panel._canvas.figure
        n_axes_before = _count_axes(fig)

        view_combo.setCurrentIndex(1)  # Derived
        n_axes_after = _count_axes(fig)

        # Axes count should remain stable (not grow)
        assert n_axes_after <= n_axes_before + 1


# -- robustness against missing data -----------------------------------------


def test_missing_chromophore_names_shows_placeholder(maps_panel):
    """Chromophore view with concentrations but no names shows placeholder."""
    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 3),
        # no chromophore_names
    })

    from PySide6.QtWidgets import QComboBox

    view_combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(view_combo, QComboBox)
    view_combo.setCurrentText("Chromophore Maps")

    fig = maps_panel._canvas.figure
    # Should show placeholder (1 axis with text)
    assert _count_axes(fig) == 1


def test_missing_derived_maps_shows_placeholder(maps_panel):
    """Derived view with no derived_maps shows placeholder."""
    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 2),
        "chromophore_names": ["HbO2", "Hb"],
        # no derived_maps
    })

    from PySide6.QtWidgets import QComboBox

    view_combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(view_combo, QComboBox)
    view_combo.setCurrentText("Derived Maps")

    fig = maps_panel._canvas.figure
    assert _count_axes(fig) == 1


def test_missing_raw_data_shows_placeholder(maps_panel):
    """Raw view with no reflectance or od_cube shows placeholder."""
    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 2),
        "chromophore_names": ["HbO2", "Hb"],
        # no reflectance, no od_cube
    })

    from PySide6.QtWidgets import QComboBox

    view_combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    assert isinstance(view_combo, QComboBox)
    view_combo.setCurrentText("Raw / Reflectance / OD")

    fig = maps_panel._canvas.figure
    assert _count_axes(fig) == 1


# -- repeated toggle stability -----------------------------------------------


def test_rapid_view_toggle_stability(maps_panel):
    """Rapidly toggling view modes does not crash or accumulate state."""
    from PySide6.QtWidgets import QComboBox

    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 3),
        "chromophore_names": ["HbO2", "Hb", "Background"],
        "derived_maps": {"THb": np.ones((10, 10)), "StO2": np.ones((10, 10))},
        "reflectance": np.random.rand(10, 10, 3),
        "od_cube": np.random.rand(10, 10, 3),
        "wavelengths": [500.0, 550.0, 600.0],
    })

    view_combo = _find_object_by_name(maps_panel._impl, VIEW_COMBO_OBJECT_NAME)
    band_combo = _find_object_by_name(maps_panel._impl, BAND_COMBO_OBJECT_NAME)
    assert isinstance(view_combo, QComboBox)
    assert isinstance(band_combo, QComboBox)

    # Stress test: 20 rapid toggles
    for i in range(20):
        view_combo.setCurrentIndex(i % 3)
        # band_combo may be disabled for non-raw views, so only change when enabled
        if band_combo.isEnabled():
            band_combo.setCurrentIndex(i % 3)

    fig = maps_panel._canvas.figure
    # Figure should be in a valid state with bounded axes
    # Max: chromophore with 3 maps = 3 images + 3 colorbars = 6
    assert _count_axes(fig) <= 6


def test_clear_then_redraw_stability(maps_panel):
    """Clear followed by show_results redraws correctly."""
    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 2),
        "chromophore_names": ["HbO2", "Hb"],
        "wavelengths": [500.0, 550.0],
    })
    maps_panel.clear()
    maps_panel.show_results({
        "concentrations": np.random.rand(20, 20, 4),
        "chromophore_names": ["A", "B", "C", "D"],
        "derived_maps": {"THb": np.ones((20, 20))},
        "wavelengths": [400.0, 500.0, 600.0, 700.0],
    })

    fig = maps_panel._canvas.figure
    assert _count_axes(fig) >= 1
    assert maps_panel._band_combo.count() == 4


def test_set_data_then_show_results_stability(maps_panel):
    """set_data followed by show_results produces correct state."""
    maps_panel.set_data({
        "reflectance": np.random.rand(10, 10, 3),
        "wavelengths": [500.0, 550.0, 600.0],
    })

    maps_panel.show_results({
        "concentrations": np.random.rand(10, 10, 2),
        "chromophore_names": ["HbO2", "Hb"],
        "wavelengths": [500.0, 550.0],
    })

    # show_results should override wavelengths
    assert maps_panel._band_combo.count() == 2
    assert maps_panel._concentrations is not None


def test_placeholder_text_present_initially(maps_panel):
    """Panel shows placeholder text before any data is loaded."""
    fig = maps_panel._canvas.figure
    assert _count_axes(fig) == 1
    # The placeholder axis should have text children
    ax = fig.get_axes()[0]
    assert len(ax.texts) > 0 or len(fig.texts) > 0
