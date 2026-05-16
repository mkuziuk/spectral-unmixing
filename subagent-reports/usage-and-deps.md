# Usage & Dependencies — Code Context

## Files Retrieved

### Core modules
1. `app/main.py` (lines 1-63) — CLI entry point; always launches the PySide6 GUI.
2. `app/core/processing.py` (lines 1-675) — all math: reflectance, optical density, overlap/absorption matrix builders, LS/NNLS/mu_a/iterative solvers, diagnostics, derived maps.
3. `app/core/io.py` (lines 1-253) — folder detection, image cube loading (JPEG via PIL, DNG via rawpy), CSV loading for chromophores, LEDs, penetration depth.
4. `app/core/export.py` (lines 1-136) — saving results (PNG maps via matplotlib Agg, NPY arrays, JSON metadata).

### GUI modules
5. `app/gui_qt/main_window.py` (lines 1-2371) — PySide6 main window: toolbars (solver selector, background/scattering/iterative parameter controls), tab panels, **pipeline adapter** (`_make_pipeline_adapter`) that wires the core pipeline to the GUI.
6. `app/gui_qt/worker.py` (lines 1-89) — `PipelineWorker` (QObject) for background thread execution; uses signals for progress/results/failure.
7. `app/gui_qt/panels/diagnostics_panel.py` (lines 1-199) — RMSE histogram, quality mask, metric display.
8. `app/gui_qt/panels/inspector_panel.py` (lines 1-316) — pixel inspector: click-to-view OD spectra, fit, residuals, concentrations.

### Dependency & config files
9. `pyproject.toml` (lines 1-16) — project metadata, dependency list (`numpy`, `scipy`, `matplotlib`, `PySide6`, `pillow`, `rawpy`), entry point `app.main:main`.
10. `requirements.txt` (lines 1-6) — same six packages.
11. `spectral-unmixing.spec` (lines 1-62) — PyInstaller spec; lists hidden imports used for Windows `.exe` build.
12. `.github/workflows/build-windows.yml` (lines 1-41) — CI/CD: builds Windows exe via pyinstaller, publishes release on tags.

### Design docs & feature notes
13. `features/spectral_unmixing.md` — original spec: describes overlap matrix, Beer-Lambert model, LS solver, pixelwise pipeline, derived maps.
14. `features/nnls.md` — brief note on adding NNLS solver + background column value change.
15. `features/background_model_research.md` — analysis of why constant background is a binary switch; proposes polynomial basis, regularization, fixed-scattering alternatives.
16. `features/custom_data_folder_support.md` — design for user-selectable data folder with validation.
17. `AGENT.md` — project-level guidance for coding agents.

### Tests
18. `tests/test_processing_fixed_scattering.py` — comprehensive unit tests for mu_a solver, iterative solver, overlap matrix, background profiles, validation hardening.
19. `tests/test_background_consistency.py` — end-to-end test with real sample data confirming background-value behavior (bg=2500 and bg=100 give identical chromophore maps; only bg=0 differs).

### Data
20. `data/leds_emission.csv` — wavelength (195-310 nm) + 8 LED columns (450, 517, 671, 775, 803, 851, 888, 939 nm).
21. `data/penetration_depth_digitized.csv` — wavelength (396-2002 nm), depth (mm).
22. `data/chromophores/HbO2.csv` — lambda (250-1000 nm), extinction_coefficient.
23. `data/chromophores/Hb.csv`, `melanin.csv`, `bilirubin.csv`, `water.csv`, `hb_agat.csv` — same format.

---

## Architecture

### Pipeline (data flow)

```
Root folder (sample/ + ref/ + dark_ref/)
  │
  ├─ detect_folders()          → sample paths, ref_dir, dark_dir, wavelengths
  ├─ load_image_cube()         → (H, W, N_bands) float64 arrays [PIL/rawpy]
  │
  ├─ compute_reflectance()     → R = (I - I_dark) / (I_0 - I_dark)
  ├─ compute_optical_density() → OD = -log10(R + ε)
  │
  ├─ Data folder (leds_emission.csv + penetration_depth*.csv + chromophores/*.csv)
  │   ├─ load_led_emission()         → common_wl, emission dict
  │   ├─ load_penetration_depth()    → penetration_wl, depth
  │   └─ load_chromophore_spectra()  → {name: (wl, coeff)}
  │
  ├─ Matrix builder (called once per config):
  │   ├─ build_overlap_matrix()      → A ∈ R^{N_LED × (N_chrom + background)}
  │   │   (used by ls/nnls/iterative)
  │   └─ build_absorption_matrix()   → E ∈ R^{N_LED × N_chrom}
  │       (used by mu_a; no pathlength/background)
  │   └─ build_fixed_scattering_profile() → μs'(λ) per band (mu_a/iterative)
  │
  ├─ Solver (per sample):
  │   ├─ solve_unmixing(od_cube, A, method="ls|nnls|mu_a")
  │   │   → concentrations, rmse_map, fitted_od
  │   └─ solve_unmixing_iterative(od_cube, static_A, ...)
  │       → concentrations, rmse_map, fitted_od, solver_info
  │
  ├─ compute_derived_maps()    → THb, StO2
  ├─ compute_diagnostics()     → condition number, NaN count, warnings
  └─ save_results()            → PNG maps, NPY arrays, JSON metadata
```

### Unmixing methods (4 solvers)

