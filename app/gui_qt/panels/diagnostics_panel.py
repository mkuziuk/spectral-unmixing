"""Diagnostics panel for displaying algorithm diagnostics and quality metrics.

Import-safe: PySide6 is deferred until instantiation.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

import numpy as np

from app.gui_qt.mpl.canvas import MplCanvas

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QWidget


OBJECT_NAME: str = "DiagnosticsPanel"

# Stable child objectNames
STATS_FRAME_OBJECT_NAME: str = "stats_frame"
STATS_TEXT_OBJECT_NAME: str = "stats_text"
DIAG_CANVAS_OBJECT_NAME: str = "diag_canvas"

_PLACEHOLDER_TEXT: str = "No diagnostics data available."


class DiagnosticsPanel:
    """Panel for displaying diagnostics information (RMSE histogram, quality mask, metrics)."""

    def __init__(self, parent: Any = None) -> None:
        self._impl = _make_widget()(parent)
        self._impl.setObjectName(OBJECT_NAME)
        self._canvas: Any = None  # MplCanvas instance, set in _setup_ui
        self._stats_text: Any = None  # QTextEdit, set in _setup_ui
        self._diagnostics: dict[str, Any] | None = None
        self._rmse_map: np.ndarray | None = None
        self._setup_ui()

    # -- public interface ----------------------------------------------------

    def set_data(self, data: Any) -> None:
        """Load diagnostic data.

        Accepts either:
          - A dict with a ``"diagnostics"`` key and optional ``"rmse_map"`` key.
          - A flat dict that directly contains diagnostic metrics and/or rmse_map.
        """
        if not isinstance(data, dict):
            self._diagnostics = None
            self._rmse_map = None
            self.refresh()
            return

        # Unnest if wrapped
        self._diagnostics = data.get("diagnostics", data)
        self._rmse_map = data.get("rmse_map")

        self.refresh()

    def show_diagnostics(self, diagnostics: dict[str, Any] | None = None) -> None:
        """Render diagnostic charts and metrics.

        Parameters
        ----------
        diagnostics : dict or None
            Expected keys (all optional):
                global_rmse            : float
                condition_number       : float
                n_nan_pixels           : int
                n_negative_reflectance : int
                warnings               : list[str]
        """
        if diagnostics is not None:
            self._diagnostics = diagnostics
        self.refresh()

    def refresh(self) -> None:
        """Refresh the diagnostics display."""
        self._populate_stats_text()
        self._redraw_canvas()

    # -- internal -----------------------------------------------------------

    def _setup_ui(self) -> None:
        """Set up the user interface.

        Layout (vertical stats, horizontal canvas):
            ┌─ QGroupBox "Quality Metrics" (stats_frame) ─┐
            │  QTextEdit read-only (stats_text)            │
            └──────────────────────────────────────────────┘
            ┌─ MplCanvas with 2 subplots (diag_canvas) ───┐
            │  ax[0] : RMSE histogram  │  ax[1] : Quality mask │
            └──────────────────────────────────────────────┘
        """
        from PySide6.QtWidgets import QGroupBox, QTextEdit, QVBoxLayout

        layout = QVBoxLayout(self._impl)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # -- top: Quality Metrics group --------------------------------------
        stats_frame = QGroupBox("Quality Metrics", self._impl)
        stats_frame.setObjectName(STATS_FRAME_OBJECT_NAME)

        stats_text = QTextEdit(stats_frame)
        stats_text.setObjectName(STATS_TEXT_OBJECT_NAME)
        stats_text.setReadOnly(True)
        stats_text.setPlainText(_PLACEHOLDER_TEXT)
        self._stats_text = stats_text

        frame_layout = QVBoxLayout(stats_frame)
        frame_layout.addWidget(stats_text)

        layout.addWidget(stats_frame, stretch=1)

        # -- bottom: matplotlib canvas (two subplots) ------------------------
        self._canvas = MplCanvas(parent=self._impl)
        self._canvas._impl.setObjectName(DIAG_CANVAS_OBJECT_NAME)

        # Configure two subplots as placeholders
        fig = self._canvas._impl.figure
        fig.clear()
        fig.add_subplot(1, 2, 1).set_title("RMSE Histogram (placeholder)")
        fig.add_subplot(1, 2, 2).set_title("Quality Mask (placeholder)")
        fig.tight_layout()
        self._canvas._impl.draw()

        layout.addWidget(self._canvas._impl, stretch=2)

    # -- stats text population -----------------------------------------------

    def _populate_stats_text(self) -> None:
        """Populate the QTextEdit with quality metrics from diagnostics."""
        if self._stats_text is None:
            return

        diag = self._diagnostics
        if not isinstance(diag, dict) or not diag:
            self._stats_text.setPlainText(_PLACEHOLDER_TEXT)
            return

        lines: list[str] = []

        # Global RMSE
        global_rmse = diag.get("global_rmse")
        if global_rmse is not None:
            try:
                lines.append(f"Global RMSE: {float(global_rmse):.4f}")
            except (TypeError, ValueError):
                lines.append("Global RMSE: N/A")
        else:
            lines.append("Global RMSE: N/A")

        # Condition number
        cond = diag.get("condition_number")
        if cond is not None:
            try:
                lines.append(f"Condition Number: {float(cond):.2f}")
            except (TypeError, ValueError):
                lines.append("Condition Number: N/A")
        else:
            lines.append("Condition Number: N/A")

        # NaN pixels
        n_nan = diag.get("n_nan_pixels")
        if n_nan is not None:
            try:
                lines.append(f"NaN Pixels: {int(n_nan)}")
            except (TypeError, ValueError):
                lines.append("NaN Pixels: N/A")
        else:
            lines.append("NaN Pixels: N/A")

        # Negative reflectance
        n_neg = diag.get("n_negative_reflectance")
        if n_neg is not None:
            try:
                lines.append(f"Negative Reflectance Pixels: {int(n_neg)}")
            except (TypeError, ValueError):
                lines.append("Negative Reflectance Pixels: N/A")
        else:
            lines.append("Negative Reflectance Pixels: N/A")

        # Warnings
        warnings_list = diag.get("warnings")
        if isinstance(warnings_list, (list, tuple)) and len(warnings_list) > 0:
            lines.append("")
            lines.append("Warnings:")
            for w in warnings_list:
                lines.append(f"  - {w}")

        self._stats_text.setPlainText("\n".join(lines))

    # -- canvas redraw -------------------------------------------------------

    def _redraw_canvas(self) -> None:
        """Clear figure and redraw histogram + quality mask."""
        if self._canvas is None:
            return

        fig = self._canvas.figure
        fig.clear()

        rmse_map = self._rmse_map
        has_valid_map = self._is_valid_rmse_map(rmse_map)

        if has_valid_map:
            self._draw_histogram(fig, rmse_map)
            self._draw_quality_mask(fig, rmse_map)
        else:
            self._draw_placeholder_axes(fig)

        fig.tight_layout()
        self._canvas._impl.draw()

    @staticmethod
    def _is_valid_rmse_map(rmse_map: Any) -> bool:
        """Check whether rmse_map is a usable 2-D ndarray."""
        if rmse_map is None:
            return False
        try:
            arr = np.asarray(rmse_map, dtype=float)
        except (TypeError, ValueError):
            return False
        if arr.ndim != 2:
            return False
        if arr.size == 0:
            return False
        return True

    def _draw_histogram(self, fig: Any, rmse_map: np.ndarray) -> None:
        """Draw RMSE histogram on the left subplot."""
        ax = fig.add_subplot(1, 2, 1)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            flat = rmse_map[np.isfinite(rmse_map)]

        if flat.size == 0:
            ax.text(
                0.5,
                0.5,
                "No valid RMSE values",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_title("RMSE Histogram")
            return

        ax.hist(flat, bins="auto", color="steelblue", edgecolor="white")

        # Median line
        median_val = float(np.median(flat))
        ax.axvline(median_val, color="red", linestyle="--", linewidth=1.5, label=f"Median = {median_val:.4f}")

        # 2x median threshold line
        threshold = 2.0 * median_val
        ax.axvline(threshold, color="orange", linestyle="--", linewidth=1.5, label=f"2× Median = {threshold:.4f}")

        ax.set_title("RMSE Histogram")
        ax.set_xlabel("RMSE")
        ax.set_ylabel("Count")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    def _draw_quality_mask(self, fig: Any, rmse_map: np.ndarray) -> None:
        """Draw quality mask (RMSE > 2×median) on the right subplot."""
        ax = fig.add_subplot(1, 2, 2)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            flat = rmse_map[np.isfinite(rmse_map)]

        if flat.size == 0:
            ax.text(
                0.5,
                0.5,
                "No valid RMSE values",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_title("Quality Mask (RMSE > 2×median)")
            return

        median_val = float(np.median(flat))
        threshold = 2.0 * median_val

        # Build binary mask: True where RMSE exceeds 2×median (or is non-finite)
        mask = np.ones_like(rmse_map, dtype=bool)
        finite_mask = np.isfinite(rmse_map)
        mask[finite_mask] = rmse_map[finite_mask] > threshold
        # Non-finite pixels are also flagged
        mask[~finite_mask] = True

        ax.imshow(mask, cmap="RdYlGn_r", origin="lower", interpolation="nearest")
        ax.set_title(f"Quality Mask (RMSE > 2×median = {threshold:.4f})")
        ax.set_axis_off()

        # Annotate counts
        n_bad = int(np.sum(mask))
        n_total = int(mask.size)
        pct = 100.0 * n_bad / n_total if n_total > 0 else 0.0
        ax.text(
            0.02,
            0.98,
            f"Bad: {n_bad}/{n_total} ({pct:.1f}%)",
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
        )

    def _draw_placeholder_axes(self, fig: Any) -> None:
        """Draw placeholder text on both subplots when no valid rmse_map."""
        ax_hist = fig.add_subplot(1, 2, 1)
        ax_hist.text(
            0.5,
            0.5,
            "RMSE Histogram — no data",
            ha="center",
            va="center",
            fontsize=12,
            color="gray",
            transform=ax_hist.transAxes,
        )
        ax_hist.set_title("RMSE Histogram")
        ax_hist.set_axis_off()

        ax_mask = fig.add_subplot(1, 2, 2)
        ax_mask.text(
            0.5,
            0.5,
            "Quality Mask — no data",
            ha="center",
            va="center",
            fontsize=12,
            color="gray",
            transform=ax_mask.transAxes,
        )
        ax_mask.set_title("Quality Mask (RMSE > 2×median)")
        ax_mask.set_axis_off()


# ---------------------------------------------------------------------------
def _make_widget() -> type:
    """Return a QWidget subclass."""
    try:
        from PySide6.QtWidgets import QWidget
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PySide6 is required to instantiate DiagnosticsPanel"
        ) from exc

    class _DiagnosticsWidget(QWidget):
        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)

    return _DiagnosticsWidget
