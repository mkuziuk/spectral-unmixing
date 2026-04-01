"""
Statistics panel — displays mean and median reflectance per wavelength for the selected hypercube.
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


class StatsPanel(ttk.Frame):
    """Tabbed panel showing reflectance statistics plot."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Controls
        ctrl = ttk.Frame(self, padding=4)
        ctrl.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(ctrl, text="Statistic:").pack(side=tk.LEFT, padx=(0, 4))
        self.stat_var = tk.StringVar(value="Median")
        self.stat_combo = ttk.Combobox(
            ctrl, textvariable=self.stat_var, values=["Mean", "Median"],
            state="readonly", width=15,
        )
        self.stat_combo.pack(side=tk.LEFT)
        self.stat_combo.bind("<<ComboboxSelected>>", self._on_stat_changed)

        # Matplotlib canvas
        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, self)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)

        self._current_res = None

    def show_results(self, name, res):
        """Display results for selected sample."""
        self._current_res = res
        self._redraw()

    def _on_stat_changed(self, event=None):
        self._redraw()

    def _redraw(self):
        if self._current_res is None:
            return
        
        res = self._current_res
        stat_choice = self.stat_var.get()
        wls = res["wavelengths"]
        reflectance = res["reflectance"]

        self.ax.clear()

        # Handle potential NaNs or invalid values safely
        valid_refl = np.where(np.isfinite(reflectance), reflectance, np.nan)

        if stat_choice == "Mean":
            stats = np.nanmean(valid_refl, axis=(0, 1))
            title_prefix = "Mean"
        else:
            stats = np.nanmedian(valid_refl, axis=(0, 1))
            title_prefix = "Median"
        
        self.ax.plot(wls, stats, marker='o', linestyle='-', color='b')
        self.ax.set_title(f"{title_prefix} Reflectance per Wavelength")
        self.ax.set_xlabel("Wavelength (nm)")
        self.ax.set_ylabel("Reflectance")
        self.ax.grid(True)
        
        self.fig.tight_layout()
        self.canvas.draw()