| Method | Matrix | Background Support | Base Library | Notes |
|--------|--------|-------------------|-------------|-------|
| `ls` | Overlap (A) | Yes | `numpy.linalg.lstsq` | Unconstrained least-squares |
| `nnls` | Overlap (A) | Yes | `scipy.optimize.nnls` | Non-negative least-squares |
| `mu_a` | Absorption (E) | No | `scipy.optimize.nnls` | Fixed-scattering OD→μa inversion then NNLS |
| `iterative` | Overlap (A) | Yes | `scipy.optimize.nnls` | NNLS with iteratively updated effective pathlength; includes fallback |

The solver is selected from a dropdown in the UI (`"ls"`, `"nnls"`, `"mu_a"`, `"iterative"`).

### Background model (3 variants)
Controlled by UI dropdown: `"constant"` (default 2500.0), `"exponential"`, `"slope"`. Only applies to ls/nnls/iterative. The constant model is known to be a binary switch (any nonzero value yields identical chromophore maps — confirmed by `test_background_consistency.py`).

### Fixed-scattering parameters (mu_a & iterative)
- `lambda0_nm` = 500.0
- `mu_s_500_cm1` = 120.0
- `power_b` = 1.0
- `lipofundin_fraction` = 0.25
- `anisotropy_g` = 0.8

### Iterative solver parameters
- `max_iter` = 25
- `tol_rel` = 1e-4
- `tol_rmse` = 1e-6
- `damping` = 0.5
- `initial_concentration` = 1e-4

---

## External Dependencies

### Runtime (required)
| Package | Import | Used In | Purpose |
|---------|--------|---------|---------|
| `numpy` | `np` | `app/core/*.py` | Arrays, `linalg.lstsq`, math, vectorized pixel ops |
| `scipy` | `scipy.optimize.nnls`, `scipy.interpolate.interp1d` | `app/core/processing.py` | NNLS solver, spectrum interpolation |
| `matplotlib` | `matplotlib.pyplot`, `matplotlib.backends.backend_qtagg` | `app/core/export.py`, `app/gui_qt/mpl/` | Map PNG export (`Agg`), GUI canvas (`QtAgg`) |
| `PySide6` | `PySide6.QtWidgets`, `PySide6.QtCore`, `PySide6.QtGui` | `app/gui_qt/*.py` | Desktop GUI framework |
| `pillow` | `PIL.Image` | `app/core/io.py` | JPEG/PNG image loading |

### Optional
| Package | Import | Used In | Purpose |
|---------|--------|---------|---------|
| `rawpy` | `rawpy` | `app/core/io.py` | DNG (raw camera) image loading — gracefully handled if missing |

### Build / CI
- `pyinstaller` — Windows `.exe` packaging (via `spectral-unmixing.spec`)
- `pytest`, `pytest-qt` — test suite

---

## Data folder structure (default `data/` or custom)
```
data/
├── leds_emission.csv          # Required: wavelength + one column per LED
├── penetration_depth*.csv     # Required: at least one; prefers `penetration_depth_digitized.csv`
└── chromophores/              # Required: at least one .csv
    ├── HbO2.csv
    ├── Hb.csv
    ├── melanin.csv
    ├── bilirubin.csv
    ├── water.csv
    └── hb_agat.csv
```

All CSV files are 2-column (wavelength, value) with a header row, loaded via `_load_two_column_csv()`.

---

## Key code snippets

### Solver dispatch (`processing.py` lines 366-387)
```python
SUPPORTED_UNMIXING_METHODS = ("ls", "nnls", "mu_a")

def solve_unmixing(od_cube, A, method="ls", mus_prime=None):
    if method == "nnls":
        return _solve_unmixing_nnls(od_cube, A)
    if method == "mu_a":
        return _solve_unmixing_mu_a(od_cube, A, mus_prime)
    if method == "ls":
        return _solve_unmixing_ls(od_cube, A)
    raise ValueError(...)
```

### Pipeline adapter wiring (`main_window.py` lines ~1300-1400)
The `_make_pipeline_adapter()` closure:
1. Validates data directory
2. Loads ref/dark cubes once
3. Loads chromophore spectra, LED emission, penetration depth
4. Builds solver matrix (overlap or absorption) based on method
5. Iterates sample dirs: load → reflectance → OD → solve → derived → diagnostics
6. Returns `{"samples": {...}, "chrom_scales": ..., "derived_scales": ..., "config": ...}`

---

## Start Here

Open **`app/core/processing.py`** to understand the solver implementations and matrix builders. This is where all unmixing methods live. Then look at **`app/gui_qt/main_window.py`** (`_make_pipeline_adapter`, around line 1300) to see how the full pipeline is assembled from the core modules.

---

## Constraints & risks

1. **Background model limitation**: The constant background model (default) makes the UI background-value field behave as a binary on/off — documented in `features/background_model_research.md`. Any nonzero value produces identical chromophore maps.
2. **Small number of LED bands** (8 bands: 450–939 nm). Limits how many chromophores/background terms can be identified.
3. **mu_a solver** does NOT support a background column — it uses `build_absorption_matrix()` (no pathlength) + fixed scattering prior.
4. **DNG loading** is optional (graceful ImportError) but rawpy must be installed for DNG support.
5. **Iterative solver** returns a `solver_info` dict with fallback metadata; panels and exporters do not currently surface the fallback status to the user.
6. **THb/StO2** are only computed when chromophore names include exactly `"HbO2"` and `"Hb"` (case-sensitive).
7. **Penetration depth file** is selected deterministically: prefers `penetration_depth_digitized.csv`, else lexicographically first `penetration_depth*.csv`.
