# Spectral Unmixing Methods — Inventory

> Generated: 2026-05-15  
> Scope: `/Users/mikhail/Projects/Biophotonics-lab/spectral-unmixing`

---

## 1. Unconstrained Least-Squares (`ls`)

| Attribute | Detail |
|---|---|
| **Method name** | `"ls"` |
| **Entry point** | `app/core/processing.py` → `solve_unmixing(od_cube, A, method="ls")` → `_solve_unmixing_ls()` |
| **Solver** | `numpy.linalg.lstsq` (unconstrained) |
| **Matrix A** | Overlap matrix from `build_overlap_matrix()` — LED-weighted extinction × pathlength |
| **Background** | Optional constant/exponential/slope column appended to A |
| **Lines** | `processing.py` lines 999–1031 (dispatch), 1037–1055 (impl) |
| **Evidence** | `processing.py:1019`: `if method == "ls": return _solve_unmixing_ls(od_cube, A)` |
| **Tests** | `test_background_consistency.py` lines 55–56: `_run_unmixing(od_cube, A, method='ls')` |

---

## 2. Non-Negative Least-Squares (`nnls`)

| Attribute | Detail |
|---|---|
| **Method name** | `"nnls"` |
| **Entry point** | `app/core/processing.py` → `solve_unmixing(od_cube, A, method="nnls")` → `_solve_unmixing_nnls()` |
| **Solver** | `scipy.optimize.nnls` (non-negativity constraint per pixel) |
| **Matrix A** | Overlap matrix from `build_overlap_matrix()` |
| **Background** | Optional constant/exponential/slope column appended to A |
| **Lines** | `processing.py` lines 1017–1018 (dispatch), 1061–1082 (impl) |
| **Evidence** | `processing.py:1017`: `if method == "nnls": return _solve_unmixing_nnls(od_cube, A)` |
| **Tests** | No dedicated test file; tested indirectly via iterative solver (which calls `_solve_unmixing_nnls` internally). Feature spec: `features/nnls.md` |

---

## 3. Fixed-Scattering OD→μa Inversion + NNLS (`mu_a`)

| Attribute | Detail |
|---|---|
| **Method name** | `"mu_a"` |
| **Entry point** | `app/core/processing.py` → `solve_unmixing(od_cube, A, method="mu_a", mus_prime=mus_prime)` → `_solve_unmixing_mu_a()` |
| **Solver** | Two-stage: (1) invert OD→μa using fixed scattering prior `_od_to_mu_a()`, (2) `scipy.optimize.nnls` on absorption basis |
| **Matrix A** | Absorption matrix from `build_absorption_matrix()` — LED-weighted extinction only (no pathlength overlap) |
| **Scattering prior** | Lipofundin power-law: `μs'(λ) = μs,500 · (λ/500)^(-b) · f_lipo · (1-g)` |
| **Background** | Not used (explicitly disabled) |
| **Lines** | `processing.py` lines 1021–1026 (dispatch), 1088–1142 (od↔mu_a), 1148–1178 (solver) |
| **Key functions** | `_od_to_mu_a()` (line 1088), `_mu_a_to_od()` (line 1111), `_solve_unmixing_mu_a()` (line 1148) |
| **Inversion formula** | `μa = 3·μs'·OD² / (1 − 3·OD²)` (line 1106) |
| **Evidence** | `processing.py:1021`: `if method == "mu_a": return _solve_unmixing_mu_a(od_cube, A, mus_prime)` |
| **Scattering params** | Defaults at lines 19–24: λ₀=500nm, μs'₅₀₀=120cm⁻¹, b=1.0, f_lipo=0.25, g=0.8 |
| **Tests** | `test_processing_fixed_scattering.py` — full unit test class `TestFixedScatteringSolver` |

---

## 4. Iterative Overlap-Matrix Solver (`iterative`)

| Attribute | Detail |
|---|---|
| **Method name** | `"iterative"` |
| **Entry point** | `app/core/processing.py` → `solve_unmixing_iterative(od_cube, static_A, ...)` |
| **Solver** | Iterative refinement loop: (1) estimate effective pathlength from current concentrations, (2) rebuild overlap matrix, (3) solve NNLS, (4) damp pathlength update, repeat |
| **Matrix A** | Rebuilt each iteration via `build_overlap_matrix()` using current pathlength |
| **Inner solver** | `_solve_unmixing_nnls()` (NNLS) |
| **Scattering prior** | Same Lipofundin model as `mu_a`, used in `estimate_effective_pathlength()` |
| **Convergence** | `max_iter=25`, `tol_rel=1e-4` (pathlength change), `tol_rmse=1e-6` (RMSE improvement), `damping=0.5` |
| **Background** | Optional constant/exponential/slope (same as ls/nnls) |
| **Lines** | `processing.py` lines 349–481 (iterative params), 482–688 (solver impl) |
| **Key functions** | `solve_unmixing_iterative()` at line 482, `estimate_effective_pathlength()` at line 421 |
| **Fallback** | Falls back to static overlap matrix if iterative loop errors (line 639–667) |
| **Evidence** | GUI combo includes `"iterative"` at `main_window.py:383`, dispatched via `_make_pipeline_adapter()` at line 1427 |
| **Note** | Not in `SUPPORTED_UNMIXING_METHODS` tuple (line 16) — called directly as a separate function |
| **Tests** | `test_processing_fixed_scattering.py` line 326: `test_iterative_solver_recovers_self_consistent_concentrations` |

