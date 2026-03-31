"""
Diagnostics panel — RMSE stats, warnings, residual histogram, quality mask.
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class DiagnosticsPanel(ttk.Frame):
    """Quality diagnostics display."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Top: stats text
        stats_frame = ttk.LabelFrame(self, text="Quality Metrics", padding=8)
        stats_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.stats_text = tk.Text(stats_frame, height=6, state=tk.DISABLED)
        self.stats_text.pack(fill=tk.X)

        # Bottom: plots
        self.fig = Figure(figsize=(10, 4), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

    def show_diagnostics(self, name, res):
        """Update diagnostics display."""
        diag = res["diagnostics"]
        rmse = res["rmse_map"]

        # --- Stats text ---
        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete("1.0", tk.END)

        lines = [
            f"Sample: {name}",
            f"Global RMSE (mean): {diag['global_rmse']:.6f}",
            f"Overlap matrix condition number: {diag['condition_number']:.2f}",
            f"NaN pixels: {diag['n_nan_pixels']}",
            f"Negative reflectance values: {diag['n_negative_reflectance']}",
        ]
        if diag["warnings"]:
            lines.append("")
            lines.extend(diag["warnings"])

        self.stats_text.insert(tk.END, "\n".join(lines))
        self.stats_text.config(state=tk.DISABLED)

        # --- Plots ---
        self.fig.clear()

        # Left: RMSE histogram
        ax1 = self.fig.add_subplot(121)
        valid = rmse[np.isfinite(rmse)].ravel()
        if len(valid) > 0:
            ax1.hist(valid, bins=50, color="#4C72B0", edgecolor="white", linewidth=0.5)
        ax1.set_xlabel("RMSE")
        ax1.set_ylabel("Pixel count")
        ax1.set_title("Residual RMSE Distribution", fontsize=10)

        # Right: quality mask (RMSE > 2× median = low quality)
        ax2 = self.fig.add_subplot(122)
        if len(valid) > 0:
            threshold = np.median(valid) * 2
            mask = rmse > threshold
            ax2.imshow(mask, cmap="Reds", aspect="equal")
            ax2.set_title(f"Low-quality mask (RMSE > {threshold:.4f})", fontsize=10)
        else:
            ax2.set_title("No valid data", fontsize=10)
        ax2.set_xticks([])
        ax2.set_yticks([])

        self.fig.tight_layout()
        self.canvas.draw()
