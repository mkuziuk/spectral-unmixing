"""
Pixel Inspector panel — click on an image to see per-pixel spectral data.

Shows:
- Measured OD spectrum (bar chart)
- Fitted OD spectrum (overlaid)
- Residual
- Estimated concentrations (table)
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class InspectorPanel(ttk.Frame):
    """Pixel inspector: click a pixel on the image, see its spectra."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._res = None
        self._selected_pixel = None

        # --- Layout: left = clickable image, right = spectra + table ---
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: clickable image
        left = ttk.Frame(paned)
        paned.add(left, weight=1)

        ttk.Label(left, text="Click a pixel on the image below:", padding=4).pack(anchor=tk.W)
        self.img_fig = Figure(figsize=(4, 4), dpi=100)
        self.img_ax = self.img_fig.add_subplot(111)
        self.img_canvas = FigureCanvasTkAgg(self.img_fig, master=left)
        self.img_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.img_canvas.mpl_connect("button_press_event", self._on_click)

        # Right: spectra + concentrations
        right = ttk.Frame(paned)
        paned.add(right, weight=2)

        self.spec_fig = Figure(figsize=(7, 4), dpi=100)
        self.spec_canvas = FigureCanvasTkAgg(self.spec_fig, master=right)
        self.spec_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Concentrations table
        table_frame = ttk.LabelFrame(right, text="Concentrations", padding=4)
        table_frame.pack(fill=tk.X, padx=4, pady=4)

        self.conc_text = tk.Text(table_frame, height=8, width=50, state=tk.DISABLED)
        self.conc_text.pack(fill=tk.X)

    def set_data(self, name, res):
        """Load new sample data for inspection."""
        self._res = res
        self._selected_pixel = None

        # Show a reference image (first band raw)
        self.img_ax.clear()
        rgb_preview = res["sample_cube"][:, :, 0]
        self.img_ax.imshow(rgb_preview, cmap="gray", aspect="equal")
        self.img_ax.set_title("Click a pixel", fontsize=10)
        self.img_fig.tight_layout()
        self.img_canvas.draw()

        # Clear spectra
        self.spec_fig.clear()
        self.spec_canvas.draw()
        self.conc_text.config(state=tk.NORMAL)
        self.conc_text.delete("1.0", tk.END)
        self.conc_text.config(state=tk.DISABLED)

    def _on_click(self, event):
        if self._res is None or event.xdata is None or event.ydata is None:
            return

        col = int(round(event.xdata))
        row = int(round(event.ydata))
        H, W = self._res["sample_cube"].shape[:2]

        if not (0 <= row < H and 0 <= col < W):
            return

        self._selected_pixel = (row, col)
        self._update_inspector(row, col)

    def _update_inspector(self, row, col):
        res = self._res
        wls = res["wavelengths"]
        od_measured = res["od_cube"][row, col, :]
        od_fitted = res["fitted_od"][row, col, :]
        residual = od_measured - od_fitted

        # --- Update image with crosshair ---
        self.img_ax.clear()
        self.img_ax.imshow(res["sample_cube"][:, :, 0], cmap="gray", aspect="equal")
        self.img_ax.axhline(row, color="red", linewidth=0.5, alpha=0.7)
        self.img_ax.axvline(col, color="red", linewidth=0.5, alpha=0.7)
        self.img_ax.plot(col, row, "r+", markersize=12, markeredgewidth=2)
        self.img_ax.set_title(f"Pixel ({row}, {col})", fontsize=10)
        self.img_fig.tight_layout()
        self.img_canvas.draw()

        # --- Spectra plot ---
        self.spec_fig.clear()

        x = np.arange(len(wls))
        bar_w = 0.35

        # Top: measured vs fitted OD
        ax1 = self.spec_fig.add_subplot(211)
        ax1.bar(x - bar_w / 2, od_measured, bar_w, label="Measured OD", color="#4C72B0")
        ax1.bar(x + bar_w / 2, od_fitted, bar_w, label="Fitted OD", color="#DD8452")
        ax1.set_xticks(x)
        ax1.set_xticklabels([str(w) for w in wls], fontsize=8)
        ax1.set_ylabel("OD")
        ax1.set_title(f"Pixel ({row}, {col}) — OD Spectrum", fontsize=10)
        ax1.legend(fontsize=8)

        # Bottom: residual
        ax2 = self.spec_fig.add_subplot(212)
        colors = ["#55A868" if r >= 0 else "#C44E52" for r in residual]
        ax2.bar(x, residual, color=colors)
        ax2.set_xticks(x)
        ax2.set_xticklabels([str(w) for w in wls], fontsize=8)
        ax2.set_ylabel("Residual")
        ax2.set_xlabel("LED wavelength (nm)")
        ax2.axhline(0, color="gray", linewidth=0.5)

        self.spec_fig.tight_layout()
        self.spec_canvas.draw()

        # --- Concentrations table ---
        conc = res["concentrations"][row, col, :]
        names = res["chromophore_names"] + ["background"]

        self.conc_text.config(state=tk.NORMAL)
        self.conc_text.delete("1.0", tk.END)
        self.conc_text.insert(tk.END, f"{'Chromophore':<16} {'Concentration':>14}\n")
        self.conc_text.insert(tk.END, "─" * 32 + "\n")
        for n, c in zip(names, conc):
            self.conc_text.insert(tk.END, f"{n:<16} {c:>14.6f}\n")

        rmse = res["rmse_map"][row, col]
        self.conc_text.insert(tk.END, f"\n{'RMSE':<16} {rmse:>14.6f}\n")
        self.conc_text.config(state=tk.DISABLED)