---

## 5. Background Models (nuisance bases)

Used by `ls`, `nnls`, and `iterative` solvers. Three models:

| Model | Profile shape | Default |
|---|---|---|
| `"constant"` | Flat across all LED bands | value=2500.0 |
| `"exponential"` | Curved decay from start→end with shape/offset | start=1.0, end=0.1, shape=1.0, offset=0.0 |
| `"slope"` | Linear from start→end | start=1.0, end=0.1 |

- **Defined**: `processing.py` lines 27–42 (`SUPPORTED_BACKGROUND_MODELS`)
- **Builder**: `build_background_profile()` at line 128
- **Appended to overlap matrix**: `build_overlap_matrix()` at line 249

---

## 6. Derived Maps (post-processing)

Not unmixing methods, but computed from concentrations:

| Map | Formula | Lines |
|---|---|---|
| **THb** | `HbO2 + Hb` | `processing.py` lines 1192–1197 |
| **StO₂** | `HbO2 / (THb + ε)` | `processing.py` lines 1192–1197 |

---

## 7. Chromophore Spectra Available

Loaded from `data/chromophores/*.csv`:

| File | Chromophore |
|---|---|
| `HbO2.csv` | Oxyhemoglobin |
| `Hb.csv` | Deoxyhemoglobin |
| `hb_agat.csv` | Hemoglobin (alternate spectrum) |
| `melanin.csv` | Melanin |
| `bilirubin.csv` | Bilirubin |
| `water.csv` | Water |

---

## 8. UI Solver Selector

- **Widget**: `QComboBox` with object name `solver_combo`
- **Items**: `["ls", "nnls", "mu_a", "iterative"]`
- **File**: `app/gui_qt/main_window.py` line 383
- **Callback**: `_on_solver_method_changed()` at line 1886
- **Control visibility**: `_set_solver_dependent_controls()` at line 1860 toggles background/scattering/iterative toolbars

---

## 9. Pipeline Wiring (how methods are invoked)

All in `app/gui_qt/main_window.py` → `_make_pipeline_adapter()` (line 1384):

| Method | Matrix builder | Solver call |
|---|---|---|
| `ls` | `build_overlap_matrix(...)` | `solve_unmixing(od_cube, A, method="ls")` |
| `nnls` | `build_overlap_matrix(...)` | `solve_unmixing(od_cube, A, method="nnls")` |
| `mu_a` | `build_absorption_matrix(...)` | `solve_unmixing(od_cube, A, method="mu_a", mus_prime=mus_prime)` |
| `iterative` | `build_overlap_matrix(...)` (initial) | `solve_unmixing_iterative(od_cube, A, ...)` |

---

## 10. Key Constants

| Constant | Value | Location |
|---|---|---|
| `SUPPORTED_UNMIXING_METHODS` | `("ls", "nnls", "mu_a")` | `processing.py:16` |
| `SUPPORTED_BACKGROUND_MODELS` | `("constant", "exponential", "slope")` | `processing.py:33` |
| Scattering λ₀ | 500.0 nm | `processing.py:19` |
| Scattering μs'(500) | 120.0 cm⁻¹ | `processing.py:20` |
| Scattering b | 1.0 | `processing.py:21` |
| Lipofundin fraction | 0.25 | `processing.py:22` |
| Anisotropy g | 0.8 | `processing.py:23` |
| Iterative max iter | 25 | `processing.py:44` |
| Iterative damping | 0.5 | `processing.py:47` |
| Iterative initial conc | 1e-4 | `processing.py:48` |

---

## 11. Files That Likely Need Changes

| File | Reason |
|---|---|
| `app/core/processing.py` | Core solver implementations; adding/modifying a method touches this file |
| `app/gui_qt/main_window.py` | UI solver combo and pipeline adapter; new methods need entries here |
| `app/gui_qt/worker.py` | Pipeline threading (likely stable) |
| `app/core/io.py` | Data loading (stable unless new data formats needed) |
| `app/core/export.py` | Result export (stable) |
| `tests/test_processing_fixed_scattering.py` | Tests for mu_a and iterative solvers |
| `tests/test_background_consistency.py` | Tests for LS/NNLS with background |

---

## 12. Architecture Summary

```
User Folder (root/ref/dark_ref)
        │
        ▼
  [io.load_image_cube] ───→ sample_cube, ref_cube, dark_cube
        │
        ▼
  [processing.compute_reflectance] ───→ R(i,j,λ)
        │
        ▼
  [processing.compute_optical_density] ───→ OD(i,j,λ)
        │
        ▼
  ┌─── choose solver ───┐
  │                      │
  ▼                      ▼
ls/nnls               mu_a                iterative
  │                      │                     │
  │ overlap matrix       │ absorption matrix   │ overlap matrix
  │ (build_overlap_mat)  │ (build_absorption)  │ (rebuilt each iter)
  │                      │                     │
  ▼                      ▼                     ▼
lstsq / nnls       OD→μa inv + nnls     pathlength est. + nnls
  │                      │                     │
  └──────────────────────┴─────────────────────┘
        │
        ▼
  concentrations, rmse_map, fitted_od
        │
        ▼
  [compute_derived_maps] → THb, StO₂
  [compute_diagnostics] → condition, warnings
  [export.save_results] → PNG, NPY, JSON
```
