"""Maps panel for displaying spatial concentration maps.

Import-safe: PySide6 and matplotlib are deferred until instantiation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QWidget


# -- stable object names -----------------------------------------------------

OBJECT_NAME: str = "MapsPanel"
VIEW_LABEL_OBJECT_NAME: str = "view_label"
VIEW_COMBO_OBJECT_NAME: str = "view_combo"
BAND_LABEL_OBJECT_NAME: str = "band_label"
BAND_COMBO_OBJECT_NAME: str = "band_combo"
MPL_CANVAS_OBJECT_NAME: str = "mpl_canvas"

# -- view combo values (order is significant) --------------------------------

VIEW_COMBO_VALUES: list[str] = [
    "Chromophore Maps",
    "Derived Maps",
    "Raw / Reflectance / OD",
]

DEFAULT_VIEW: str = VIEW_COMBO_VALUES[0]

# -- internal view mode keys -------------------------------------------------

_VIEW_CHROMOPHORE: str = "Chromophore Maps"
_VIEW_DERIVED: str = "Derived Maps"
_VIEW_RAW: str = "Raw / Reflectance / OD"

_PLACEHOLDER_TEXT: str = "No data loaded."


class MapsPanel:
    """Panel for displaying spatial concentration maps."""

    def __init__(self, parent: Any = None) -> None:
        self._impl = _make_widget()(parent)
        self._impl.setObjectName(OBJECT_NAME)

        # Internal state
        self._canvas: Any = None
        self._view_combo: Any = None
        self._band_combo: Any = None

        # Data store
        self._results: dict[str, Any] | None = None
        self._chromophore_names: list[str] | None = None
        self._concentrations: Any = None  # np.ndarray | None
        self._derived_maps: dict[str, Any] | None = None
        self._reflectance: Any = None  # np.ndarray | None
        self._od_cube: Any = None  # np.ndarray | None
        self._wavelengths: list[float] | None = None

        self._setup_ui()
        self._show_placeholder()

    # -- public interface ----------------------------------------------------

    def set_data(self, data: dict[str, Any]) -> None:
        """Load raw / intermediate data and populate band selector.

        Expected keys (all optional):
            reflectance : np.ndarray (H, W, N)
            od_cube     : np.ndarray (H, W, N)
            wavelengths : list[float]  (length N)
        """
        self._reflectance = data.get("reflectance")
        self._od_cube = data.get("od_cube")
        self._wavelengths = data.get("wavelengths")

        self._populate_band_combo()
        self._redraw()

    def show_results(self, results: dict[str, Any] | None = None) -> None:
        """Render unmixing result maps.

        Expected keys (all optional):
            concentrations    : np.ndarray (H, W, N_components)
            chromophore_names : list[str]
            derived_maps      : dict[str, np.ndarray]  e.g. {"THb": ..., "StO2": ...}
            reflectance       : np.ndarray (H, W, N)
            od_cube           : np.ndarray (H, W, N)
            wavelengths       : list[float]
        """
        if results is None:
            self.clear()
            return

        self._results = results
        self._chromophore_names = results.get("chromophore_names")
        self._concentrations = results.get("concentrations")
        self._derived_maps = results.get("derived_maps")

        # Also accept raw data embedded in results
        if "reflectance" in results:
            self._reflectance = results["reflectance"]
        if "od_cube" in results:
            self._od_cube = results["od_cube"]
        if "wavelengths" in results:
            self._wavelengths = results["wavelengths"]

        self._populate_band_combo()
        self._redraw()

    def clear(self) -> None:
        """Clear displayed maps and reset internal state."""
        self._results = None
        self._chromophore_names = None
        self._concentrations = None
        self._derived_maps = None
        self._reflectance = None
        self._od_cube = None
        self._wavelengths = None

        # Reset band combo
        if self._band_combo is not None:
            self._band_combo.clear()
            self._band_combo.setEnabled(False)

        self._show_placeholder()

    # -- internal -----------------------------------------------------------

    def _setup_ui(self) -> None:
        """Set up the user interface.

        Layout structure (vertical):
          - top controls row (horizontal): view_label, view_combo, band_label, band_combo
          - center: matplotlib canvas (QtAgg)
          - bottom: NavigationToolbar2QT
        """
        from PySide6.QtWidgets import (
            QComboBox,
            QHBoxLayout,
            QLabel,
            QVBoxLayout,
            QWidget,
        )

        # -- top controls row ------------------------------------------------
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(4, 4, 4, 4)
        controls_layout.setSpacing(8)

        view_label = QLabel("View:", self._impl)
        view_label.setObjectName(VIEW_LABEL_OBJECT_NAME)
        controls_layout.addWidget(view_label)

        view_combo = QComboBox(self._impl)
        view_combo.setObjectName(VIEW_COMBO_OBJECT_NAME)
        view_combo.addItems(VIEW_COMBO_VALUES)
        view_combo.setCurrentText(DEFAULT_VIEW)
        self._view_combo = view_combo
        controls_layout.addWidget(view_combo)

        band_label = QLabel("Band:", self._impl)
        band_label.setObjectName(BAND_LABEL_OBJECT_NAME)
        controls_layout.addWidget(band_label)

        band_combo = QComboBox(self._impl)
        band_combo.setObjectName(BAND_COMBO_OBJECT_NAME)
        band_combo.setEnabled(False)  # disabled until data loaded
        self._band_combo = band_combo
        controls_layout.addWidget(band_combo)

        controls_layout.addStretch()

        # -- matplotlib canvas -----------------------------------------------
        from app.gui_qt.mpl.canvas import MplCanvas

        self._canvas = MplCanvas(parent=self._impl)
        self._canvas._impl.setObjectName(MPL_CANVAS_OBJECT_NAME)
        # Give the canvas a stretchable policy so it fills available space
        self._canvas._impl.setSizePolicy(
            self._canvas._impl.sizePolicy().horizontalPolicy(),
            self._canvas._impl.sizePolicy().verticalPolicy(),
        )

        # -- assemble vertical layout ----------------------------------------
        main_layout = QVBoxLayout(self._impl)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self._canvas._impl, stretch=1)

        self._impl.setLayout(main_layout)

        # -- wire signals (after widgets exist) ------------------------------
        view_combo.currentIndexChanged.connect(self._on_redraw)
        band_combo.currentIndexChanged.connect(self._on_redraw)

    def _show_placeholder(self) -> None:
        """Display placeholder text on the figure."""
        fig = self._canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            _PLACEHOLDER_TEXT,
            ha="center",
            va="center",
            fontsize=14,
            color="gray",
            transform=ax.transAxes,
        )
        ax.set_axis_off()
        fig.tight_layout()
        self._canvas._impl.draw()

    def _populate_band_combo(self) -> None:
        """Populate band combo from available wavelengths."""
        combo = self._band_combo
        if combo is None:
            return

        combo.blockSignals(True)
        combo.clear()

        if self._wavelengths is not None and len(self._wavelengths) > 0:
            for wl in self._wavelengths:
                combo.addItem(f"{wl:.1f} nm")
            combo.setEnabled(True)
            combo.setCurrentIndex(0)
        else:
            combo.setEnabled(False)

        combo.blockSignals(False)

    def _on_redraw(self) -> None:
        """Handle view or band selection change — trigger a full redraw."""
        self._redraw()

    def _redraw(self) -> None:
        """Clear the figure and redraw based on current view mode and band."""
        if self._canvas is None:
            return

        view_mode = self._current_view_mode()
        band_index = self._current_band_index()

        # Update band combo enabled state based on view mode
        self._update_band_combo_state(view_mode)

        # Clear figure to prevent stale artists / duplicate colorbars
        fig = self._canvas.figure
        fig.clear()

        if view_mode == _VIEW_CHROMOPHORE:
            self._draw_chromophore_map(fig)
        elif view_mode == _VIEW_DERIVED:
            self._draw_derived_map(fig)
        elif view_mode == _VIEW_RAW:
            self._draw_raw_band(fig, band_index)
        else:
            self._show_placeholder()
            return

        fig.tight_layout()
        self._canvas._impl.draw()

    # -- view-mode dispatchers -----------------------------------------------

    def _current_view_mode(self) -> str:
        if self._view_combo is not None:
            return self._view_combo.currentText()
        return DEFAULT_VIEW

    def _current_band_index(self) -> int:
        if self._band_combo is not None and self._band_combo.isEnabled():
            return max(0, self._band_combo.currentIndex())
        return 0

    def _update_band_combo_state(self, view_mode: str) -> None:
        """Enable/disable band combo based on view mode.

        Band selector is only relevant for Raw / Reflectance / OD view.
        """
        if self._band_combo is None:
            return
        should_enable = (view_mode == _VIEW_RAW) and (
            self._wavelengths is not None and len(self._wavelengths) > 0
        )
        self._band_combo.setEnabled(should_enable)

    def _draw_chromophore_map(self, fig: Any) -> None:
        """Draw ALL chromophore concentration maps in a grid.

        Layout: 3 columns, rows computed from chromophore count.
        Each subplot shows one chromophore with title and colorbar.
        """
        component_names = self._component_display_names()
        if self._concentrations is None or len(component_names) == 0:
            self._show_placeholder()
            return

        n_chrom = len(component_names)
        ncols = 3
        nrows = (n_chrom + ncols - 1) // ncols  # ceiling division

        for idx, name in enumerate(component_names):
            try:
                data = self._concentrations[:, :, idx]
            except IndexError:
                continue

            ax = fig.add_subplot(nrows, ncols, idx + 1)
            im = ax.imshow(data, cmap="viridis", origin="lower")
            ax.set_title(self._format_map_title(name, data))
            ax.set_axis_off()
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    def _draw_derived_map(self, fig: Any) -> None:
        """Draw ALL derived maps in a 1×N row grid.

        Each subplot shows one derived metric (e.g. THb, StO₂, RMSE)
        with title and colorbar.
        """
        if self._derived_maps is None or len(self._derived_maps) == 0:
            self._show_placeholder()
            return

        keys = list(self._derived_maps.keys())
        n_derived = len(keys)

        for idx, name in enumerate(keys):
            data = self._derived_maps[name]
            if data is None:
                continue

            ax = fig.add_subplot(1, n_derived, idx + 1)
            im = ax.imshow(data, cmap="viridis", origin="lower")
            ax.set_title(self._format_map_title(name, data))
            ax.set_axis_off()
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    def _draw_raw_band(self, fig: Any, band_index: int) -> None:
        """Draw 3 panels side-by-side: Raw, Reflectance, Optical Density.

        The band_index selects which wavelength band to display across all three panels.
        """
        n_bands = 0
        if self._reflectance is not None:
            n_bands = max(n_bands, self._reflectance.shape[2] if self._reflectance.ndim == 3 else 1)
        if self._od_cube is not None:
            n_bands = max(n_bands, self._od_cube.shape[2] if self._od_cube.ndim == 3 else 1)

        if n_bands == 0:
            self._show_placeholder()
            return

        idx = band_index % n_bands

        wl_label = ""
        if self._wavelengths and idx < len(self._wavelengths):
            wl_label = f" @ {self._wavelengths[idx]:.1f} nm"

        # Build the three panels: Raw, Reflectance, OD
        panels: list[tuple[Any | None, str]] = []

        # Panel 1: Raw (prefer reflectance, fall back to OD)
        if self._reflectance is not None:
            raw_data = self._reflectance[:, :, idx] if self._reflectance.ndim == 3 else self._reflectance
            panels.append((raw_data, f"Raw{wl_label}"))
        elif self._od_cube is not None:
            raw_data = self._od_cube[:, :, idx] if self._od_cube.ndim == 3 else self._od_cube
            panels.append((raw_data, f"Raw{wl_label}"))

        # Panel 2: Reflectance
        if self._reflectance is not None:
            ref_data = self._reflectance[:, :, idx] if self._reflectance.ndim == 3 else self._reflectance
            panels.append((ref_data, f"Reflectance{wl_label}"))

        # Panel 3: Optical Density
        if self._od_cube is not None:
            od_data = self._od_cube[:, :, idx] if self._od_cube.ndim == 3 else self._od_cube
            panels.append((od_data, f"Optical Density{wl_label}"))

        if len(panels) == 0:
            self._show_placeholder()
            return

        ncols = len(panels)
        nrows = 1

        for panel_idx, (data, title) in enumerate(panels):
            ax = fig.add_subplot(nrows, ncols, panel_idx + 1)
            if data is None:
                ax.set_axis_off()
                ax.set_title(title)
                continue
            im = ax.imshow(data, cmap="gray", origin="lower")
            ax.set_title(self._format_map_title(title, data))
            ax.set_axis_off()
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    def _component_display_names(self) -> list[str]:
        """Return component names aligned to the concentration cube."""
        if self._concentrations is None:
            return []

        conc_shape = getattr(self._concentrations, "shape", ())
        if len(conc_shape) < 3:
            return []

        names = list(self._chromophore_names or [])
        has_explicit_background_flag = "include_background" in (self._results or {})
        include_background = bool((self._results or {}).get("include_background", True))
        if not names and not has_explicit_background_flag:
            return []
        if include_background and len(names) < conc_shape[2]:
            names.append("Background")
        if len(names) < conc_shape[2]:
            names.extend(
                f"Component {idx + 1}"
                for idx in range(len(names), conc_shape[2])
            )
        return names[: conc_shape[2]]

    @staticmethod
    def _format_map_title(name: str, data: Any) -> str:
        """Format subplot title with nan-safe mean and median statistics."""
        finite = np.asarray(data)[np.isfinite(data)]
        if finite.size == 0:
            return name

        mean_val = float(finite.mean())
        median_val = float(np.median(finite))
        return f"{name}\nμ={mean_val:.3e}, med={median_val:.3e}"


# ---------------------------------------------------------------------------
def _make_widget() -> type:
    """Return a QWidget subclass."""
    try:
        from PySide6.QtWidgets import QWidget
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PySide6 is required to instantiate MapsPanel"
        ) from exc

    class _MapsWidget(QWidget):
        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)

    return _MapsWidget
