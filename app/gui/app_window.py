"""
Main application window — tkinter-based GUI for spectral unmixing.

DEPRECATED: This module is retained only for the ``--legacy-tk`` rollback path.
All new GUI development should target ``app.gui_qt``.

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

import warnings
warnings.warn(
    "app.gui.app_window is deprecated; use app.gui_qt for the default PySide6 UI.",
    DeprecationWarning,
    stacklevel=2,
)

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
        self._default_data_dir = self.data_dir  # Store default for reset
        self._scattering_params = processing.get_default_scattering_parameters()

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

    def _refresh_chromophore_menu(self):
        """Rebuild chromophore menu checkboxes based on current data_dir."""
        # Clear existing entries
        self.chrom_vars.clear()
        menu_items = self.chrom_menu.index("end")
        if menu_items is not None:
            for _ in range(menu_items + 1):
                self.chrom_menu.delete(0)

        if not self.data_dir:
            self.chrom_menu.add_separator()
            self.chrom_menu.add_checkbutton(label="Background", variable=self.background_var)
            return

        try:
            chrom_spectra = loader.load_chromophore_spectra(self.data_dir)
            for c in sorted(chrom_spectra.keys()):
                var = tk.BooleanVar(value=True)
                self.chrom_vars[c] = var
                self.chrom_menu.add_checkbutton(label=c, variable=var)
        except Exception:
            # If loading fails, leave menu empty except background
            pass

        self.chrom_menu.add_separator()
        self.chrom_menu.add_checkbutton(label="Background", variable=self.background_var)

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

    def _on_select_data_folder(self):
        """Select a custom data folder and update UI."""
        path = filedialog.askdirectory(title="Select data folder (contains chromophores/, leds_emission.csv, etc.)")
        if not path:
            return

        # Validate with core I/O helper
        try:
            loader.validate_data_directory(path)
        except FileNotFoundError as e:
            messagebox.showerror("Invalid Data Folder", str(e))
            return
        except ValueError as e:
            messagebox.showerror("Invalid Data Folder", str(e))
            return

        self.data_dir = path
        self._refresh_chromophore_menu()
        self.data_source_var.set(f"Data: custom ({os.path.basename(path)})")

    def _on_reset_data_folder(self):
        """Reset to auto-discovered default data folder."""
        self.data_dir = self._find_data_dir()
        self._default_data_dir = self.data_dir
        self._refresh_chromophore_menu()
        if self.data_dir:
            self.data_source_var.set(f"Data: default ({os.path.basename(self.data_dir)})")
        else:
            self.data_source_var.set("Data: default (not found)")

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self):
        toolbar = ttk.Frame(self, padding=6)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(
            toolbar, text="📂 Select Root Folder", command=self._on_select_folder,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            toolbar, text="🧪 Select Data Folder", command=self._on_select_data_folder,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            toolbar, text="🔄 Use Default Data", command=self._on_reset_data_folder,
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.chrom_mb = ttk.Menubutton(toolbar, text="Chromophores")
        self.chrom_menu = tk.Menu(self.chrom_mb, tearoff=False)
        self.chrom_mb.configure(menu=self.chrom_menu)
        self.chrom_mb.pack(side=tk.LEFT, padx=(0, 8))

        self.background_var = tk.BooleanVar(value=True)
        self.chrom_vars = {}
        self._refresh_chromophore_menu()

        # Solver selection dropdown
        ttk.Label(toolbar, text="Solver:").pack(side=tk.LEFT, padx=(8, 4))
        self.solver_var = tk.StringVar(value="ls")
        self.solver_combo = ttk.Combobox(
            toolbar,
            textvariable=self.solver_var,
            values=["ls", "nnls", "mu_a", "iterative"],
            state="readonly",
            width=8,
        )
        self.solver_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.solver_combo.bind("<<ComboboxSelected>>", self._on_solver_method_changed)

        # Background value input
        self.background_label = ttk.Label(toolbar, text="Background:")
        self.background_label.pack(side=tk.LEFT, padx=(8, 4))
        self.background_value_var = tk.StringVar(value="2500.0")
        self.bg_entry = ttk.Entry(toolbar, textvariable=self.background_value_var, width=8)
        self.bg_entry.pack(side=tk.LEFT, padx=(0, 8))

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

        default_data = (
            f"Data: default ({os.path.basename(self.data_dir)})" if self.data_dir else "Data: default (not found)"
        )
        self.data_source_var = tk.StringVar(value=default_data)
        ttk.Label(toolbar, textvariable=self.data_source_var).pack(side=tk.LEFT, padx=(8, 12))

        self.status_var = tk.StringVar(value="No folder selected")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side=tk.LEFT)

        self.scattering_frame = ttk.Frame(self, padding=(12, 0, 12, 6))

        ttk.Label(self.scattering_frame, text="Fixed scattering:").pack(side=tk.LEFT, padx=(0, 8))

        self.lambda0_var = tk.StringVar(value=str(self._scattering_params["lambda0_nm"]))
        ttk.Label(self.scattering_frame, text="lambda0 (nm):").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(self.scattering_frame, textvariable=self.lambda0_var, width=8).pack(side=tk.LEFT, padx=(0, 8))

        self.mu_s_500_var = tk.StringVar(value=str(self._scattering_params["mu_s_500_cm1"]))
        ttk.Label(self.scattering_frame, text="mu_s_500 (cm^-1):").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(self.scattering_frame, textvariable=self.mu_s_500_var, width=8).pack(side=tk.LEFT, padx=(0, 8))

        self.power_b_var = tk.StringVar(value=str(self._scattering_params["power_b"]))
        ttk.Label(self.scattering_frame, text="b:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(self.scattering_frame, textvariable=self.power_b_var, width=8).pack(side=tk.LEFT, padx=(0, 8))

        self.lipofundin_var = tk.StringVar(value=str(self._scattering_params["lipofundin_fraction"]))
        ttk.Label(self.scattering_frame, text="lipo frac:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(self.scattering_frame, textvariable=self.lipofundin_var, width=8).pack(side=tk.LEFT, padx=(0, 8))

        self.anisotropy_var = tk.StringVar(value=str(self._scattering_params["anisotropy_g"]))
        ttk.Label(self.scattering_frame, text="g:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(self.scattering_frame, textvariable=self.anisotropy_var, width=8).pack(side=tk.LEFT, padx=(0, 8))

        self._update_solver_dependent_controls()

    def _on_solver_method_changed(self, _event=None):
        """Update solver-specific controls when the combobox changes."""
        self._update_solver_dependent_controls()

    def _update_solver_dependent_controls(self):
        """Show fixed-scattering controls for solvers that use them."""
        use_fixed_scattering = self.solver_var.get() in {"mu_a", "iterative"}

        if use_fixed_scattering:
            self.scattering_frame.pack(side=tk.TOP, fill=tk.X)
            self.bg_entry.state(["disabled"])
        else:
            self.scattering_frame.pack_forget()
            self.bg_entry.state(["!disabled"])

    def _read_scattering_params_from_ui(self):
        """Read and validate fixed-scattering parameters from the Tk controls."""
        raw = {
            "lambda0_nm": self.lambda0_var.get().strip(),
            "mu_s_500_cm1": self.mu_s_500_var.get().strip(),
            "power_b": self.power_b_var.get().strip(),
            "lipofundin_fraction": self.lipofundin_var.get().strip(),
            "anisotropy_g": self.anisotropy_var.get().strip(),
        }
        validated = processing.validate_scattering_parameters(raw)
        self._scattering_params = validated
        return dict(validated)

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
            # Validate data_dir before starting
            if not self.data_dir:
                raise FileNotFoundError("No data folder selected. Please select a valid data folder.")
            try:
                loader.validate_data_directory(self.data_dir)
            except (FileNotFoundError, ValueError) as e:
                raise RuntimeError(f"Invalid data folder: {e}")

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
            solver_method = self.solver_var.get()

            if not selected_chroms and not include_background:
                raise ValueError("No components selected for unmixing.")

            mus_prime = None
            scattering_parameters = None
            if solver_method in {"mu_a", "iterative"}:
                bg_value = float(self.background_value_var.get() or 2500.0)
                include_background = False
                if not selected_chroms:
                    raise ValueError(
                        f"Select at least one chromophore for the {solver_method} solver."
                    )
                scattering_parameters = self._read_scattering_params_from_ui()
            if solver_method == "mu_a":
                A, chrom_names = processing.build_absorption_matrix(
                    led_wl,
                    led_em,
                    chrom_spectra,
                    wls,
                    chromophore_names=selected_chroms,
                )
                mus_prime = processing.build_fixed_scattering_profile(
                    led_wl,
                    led_em,
                    wls,
                    **scattering_parameters,
                )
            elif solver_method == "iterative":
                A, chrom_names = processing.build_overlap_matrix(
                    led_wl, led_em, chrom_spectra, pen_wl, pen_depth, wls,
                    chromophore_names=selected_chroms,
                    include_background=False,
                    background_value=bg_value,
                )
            else:
                try:
                    bg_value = float(self.background_value_var.get())
                except ValueError:
                    raise ValueError("Background value must be a number.")
                A, chrom_names = processing.build_overlap_matrix(
                    led_wl, led_em, chrom_spectra, pen_wl, pen_depth, wls,
                    chromophore_names=selected_chroms,
                    include_background=include_background,
                    background_value=bg_value,
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
                solver_info = None
                active_A = A
                if solver_method == "iterative":
                    concentrations, rmse_map, fitted_od, solver_info = (
                        processing.solve_unmixing_iterative(
                            od_cube,
                            A,
                            led_wl,
                            led_em,
                            chrom_spectra,
                            wls,
                            chromophore_names=chrom_names,
                            include_background=False,
                            background_value=bg_value,
                            scattering_parameters=scattering_parameters,
                        )
                    )
                    active_A = solver_info.get("A_used", A)
                else:
                    concentrations, rmse_map, fitted_od = processing.solve_unmixing(
                        od_cube,
                        A,
                        method=solver_method,
                        mus_prime=mus_prime,
                    )

                # Derived maps
                derived = processing.compute_derived_maps(concentrations, chrom_names)

                # Diagnostics
                diag = processing.compute_diagnostics(reflectance, od_cube, rmse_map, active_A)

                self.results[sample_name] = {
                    "sample_cube": sample_cube,
                    "reflectance": reflectance,
                    "od_cube": od_cube,
                    "concentrations": concentrations,
                    "fitted_od": fitted_od,
                    "rmse_map": rmse_map,
                    "derived": derived,
                    "diagnostics": diag,
                    "A": active_A,
                    "chromophore_names": chrom_names,
                    "include_background": include_background,
                    "background_value": bg_value,
                    "scattering_parameters": scattering_parameters,
                    "solver_info": solver_info,
                    "solver_method": solver_method,
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
