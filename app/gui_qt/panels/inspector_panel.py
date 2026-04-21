"""Inspector panel for examining pixel-level spectral data.

Import-safe: PySide6 is deferred until instantiation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QWidget


OBJECT_NAME: str = "InspectorPanel"

# QT-009 stable object names
INSPECTOR_SPLITTER_OBJECT_NAME: str = "inspector_splitter"
INSPECTOR_CLICK_LABEL_OBJECT_NAME: str = "inspector_click_label"
IMG_CANVAS_OBJECT_NAME: str = "img_canvas"
SPEC_CANVAS_OBJECT_NAME: str = "spec_canvas"
CONC_GROUP_OBJECT_NAME: str = "conc_group"
CONC_TEXT_OBJECT_NAME: str = "conc_text"


class InspectorPanel:
    """Panel for inspecting individual pixel spectra and fit quality."""

    def __init__(self, parent: Any = None) -> None:
        self._impl = _make_widget()(parent)
        self._impl.setObjectName(OBJECT_NAME)

        self._data: dict[str, Any] | None = None
        self._selected_pixel: tuple[int, int] | None = None
        self._img_canvas_widget: Any = None
        self._spec_canvas_widget: Any = None
        self._conc_text_widget: Any = None
        self._click_label_widget: Any = None
        self._img_click_cid: int | None = None

        self._setup_ui()

    # -- public interface (stubs) -------------------------------------------

    def show_diagnostics(self, diagnostics: dict[str, Any] | None = None) -> None:
        """Display fit diagnostics for the selected pixel."""
        return None

    def set_data(self, data: Any) -> None:
        """Load data for inspection."""
        self._data = data if isinstance(data, dict) else None
        self._selected_pixel = None
        self.refresh()

    def refresh(self) -> None:
        """Refresh the inspector view."""
        self._render_image_preview()
        self._render_spectra()
        self._render_concentrations()

    def _on_img_canvas_click(self, event: Any) -> None:
        """Matplotlib button_press_event callback for image canvas."""
        x = getattr(event, "xdata", None)
        y = getattr(event, "ydata", None)
        self._handle_canvas_click(x=x, y=y)

    def _handle_canvas_click(self, x: Any, y: Any) -> None:
        """Update selected pixel using image-canvas data coordinates."""
        if x is None or y is None:
            return

        shape = self._image_shape()
        if shape is None:
            return

        row = int(round(float(y)))
        col = int(round(float(x)))
        height, width = shape
        if row < 0 or col < 0 or row >= height or col >= width:
            return

        self._selected_pixel = (row, col)
        self.refresh()

    # -- internal -----------------------------------------------------------

    def _setup_ui(self) -> None:
        """Set up QT-009 pixel inspector layout shell."""
        from PySide6.QtCore import QTimer, Qt
        from PySide6.QtWidgets import (
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QSplitter,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )

        root_layout = QVBoxLayout(self._impl)
        root_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self._impl)
        splitter.setObjectName(INSPECTOR_SPLITTER_OBJECT_NAME)
        root_layout.addWidget(splitter)

        # -- left: click prompt + image canvas -------------------------------
        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        click_label = QLabel("Click a pixel on the image below:", left)
        click_label.setObjectName(INSPECTOR_CLICK_LABEL_OBJECT_NAME)
        self._click_label_widget = click_label
        left_layout.addWidget(click_label)

        img_canvas_widget = self._build_canvas_widget(left, IMG_CANVAS_OBJECT_NAME)
        self._img_canvas_widget = img_canvas_widget

        # Horizontally center the image canvas within the left pane using a
        # wrapper layout with equal stretch on both sides.  This is more
        # reliable than AlignHCenter because the canvas has an expanding size
        # policy and would otherwise fill the full width.
        img_center_wrapper = QWidget(left)
        img_center_layout = QHBoxLayout(img_center_wrapper)
        img_center_layout.setContentsMargins(0, 0, 0, 0)
        img_center_layout.addStretch(1)
        img_center_layout.addWidget(img_canvas_widget)
        img_center_layout.addStretch(1)
        left_layout.addWidget(img_center_wrapper, stretch=1)

        # Add a stretch after the image wrapper so it stays centered rather
        # than expanding downward to fill unused vertical space.
        left_layout.addStretch(1)

        # -- right: spectra canvas + concentrations --------------------------
        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        spec_canvas_widget = self._build_canvas_widget(right, SPEC_CANVAS_OBJECT_NAME)
        self._spec_canvas_widget = spec_canvas_widget
        right_layout.addWidget(spec_canvas_widget)

        conc_group = QGroupBox("Concentrations", right)
        conc_group.setObjectName(CONC_GROUP_OBJECT_NAME)
        conc_layout = QVBoxLayout(conc_group)

        conc_text = QTextEdit(conc_group)
        conc_text.setObjectName(CONC_TEXT_OBJECT_NAME)
        conc_text.setReadOnly(True)
        self._conc_text_widget = conc_text
        conc_layout.addWidget(conc_text)
        right_layout.addWidget(conc_group)

        splitter.addWidget(left)
        splitter.addWidget(right)

        # Approximate 1:2 left:right initial split.
        splitter.setSizes([400, 800])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        # Re-apply after first layout pass to keep startup ratio stable.
        def _apply_startup_splitter_sizes() -> None:
            try:
                splitter.setSizes([400, 800])
            except RuntimeError:
                # Widget may already be deleted by the time the timer fires.
                return

        QTimer.singleShot(0, _apply_startup_splitter_sizes)

        self._wire_click_handler()
        self.refresh()

    @staticmethod
    def _build_canvas_widget(parent: Any, object_name: str) -> Any:
        """Return a canvas widget, preferring MplCanvas when available."""
        try:
            from app.gui_qt.mpl import MplCanvas

            canvas = MplCanvas(parent)
            widget = canvas._impl
        except Exception:
            # Placeholder fallback keeps shell instantiable without matplotlib
            # or backend/runtime canvas issues during early Qt migration.
            from PySide6.QtWidgets import QFrame

            widget = QFrame(parent)
            widget.setFrameShape(QFrame.Shape.StyledPanel)

        widget.setObjectName(object_name)
        return widget

    def _wire_click_handler(self) -> None:
        """Connect matplotlib click events when canvas supports it."""
        canvas = self._img_canvas_widget
        if canvas is None:
            return

        mpl_connect = getattr(canvas, "mpl_connect", None)
        if not callable(mpl_connect):
            return

        try:
            self._img_click_cid = mpl_connect("button_press_event", self._on_img_canvas_click)
        except Exception:
            self._img_click_cid = None

    def _image_shape(self) -> tuple[int, int] | None:
        """Return image shape (H, W) from available data arrays."""
        if not isinstance(self._data, dict):
            return None

        for key in ("sample_cube", "od_cube", "fitted_od", "concentrations"):
            arr = self._as_array(self._data.get(key))
            if arr is None:
                continue
            if arr.ndim >= 2:
                return int(arr.shape[0]), int(arr.shape[1])

        rmse = self._as_array(self._data.get("rmse_map"))
        if rmse is not None and rmse.ndim >= 2:
            return int(rmse.shape[0]), int(rmse.shape[1])
        return None

    def _as_array(self, value: Any) -> np.ndarray | None:
        """Best-effort conversion to ndarray."""
        if value is None:
            return None
        try:
            return np.asarray(value)
        except Exception:
            return None

    def _canvas_figure(self, canvas_widget: Any) -> Any:
        """Return matplotlib figure for a canvas widget when available."""
        if canvas_widget is None:
            return None
        return getattr(canvas_widget, "figure", None)

    def _safe_draw_canvas(self, canvas_widget: Any) -> None:
        """Redraw canvas if it supports draw()."""
        draw = getattr(canvas_widget, "draw", None)
        if callable(draw):
            try:
                draw()
            except Exception:
                return

    def _render_image_preview(self) -> None:
        """Render left image preview and optional crosshair."""
        fig = self._canvas_figure(self._img_canvas_widget)
        if fig is None:
            return

        fig.clear()
        ax = fig.add_subplot(111)

        image = None
        if isinstance(self._data, dict):
            sample_cube = self._as_array(self._data.get("sample_cube"))
            od_cube = self._as_array(self._data.get("od_cube"))
            fitted_od = self._as_array(self._data.get("fitted_od"))
            rmse_map = self._as_array(self._data.get("rmse_map"))

            if sample_cube is not None and sample_cube.ndim >= 3 and sample_cube.shape[2] > 0:
                image = sample_cube[:, :, 0]
            elif od_cube is not None and od_cube.ndim >= 3 and od_cube.shape[2] > 0:
                image = od_cube[:, :, 0]
            elif fitted_od is not None and fitted_od.ndim >= 3 and fitted_od.shape[2] > 0:
                image = fitted_od[:, :, 0]
            elif rmse_map is not None and rmse_map.ndim >= 2:
                image = rmse_map

        if image is None:
            ax.text(0.5, 0.5, "No image data", transform=ax.transAxes, ha="center", va="center")
            ax.set_axis_off()
            fig.tight_layout()
            self._safe_draw_canvas(self._img_canvas_widget)
            return

        ax.imshow(image, cmap="gray", aspect="equal")
        if self._selected_pixel is not None:
            row, col = self._selected_pixel
            shape = self._image_shape()
            if shape is not None:
                height, width = shape
                if 0 <= row < height and 0 <= col < width:
                    ax.axhline(row, color="red", linewidth=0.8, alpha=0.7)
                    ax.axvline(col, color="red", linewidth=0.8, alpha=0.7)
                    ax.plot(col, row, "r+", markersize=10, markeredgewidth=1.5)
                    ax.set_title(f"Pixel ({row}, {col})", fontsize=10)
                else:
                    ax.set_title("Click a pixel", fontsize=10)
            else:
                ax.set_title("Click a pixel", fontsize=10)
        else:
            ax.set_title("Click a pixel", fontsize=10)

        fig.tight_layout()
        self._safe_draw_canvas(self._img_canvas_widget)

    def _render_spectra(self) -> None:
        """Render measured/fitted/residual spectra for selected pixel."""
        fig = self._canvas_figure(self._spec_canvas_widget)
        if fig is None:
            return

        fig.clear()
        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212)

        if not isinstance(self._data, dict) or self._selected_pixel is None:
            ax1.text(0.5, 0.5, "No pixel selected", transform=ax1.transAxes, ha="center", va="center")
            ax2.text(0.5, 0.5, "Residual unavailable", transform=ax2.transAxes, ha="center", va="center")
            fig.tight_layout()
            self._safe_draw_canvas(self._spec_canvas_widget)
            return

        od_cube = self._as_array(self._data.get("od_cube"))
        fitted_od = self._as_array(self._data.get("fitted_od"))
        row, col = self._selected_pixel
        if (
            od_cube is None
            or fitted_od is None
            or od_cube.ndim < 3
            or fitted_od.ndim < 3
            or od_cube.shape[:2] != fitted_od.shape[:2]
            or od_cube.shape[2] != fitted_od.shape[2]
            or row < 0
            or col < 0
            or row >= od_cube.shape[0]
            or col >= od_cube.shape[1]
        ):
            ax1.text(0.5, 0.5, "Spectra unavailable", transform=ax1.transAxes, ha="center", va="center")
            ax2.text(0.5, 0.5, "Residual unavailable", transform=ax2.transAxes, ha="center", va="center")
            fig.tight_layout()
            self._safe_draw_canvas(self._spec_canvas_widget)
            return

        measured = od_cube[row, col, :]
        fitted = fitted_od[row, col, :]
        residual = measured - fitted

        wavelengths = self._as_array(self._data.get("wavelengths"))
        if wavelengths is None or wavelengths.ndim != 1 or wavelengths.shape[0] != measured.shape[0]:
            x = np.arange(measured.shape[0])
            x_tick_labels = [str(i) for i in x]
            x_axis_label = "Band index"
        else:
            x = wavelengths
            x_tick_labels = [str(int(w)) if float(w).is_integer() else str(float(w)) for w in wavelengths]
            x_axis_label = "LED wavelength (nm)"

        bar_w = 0.35
        ax1.bar(x - bar_w / 2, measured, bar_w, label="Measured OD", color="#4C72B0")
        ax1.bar(x + bar_w / 2, fitted, bar_w, label="Fitted OD", color="#DD8452")
        ax1.set_ylabel("OD")
        ax1.set_title(f"Pixel ({row}, {col}) — OD Spectrum", fontsize=10)
        ax1.legend(fontsize=8)

        if np.asarray(x).ndim == 1 and len(x_tick_labels) <= 12:
            ax1.set_xticks(x)
            ax1.set_xticklabels(x_tick_labels, fontsize=8)

        colors = ["#55A868" if r >= 0 else "#C44E52" for r in residual]
        ax2.bar(x, residual, color=colors)
        ax2.axhline(0, color="gray", linewidth=0.5)
        ax2.set_ylabel("Residual")
        ax2.set_xlabel(x_axis_label)

        if np.asarray(x).ndim == 1 and len(x_tick_labels) <= 12:
            ax2.set_xticks(x)
            ax2.set_xticklabels(x_tick_labels, fontsize=8)

        fig.tight_layout()
        self._safe_draw_canvas(self._spec_canvas_widget)

    def _render_concentrations(self) -> None:
        """Render concentrations text table for selected pixel."""
        if self._conc_text_widget is None:
            return

        if not isinstance(self._data, dict) or self._selected_pixel is None:
            self._conc_text_widget.setPlainText("No pixel selected.")
            return

        concentrations = self._as_array(self._data.get("concentrations"))
        row, col = self._selected_pixel
        if (
            concentrations is None
            or concentrations.ndim < 3
            or row < 0
            or col < 0
            or row >= concentrations.shape[0]
            or col >= concentrations.shape[1]
        ):
            self._conc_text_widget.setPlainText("Concentration data unavailable for selected pixel.")
            return

        conc_vec = np.asarray(concentrations[row, col, :]).reshape(-1)
        names = list(self._data.get("chromophore_names") or [])
        include_background = bool(self._data.get("include_background", True))
        if include_background and len(names) < len(conc_vec):
            names = [*names, "background"]
        if len(names) < len(conc_vec):
            names.extend([f"component_{i + 1}" for i in range(len(names), len(conc_vec))])
        if len(names) > len(conc_vec):
            names = names[: len(conc_vec)]

        lines = [f"Pixel ({row}, {col})", f"{'Chromophore':<16} {'Concentration':>14}", "─" * 32]
        for name, value in zip(names, conc_vec):
            lines.append(f"{name:<16} {float(value):>14.6e}")

        rmse_map = self._as_array(self._data.get("rmse_map"))
        if rmse_map is not None and rmse_map.ndim >= 2 and row < rmse_map.shape[0] and col < rmse_map.shape[1]:
            lines.append("")
            lines.append(f"{'RMSE':<16} {float(rmse_map[row, col]):>14.6e}")

        self._conc_text_widget.setPlainText("\n".join(lines))


# ---------------------------------------------------------------------------
def _make_widget() -> type:
    """Return a QWidget subclass."""
    try:
        from PySide6.QtWidgets import QWidget
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PySide6 is required to instantiate InspectorPanel"
        ) from exc

    class _InspectorWidget(QWidget):
        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)

    return _InspectorWidget
