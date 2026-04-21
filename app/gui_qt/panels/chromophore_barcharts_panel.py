"""Chromophore summary bar charts across processed samples.

Import-safe: PySide6 is deferred until instantiation.
"""

from __future__ import annotations

import math
import warnings
from typing import TYPE_CHECKING, Any

import numpy as np

from app.gui_qt.mpl.canvas import MplCanvas

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QWidget


OBJECT_NAME: str = "ChromophoreBarChartsPanel"
BAR_CHARTS_CANVAS_OBJECT_NAME: str = "chromophore_barcharts_canvas"
_PLACEHOLDER_TEXT: str = "No valid chromophore concentration data"
_FIGURE_TITLE: str = "Chromophore Comparison Across Samples"


class ChromophoreBarChartsPanel:
    """Panel for per-sample chromophore mean/median bar charts."""

    def __init__(self, parent: Any = None) -> None:
        self._impl = _make_widget()(parent)
        self._impl.setObjectName(OBJECT_NAME)
        self._results: dict[str, dict[str, Any]] = {}
        self._setup_ui()

    def refresh(self, data: Any = None) -> None:
        """Refresh the rendered charts, optionally replacing the data."""
        if data is not None:
            self.set_data(data)
            return
        self._redraw()

    def set_data(self, data: Any) -> None:
        """Load a processed-sample mapping and redraw the figure."""
        self._results = self._coerce_results(data)
        self._redraw()

    def _setup_ui(self) -> None:
        """Set up the panel canvas."""
        from PySide6.QtWidgets import QVBoxLayout

        root_layout = QVBoxLayout(self._impl)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        self._canvas = MplCanvas(self._impl)
        self._canvas._impl.setObjectName(BAR_CHARTS_CANVAS_OBJECT_NAME)
        root_layout.addWidget(self._canvas._impl, 1)

        self._redraw()

    @staticmethod
    def _coerce_results(data: Any) -> dict[str, dict[str, Any]]:
        """Accept either a raw results mapping or a payload with ``samples``."""
        if not isinstance(data, dict):
            return {}

        samples = data.get("samples")
        if isinstance(samples, dict):
            return {str(name): sample for name, sample in samples.items() if isinstance(sample, dict)}

        if "concentrations" in data and isinstance(data.get("chromophore_names"), list):
            return {"Sample": data}

        result_map: dict[str, dict[str, Any]] = {}
        for name, sample in data.items():
            if isinstance(sample, dict) and "concentrations" in sample:
                result_map[str(name)] = sample
        return result_map

    def _compute_chart_data(
        self,
    ) -> tuple[list[str], list[str], np.ndarray, np.ndarray] | None:
        """Return sample names, chromophore names, mean values, and medians."""
        if not self._results:
            return None

        sample_names = list(self._results.keys())
        reference_names: list[str] | None = None
        n_chromophores = 0

        for sample in self._results.values():
            chromophore_names = sample.get("chromophore_names")
            concentrations = np.asarray(sample.get("concentrations"), dtype=float)
            if not isinstance(chromophore_names, list):
                continue
            if concentrations.ndim != 3:
                continue
            n_chromophores = min(len(chromophore_names), concentrations.shape[2])
            if n_chromophores == 0:
                continue
            reference_names = [str(name) for name in chromophore_names[:n_chromophores]]
            break

        if reference_names is None:
            return None

        means = np.full((len(sample_names), n_chromophores), np.nan, dtype=float)
        medians = np.full((len(sample_names), n_chromophores), np.nan, dtype=float)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            for sample_idx, sample_name in enumerate(sample_names):
                concentrations = np.asarray(self._results[sample_name].get("concentrations"), dtype=float)
                if concentrations.ndim != 3:
                    continue

                usable_channels = min(n_chromophores, concentrations.shape[2])
                for chrom_idx in range(usable_channels):
                    channel = np.where(np.isfinite(concentrations[:, :, chrom_idx]), concentrations[:, :, chrom_idx], np.nan)
                    means[sample_idx, chrom_idx] = float(np.nanmean(channel))
                    medians[sample_idx, chrom_idx] = float(np.nanmedian(channel))

        if not np.isfinite(means).any() and not np.isfinite(medians).any():
            return None

        return sample_names, reference_names, means, medians

    def _redraw(self) -> None:
        """Render the per-chromophore mean/median bar charts."""
        fig = self._canvas.figure
        fig.clear()

        chart_data = self._compute_chart_data()
        if chart_data is None:
            ax = fig.add_subplot(111)
            ax.text(
                0.5,
                0.5,
                _PLACEHOLDER_TEXT,
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_title("Chromophore Summary")
            ax.set_xlabel("Samples")
            ax.set_ylabel("Concentration")
            fig.tight_layout()
            self._canvas._impl.draw()
            return

        sample_names, chromophore_names, means, medians = chart_data
        n_chromophores = len(chromophore_names)
        n_cols = min(3, n_chromophores)
        n_rows = int(math.ceil(n_chromophores / n_cols))
        x_positions = np.arange(len(sample_names), dtype=float)
        bar_width = 0.35

        axes = []
        for chrom_idx, chrom_name in enumerate(chromophore_names):
            ax = fig.add_subplot(n_rows, n_cols, chrom_idx + 1)
            ax.bar(x_positions - bar_width / 2, means[:, chrom_idx], bar_width, label="Mean")
            ax.bar(x_positions + bar_width / 2, medians[:, chrom_idx], bar_width, label="Median")
            ax.set_title(f"{chrom_name}: Mean vs Median")
            ax.set_xlabel("Samples")
            ax.set_ylabel("Concentration")
            ax.set_xticks(x_positions)
            ax.set_xticklabels(sample_names, rotation=45, ha="right")
            ax.grid(axis="y", alpha=0.3)
            ax.legend()
            axes.append(ax)

        fig.suptitle(_FIGURE_TITLE)
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
        self._canvas._impl.draw()


def _make_widget() -> type:
    """Return a QWidget subclass."""
    try:
        from PySide6.QtWidgets import QWidget
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PySide6 is required to instantiate ChromophoreBarChartsPanel"
        ) from exc

    class _ChromophoreBarChartsWidget(QWidget):
        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)

    return _ChromophoreBarChartsWidget
