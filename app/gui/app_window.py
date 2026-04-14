"""
Main application window — tkinter-based GUI for spectral unmixing.

Layout:
    ┌──────────────────────────────────────────────┐
    │  Toolbar (folder picker, run, save)          │
    ├────────────┬─────────────────────────────────┤
    │  Sidebar   │  Main content area (Notebook)   │
    │  - Info    │  - Tab: Maps                    │
    │  - Diag    │  - Tab: Inspector               │
    │            │  - Tab: Diagnostics             │
    └────────────┴─────────────────────────────────┘
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import numpy as np

from app.core import io as loader
from app.core import processing
from app.core import export
from app.gui.viz_panel import VizPanel
from app.gui.inspector import InspectorPanel
from app.gui.diagnostics import DiagnosticsPanel
from app.gui.stats_panel import StatsPanel


class SpectralUnmixingApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("Spectral Unmixing")
        self.geometry("1400x900")
        self.minsize(1000, 700)

        # ---- State ----
        self.root_dir = None
        self.folder_info = None
        self.data_dir = self._find_data_dir()
        self.results = {}  # sample_name → result dict

        # ---- Build UI ----
        self._build_toolbar()
        self._build_main_area()

        # Style tweaks
        style = ttk.Style(self)
        style.configure("TButton", padding=4)
        style.configure("Header.TLabel", font=("", 11, "bold"))

    # ------------------------------------------------------------------
    # Data directory
    # ------------------------------------------------------------------

    def _find_data_dir(self):
        """Locate the data/ folder relative to the project root."""
        # Support PyInstaller bundled data
        if hasattr(sys, "_MEIPASS"):
            bundle_dir = getattr(sys, "_MEIPASS")
            data_path = os.path.join(bundle_dir, "data")
            if os.path.isdir(data_path):
                return data_path

        # Try relative to the script / cwd
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data"),
            os.path.join(os.getcwd(), "data"),
        ]
        for c in candidates:
            c = os.path.normpath(c)
            if os.path.isdir(c):
                return c
        return None

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self):
        toolbar = ttk.Frame(self, padding=6)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(
            toolbar, text="📂 Select Root Folder", command=self._on_select_folder,
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.chrom_mb = ttk.Menubutton(toolbar, text="Chromophores")
        self.chrom_menu = tk.Menu(self.chrom_mb, tearoff=False)
        self.chrom_mb.configure(menu=self.chrom_menu)
        self.chrom_mb.pack(side=tk.LEFT, padx=(0, 8))

        self.chrom_vars = {}
        if self.data_dir:
            chrom_spectra = loader.load_chromophore_spectra(self.data_dir)
            for c in chrom_spectra.keys():
                var = tk.BooleanVar(value=True)
                self.chrom_vars[c] = var
                self.chrom_menu.add_checkbutton(label=c, variable=var)

        self.background_var = tk.BooleanVar(value=True)
        self.chrom_menu.add_separator()
        self.chrom_menu.add_checkbutton(label="Background", variable=self.background_var)

        self.run_btn = ttk.Button(
            toolbar, text="▶ Run Unmixing", command=self._on_run, state=tk.DISABLED,
        )
        self.run_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.save_btn = ttk.Button(
            toolbar, text="💾 Save Results", command=self._on_save, state=tk.DISABLED,
        )
        self.save_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.progress = ttk.Progressbar(toolbar, length=200, mode="determinate")
        self.progress.pack(side=tk.LEFT, padx=(8, 8))

        self.status_var = tk.StringVar(value="No folder selected")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side=tk.LEFT)

    # ------------------------------------------------------------------
    # Main area: sidebar + notebook
    # ------------------------------------------------------------------

    def _build_main_area(self):
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # --- Sidebar ---
        sidebar = ttk.Frame(paned, padding=6)
        paned.add(sidebar, weight=0)

        ttk.Label(sidebar, text="Folder Info", style="Header.TLabel").pack(anchor=tk.W)
        self.info_text = tk.Text(sidebar, width=30, height=12, wrap=tk.WORD, state=tk.DISABLED)
        self.info_text.pack(fill=tk.X, pady=(4, 12))

        ttk.Label(sidebar, text="Sample", style="Header.TLabel").pack(anchor=tk.W)
        self.sample_var = tk.StringVar()
        self.sample_combo = ttk.Combobox(
            sidebar, textvariable=self.sample_var, state="readonly", width=25,
        )
        self.sample_combo.pack(fill=tk.X, pady=(4, 12))
        self.sample_combo.bind("<<ComboboxSelected>>", self._on_sample_selected)

        ttk.Label(sidebar, text="Warnings", style="Header.TLabel").pack(anchor=tk.W)
        self.warnings_text = tk.Text(sidebar, width=30, height=10, wrap=tk.WORD, state=tk.DISABLED, fg="red")
        self.warnings_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        # --- Notebook (content) ---
        self.notebook = ttk.Notebook(paned)
        paned.add(self.notebook, weight=1)

        self.viz_panel = VizPanel(self.notebook, self)
        self.notebook.add(self.viz_panel, text="Maps")

        self.inspector_panel = InspectorPanel(self.notebook, self)
        self.notebook.add(self.inspector_panel, text="Pixel Inspector")

        self.diag_panel = DiagnosticsPanel(self.notebook, self)
        self.notebook.add(self.diag_panel, text="Diagnostics")

        self.stats_panel = StatsPanel(self.notebook, self)
        self.notebook.add(self.stats_panel, text="Reflectance Stats")

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_select_folder(self):
        path = filedialog.askdirectory(title="Select root folder with image cubes")
        if not path:
            return
        try:
            info = loader.detect_folders(path)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        self.root_dir = path
        self.folder_info = info
        self.results.clear()

        # Update info panel
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert(tk.END, f"Root: {os.path.basename(path)}\n")
        self.info_text.insert(tk.END, f"Samples: {len(info['sample_names'])}\n")
        for s in info["sample_names"]:
            self.info_text.insert(tk.END, f"  • {s}\n")
        self.info_text.insert(tk.END, f"\nLEDs: {len(info['wavelengths'])}\n")
        self.info_text.insert(tk.END, f"  {info['wavelengths']} nm\n")
        self.info_text.insert(tk.END, f"\nRef: ✓\nDark ref: ✓\n")
        self.info_text.config(state=tk.DISABLED)

        self.status_var.set(f"Loaded: {os.path.basename(path)}")
        self.run_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.DISABLED)
        self.sample_combo["values"] = []

    def _on_run(self):
        """Run unmixing in a background thread."""
        self.run_btn.config(state=tk.DISABLED)
        self.status_var.set("Processing...")
        thread = threading.Thread(target=self._run_pipeline, daemon=True)
        thread.start()

    def _run_pipeline(self):
        """Background processing pipeline."""
        try:
            info = self.folder_info
            wls = info["wavelengths"]

            # Load reference cubes once
            self._set_status("Loading reference cubes...")
            ref_cube = loader.load_image_cube(info["ref_dir"], wls)
            dark_cube = loader.load_image_cube(info["dark_ref_dir"], wls)

            # Load spectral data and build overlap matrix once
            self._set_status("Building overlap matrix...")
            chrom_spectra = loader.load_chromophore_spectra(self.data_dir)
            led_wl, led_em = loader.load_led_emission(self.data_dir, wls)
            pen_wl, pen_depth = loader.load_penetration_depth(self.data_dir)

            selected_chroms = [c for c, var in self.chrom_vars.items() if var.get()]
            include_background = self.background_var.get()

            if not selected_chroms and not include_background:
                raise ValueError("No components selected for unmixing.")

            A, chrom_names = processing.build_overlap_matrix(
                led_wl, led_em, chrom_spectra, pen_wl, pen_depth, wls,
                chromophore_names=selected_chroms,
                include_background=include_background
            )

            n_samples = len(info["samples"])
            self.results.clear()

            for idx, (sample_dir, sample_name) in enumerate(
                zip(info["samples"], info["sample_names"])
            ):
                pct = int(100 * idx / n_samples)
                self._set_status(f"Processing {sample_name} ({idx+1}/{n_samples})...")
                self._set_progress(pct)

                # Load sample cube
                sample_cube = loader.load_image_cube(sample_dir, wls)

                # Reflectance
                reflectance = processing.compute_reflectance(sample_cube, ref_cube, dark_cube)

                # Optical density
                od_cube = processing.compute_optical_density(reflectance)

                # Unmixing
                concentrations, rmse_map, fitted_od = processing.solve_unmixing(od_cube, A)

                # Derived maps
                derived = processing.compute_derived_maps(concentrations, chrom_names)

                # Diagnostics
                diag = processing.compute_diagnostics(reflectance, od_cube, rmse_map, A)

                self.results[sample_name] = {
                    "sample_cube": sample_cube,
                    "reflectance": reflectance,
                    "od_cube": od_cube,
                    "concentrations": concentrations,
                    "fitted_od": fitted_od,
                    "rmse_map": rmse_map,
                    "derived": derived,
                    "diagnostics": diag,
                    "A": A,
                    "chromophore_names": chrom_names,
                    "include_background": include_background,
                    "wavelengths": wls,
                }

            # Compute global min/max scales per chromophore across all samples
            chrom_scales, derived_scales = self._compute_global_scales(chrom_names, include_background)

            self._set_progress(100)
            self._set_status(f"Done — {n_samples} samples processed")

            # Store scales in results for use by viz/export
            self._chrom_scales = chrom_scales
            self._derived_scales = derived_scales

            # Update UI on main thread
            self.after(0, self._on_pipeline_done)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Processing Error", str(e)))
            self.after(0, lambda: self.run_btn.config(state=tk.NORMAL))
            self.after(0, lambda: self.status_var.set("Error during processing"))

    def _compute_global_scales(self, chrom_names, include_background):
        """
        Compute global min/max per chromophore across all samples.

        Returns
        -------
        chrom_scales : dict  {name: (vmin, vmax)}
        derived_scales : dict  {name: (vmin, vmax)}  for THb, StO2, RMSE
        """
        all_names = chrom_names.copy()
        if include_background:
            all_names.append("background")

        n_chrom = len(all_names)

        # Chromophore scales
        chrom_scales = {}
        for i, name in enumerate(all_names):
            vals = []
            for res in self.results.values():
                conc = res["concentrations"][:, :, i]
                finite = conc[np.isfinite(conc)]
                if finite.size > 0:
                    vals.append(finite)
            if vals:
                all_vals = np.concatenate(vals)
                chrom_scales[name] = (float(all_vals.min()), float(all_vals.max()))
            else:
                chrom_scales[name] = (0.0, 1.0)

        # Derived scales (THb, StO2, RMSE)
        derived_scales = {}
        for res in self.results.values():
            for key in ["THb", "StO2"]:
                data = res["derived"].get(key)
                if data is not None:
                    finite = data[np.isfinite(data)]
                    if finite.size > 0:
                        cur = derived_scales.get(key)
                        if cur is None:
                            derived_scales[key] = (float(finite.min()), float(finite.max()))
                        else:
                            derived_scales[key] = (
                                min(cur[0], float(finite.min())),
                                max(cur[1], float(finite.max())),
                            )
            # RMSE
            rmse = res["rmse_map"]
            finite = rmse[np.isfinite(rmse)]
            if finite.size > 0:
                cur = derived_scales.get("RMSE")
                if cur is None:
                    derived_scales["RMSE"] = (float(finite.min()), float(finite.max()))
                else:
                    derived_scales["RMSE"] = (
                        min(cur[0], float(finite.min())),
                        max(cur[1], float(finite.max())),
                    )

        return chrom_scales, derived_scales

    def _on_pipeline_done(self):
        """Called on the main thread after pipeline completes."""
        names = list(self.results.keys())
        self.sample_combo["values"] = names
        if names:
            self.sample_combo.current(0)
            self._on_sample_selected(None)
        self.run_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.NORMAL)

    def _on_sample_selected(self, event):
        """User picked a sample from the dropdown."""
        name = self.sample_var.get()
        if name not in self.results:
            return
        res = self.results[name]

        # Update warnings sidebar
        self.warnings_text.config(state=tk.NORMAL)
        self.warnings_text.delete("1.0", tk.END)
        for w in res["diagnostics"]["warnings"]:
            self.warnings_text.insert(tk.END, w + "\n")
        if not res["diagnostics"]["warnings"]:
            self.warnings_text.insert(tk.END, "No warnings ✓")
        self.warnings_text.config(state=tk.DISABLED)

        # Update panels
        chrom_scales = getattr(self, "_chrom_scales", None)
        derived_scales = getattr(self, "_derived_scales", None)
        self.viz_panel.show_results(name, res, chrom_scales, derived_scales)
        self.inspector_panel.set_data(name, res)
        self.diag_panel.show_diagnostics(name, res)
        self.stats_panel.show_results(name, res)

    def _on_save(self):
        """Save all results to disk."""
        out_dir = filedialog.askdirectory(title="Select output directory")
        if not out_dir:
            return
        chrom_scales = getattr(self, "_chrom_scales", None)
        derived_scales = getattr(self, "_derived_scales", None)
        for name, res in self.results.items():
            self._set_status(f"Saving {name}...")
            export.save_results(
                out_dir, name,
                res["concentrations"],
                res["chromophore_names"],
                res["derived"],
                res["rmse_map"],
                res["diagnostics"],
                chrom_scales=chrom_scales,
                derived_scales=derived_scales,
            )
        self._set_status(f"Saved {len(self.results)} samples to {os.path.basename(out_dir)}")
        messagebox.showinfo("Export", f"Results saved to:\n{out_dir}")

    # ------------------------------------------------------------------
    # Thread-safe UI helpers
    # ------------------------------------------------------------------

    def _set_status(self, text):
        self.after(0, lambda: self.status_var.set(text))

    def _set_progress(self, value):
        self.after(0, lambda: self.progress.configure(value=value))
