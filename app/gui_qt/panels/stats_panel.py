"""Stats panel for summary statistics of unmixing results.

Import-safe: PySide6 is deferred until instantiation.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

import numpy as np

from app.gui_qt.mpl.canvas import MplCanvas, MplToolbar

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QWidget


OBJECT_NAME: str = "StatsPanel"
STAT_LABEL_OBJECT_NAME: str = "stat_label"
STAT_COMBO_OBJECT_NAME: str = "stat_combo"
STAT_CANVAS_OBJECT_NAME: str = "stat_canvas"
STAT_NAV_TOOLBAR_OBJECT_NAME: str = "stat_nav_toolbar"
STAT_OPTIONS: list[str] = ["Mean", "Median"]


class StatsPanel:
    """Panel for displaying summary statistics (mean, std, histograms)."""

    def __init__(self, parent: Any = None) -> None:
        self._impl = _make_widget()(parent)
        self._impl.setObjectName(OBJECT_NAME)
        self._current_res: Any = None
        self._stat_combo: Any = None
        self._setup_ui()

    # -- public interface (stubs) -------------------------------------------

    def refresh(self, stats: dict[str, Any] | None = None) -> None:
        """Refresh the statistics display."""
        if stats is not None:
            self._current_res = stats
        self._redraw()

    def set_data(self, data: Any) -> None:
        """Load data for statistical summary."""
        self._current_res = data
        self._redraw()

    # -- internal -----------------------------------------------------------

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout

        root_layout = QVBoxLayout(self._impl)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        controls_row = QHBoxLayout()

        stat_label = QLabel("Statistic:", self._impl)
        stat_label.setObjectName(STAT_LABEL_OBJECT_NAME)
        controls_row.addWidget(stat_label)

        stat_combo = QComboBox(self._impl)
        stat_combo.setObjectName(STAT_COMBO_OBJECT_NAME)
        stat_combo.setEditable(False)
        stat_combo.addItems(STAT_OPTIONS)
        stat_combo.setCurrentText("Median")
        stat_combo.currentTextChanged.connect(self._on_stat_changed)
        controls_row.addWidget(stat_combo)
        controls_row.addStretch(1)
        self._stat_combo = stat_combo

        root_layout.addLayout(controls_row)

        self._stat_canvas = MplCanvas(self._impl)
        self._stat_canvas._impl.setObjectName(STAT_CANVAS_OBJECT_NAME)
        root_layout.addWidget(self._stat_canvas._impl, 1)

        self._stat_nav_toolbar = MplToolbar(self._stat_canvas, self._impl)
        self._stat_nav_toolbar._impl.setObjectName(STAT_NAV_TOOLBAR_OBJECT_NAME)
        root_layout.addWidget(self._stat_nav_toolbar._impl)

        self._redraw()

    def _on_stat_changed(self, _text: str) -> None:
        """Redraw when statistic type is changed from the combo box."""
        self._redraw()

    def _compute_series(self) -> tuple[np.ndarray, np.ndarray, str] | None:
        """Return (x, y, title_prefix) for current data or None if invalid."""
        res = self._current_res
        if not isinstance(res, dict):
            return None

        wavelengths = np.asarray(res.get("wavelengths"), dtype=float)
        reflectance = np.asarray(res.get("reflectance"), dtype=float)

        if wavelengths.ndim != 1 or wavelengths.size == 0:
            return None
        if reflectance.ndim != 3:
            return None
        if reflectance.shape[2] != wavelengths.size:
            return None

        valid_refl = np.where(np.isfinite(reflectance), reflectance, np.nan)
        stat_choice = self._stat_combo.currentText() if self._stat_combo is not None else "Median"

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            if stat_choice == "Mean":
                stats = np.nanmean(valid_refl, axis=(0, 1))
                title_prefix = "Mean"
            else:
                stats = np.nanmedian(valid_refl, axis=(0, 1))
                title_prefix = "Median"

        return wavelengths, np.asarray(stats, dtype=float), title_prefix

    def _redraw(self) -> None:
        """Clear and redraw the reflectance statistic plot."""
        fig = self._stat_canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)

        series = self._compute_series()
        if series is None:
            ax.text(
                0.5,
                0.5,
                "No valid reflectance data",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_title("Reflectance per Wavelength")
        else:
            wls, stats, title_prefix = series
            ax.plot(wls, stats, marker="o", linestyle="-")
            ax.set_title(f"{title_prefix} Reflectance per Wavelength")

        ax.set_xlabel("Wavelength (nm)")
        ax.set_ylabel("Reflectance")
        ax.grid(True)
        fig.tight_layout()
        self._stat_canvas._impl.draw()


# ---------------------------------------------------------------------------
def _make_widget() -> type:
    """Return a QWidget subclass."""
    try:
        from PySide6.QtWidgets import QWidget
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PySide6 is required to instantiate StatsPanel"
        ) from exc

    class _StatsWidget(QWidget):
        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)

    return _StatsWidget
