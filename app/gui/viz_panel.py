"""
Visualization panel — displays chromophore maps, derived maps, and raw/reflectance/OD images.

Uses matplotlib FigureCanvasTkAgg embedded in a tkinter frame.
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


class VizPanel(ttk.Frame):
    """Tabbed visualization panel showing image grids."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # View selector
        ctrl = ttk.Frame(self, padding=4)
        ctrl.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(ctrl, text="View:").pack(side=tk.LEFT, padx=(0, 4))
        self.view_var = tk.StringVar(value="Chromophore Maps")
        views = ["Chromophore Maps", "Derived Maps", "Raw / Reflectance / OD"]
        self.view_combo = ttk.Combobox(
            ctrl, textvariable=self.view_var, values=views,
            state="readonly", width=25,
        )
        self.view_combo.pack(side=tk.LEFT)
        self.view_combo.bind("<<ComboboxSelected>>", self._on_view_changed)

        # Band selector (for Raw/Refl/OD view)
        ttk.Label(ctrl, text="  Band:").pack(side=tk.LEFT, padx=(12, 4))
        self.band_var = tk.StringVar()
        self.band_combo = ttk.Combobox(
            ctrl, textvariable=self.band_var, state="readonly", width=10,
        )
        self.band_combo.pack(side=tk.LEFT)
        self.band_combo.bind("<<ComboboxSelected>>", self._on_view_changed)

        # Matplotlib canvas
        self.fig = Figure(figsize=(12, 7), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, self)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)

        self._current_res = None

    def show_results(self, name, res):
        """Display results for selected sample."""
        self._current_res = res

        # Update band combo
        wls = res["wavelengths"]
        self.band_combo["values"] = [f"{w} nm" for w in wls]
        if wls:
            self.band_combo.current(0)

        self._redraw()

    def _on_view_changed(self, event=None):
        self._redraw()

    def _redraw(self):
        if self._current_res is None:
            return
        res = self._current_res
        view = self.view_var.get()

        self.fig.clear()

        if view == "Chromophore Maps":
            self._draw_chromophore_maps(res)
        elif view == "Derived Maps":
            self._draw_derived_maps(res)
        elif view == "Raw / Reflectance / OD":
            self._draw_raw_refl_od(res)

        self.fig.tight_layout()
        self.canvas.draw()

    def _draw_chromophore_maps(self, res):
        conc = res["concentrations"]
        names = res["chromophore_names"].copy()
        if res.get("include_background", True):
            names.append("background")
        n = len(names)
        cols = 3
        rows = (n + cols - 1) // cols

        for i, name in enumerate(names):
            ax = self.fig.add_subplot(rows, cols, i + 1)
            data = conc[:, :, i]
            im = ax.imshow(data, cmap="viridis", aspect="equal")
            ax.set_title(name, fontsize=10)
            ax.set_xticks([])
            ax.set_yticks([])
            self.fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    def _draw_derived_maps(self, res):
        maps = {
            "THb": res["derived"]["THb"],
            "StO₂": res["derived"]["StO2"],
            "RMSE": res["rmse_map"],
        }
        cmaps = {"THb": "Reds", "StO₂": "RdYlBu_r", "RMSE": "hot"}

        for i, (name, data) in enumerate(maps.items()):
            ax = self.fig.add_subplot(1, 3, i + 1)
            im = ax.imshow(data, cmap=cmaps.get(name, "viridis"), aspect="equal")
            ax.set_title(name, fontsize=10)
            ax.set_xticks([])
            ax.set_yticks([])
            self.fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    def _draw_raw_refl_od(self, res):
        # Get selected band index
        band_str = self.band_var.get()
        wls = res["wavelengths"]
        try:
            band_idx = next(
                i for i, w in enumerate(wls) if f"{w} nm" == band_str
            )
        except StopIteration:
            band_idx = 0

        panels = [
            ("Raw", res["sample_cube"][:, :, band_idx], "gray"),
            ("Reflectance", res["reflectance"][:, :, band_idx], "gray"),
            ("Optical Density", res["od_cube"][:, :, band_idx], "inferno"),
        ]

        for i, (title, data, cmap) in enumerate(panels):
            ax = self.fig.add_subplot(1, 3, i + 1)
            im = ax.imshow(data, cmap=cmap, aspect="equal")
            ax.set_title(f"{title} @ {wls[band_idx]} nm", fontsize=10)
            ax.set_xticks([])
            ax.set_yticks([])
            self.fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
