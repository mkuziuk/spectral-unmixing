# Kubelka-Munk Solver — Implementation Context

> Auto-generated from codebase analysis for the `feature/kubelka-munk-solver` branch.
> **Do not edit files.** This document describes the integration surface, not a plan to modify it.

---

## 1. Codebase Map

```
app/
├── main.py                           # entry point
├── core/
│   ├── __init__.py
│   ├── processing.py                  # ★ ALL solver math, matrices, dispatching
│   ├── io.py                          # image loading, CSV parsing, folder detection
│   └── export.py                      # result serialization (PNG/NPY/JSON)
├── gui_qt/
│   ├── main_window.py                 # ★ Qt window, pipeline adapter, toolbars
│   ├── worker.py                      # QObject background worker
│   ├── widgets/
│   │   └── chromophore_menu.py       # checkable menu for chromophore selection
│   ├── panels/                        # Maps, Inspector, Diagnostics, Stats, BarCharts
│   └── mpl/                           # Matplotlib canvas helpers

data/
├── leds_emission.csv                  # 3649 rows × 8 LED cols (450–939 nm)
├── penetration_depth_digitized.csv    # 628 rows, λ: 397–2002 nm, l: 0.34–3.55 cm
└── chromophores/
    ├── HbO2.csv, Hb.csv               # OMLC standard hemoglobin (250–1000 nm)
    ├── bilirubin.csv                   # standard bilirubin (250–1000 nm)
    ├── hb_agat.csv, hb_agat_extr.csv   # Agati hemoglobin variants
    ├── bili_agat.csv                   # Agati bilirubin
    ├── melanin.csv, water.csv

tests/
├── test_processing_fixed_scattering.py  # ★ model test pattern for new solvers
├── test_main_window_qt013_callbacks.py  # ★ Qt integration test pattern
├── test_chromophore_menu_qt004.py       # ChromophoreMenu behavior
├── test_pipeline_thread_qt012.py        # Threading, progress, state transitions
└── ...

features/
└── kubelka_munk_solver.md              # ★ the specification document

research-reports/
├── blb-alternatives.md                 # KM theory, equations, literature
├── diffusion-models.md                 # diffusion theory context
├── lipofundin-hb-bilirubin-phantoms.md # phantom materials and spectra
└── local-integration-context.md        # earlier integration analysis
```

---

## 2. Current Solver Architecture (`app/core/processing.py`)

### 2.1 Solver Registry

```python
# processing.py line 16
SUPPORTED_UNMIXING_METHODS: tuple[str, ...] = ("ls", "nnls", "mu_a")
```

The `"iterative"` solver is *not* in this tuple — it has its own entry point
`solve_unmixing_iterative()`.  The dispatcher `solve_unmixing()` (line ~537) handles
`ls`/`nnls`/`mu_a` only.  A KM solver can follow either pattern (dispatched or
standalone).

### 2.2 Solver Dispatch Pattern

```python
def solve_unmixing(od_cube, A, method="ls", mus_prime=None) -> tuple:
    # → concentrations (H,W,n_components), rmse_map (H,W), fitted_od (H,W,n_bands)
    if method == "nnls":  return _solve_unmixing_nnls(od_cube, A)
    if method == "mu_a":  return _solve_unmixing_mu_a(od_cube, A, mus_prime)
    if method == "ls":    return _solve_unmixing_ls(od_cube, A)
    raise ValueError(f"Unsupported: {method!r}. Expected {SUPPORTED_UNMIXING_METHODS}.")
```

Each internal solver returns `(concentrations, rmse_map, fitted_od)`.
The iterative solver returns a 4-element tuple adding `solver_info`.

### 2.3 Matrix Builders (pre-existing)

| Function | Returns | Used by |
|---|---|---|
| `build_overlap_matrix()` | `Aₙₖ = lⁿ·εₖⁿ` | ls, nnls, iterative |
| `build_absorption_matrix()` | `Eₙₖ = εₖⁿ` | mu_a |
| `build_fixed_scattering_profile()` | μs' per band | mu_a, iterative |

These share the internal `_normalized_led_profiles()` helper which
area-normalizes LED emission spectra and returns a common wavelength grid.

### 2.4 Scattering Defaults

```python
# processing.py lines 19-24
SCATTERING_REFERENCE_WAVELENGTH_NM = 500.0
SCATTERING_MU_S_500_CM1 = 120.0
SCATTERING_POWER_B = 1.0
SCATTERING_LIPOFUNDIN_FRACTION = 0.25
SCATTERING_ANISOTROPY_G = 0.8
```

The scattering law is:
```
μs(λ) = μs(500) · (λ/500)^(-b) · f_lipo
μs'(λ) = μs(λ) · (1 - g)
```

---

## 3. Main Window Integration Points (`app/gui_qt/main_window.py`)

### 3.1 Solver Combo Construction

```python
# main_window.py line ~397 (in _build_toolbar)
solver_combo.addItems(["ls", "nnls", "mu_a", "iterative"])
```

Adding a KM solver requires adding `"km"` (or similar) to this list.

### 3.2 Solver-Dependent Control Visibility

```python
# main_window.py ~line 1640 (in _set_solver_dependent_controls)
def _set_solver_dependent_controls(self, solver_method: str) -> None:
    use_fixed_scattering = self._uses_fixed_scattering_solver(solver_method)
    use_iterative_controls = solver_method == "iterative"
    use_background_controls = solver_method != "mu_a"
    # ... toggles toolbar visibility based on these booleans
```

`_uses_fixed_scattering_solver()` (line ~1524) returns True for `mu_a` and `iterative`.
For KM, decide:
- Background controls: **OFF** (KM doesn't use an OD background baseline)
- Scattering controls: **ON** (KM uses wavelength-dependent scattering `S(λ)`)
- Iterative controls: **OFF** (unless the KM solver is iterative)

### 3.3 Configuration Snapshot

```python
# main_window.py ~line 1335 (in _build_config_snapshot)
# Captures solver_method, background_parameters, scattering_parameters,
# iterative_parameters, include_background, selected_chromophores.
# For KM: scattering_parameters are needed (λ0 and power-law), background is not.
```

### 3.4 Pipeline Adapter — Where the Solver is Called

```python
# main_window.py ~lines 1400-1520 (in _make_pipeline_adapter)
def _pipeline():
    # 1. Load data (chrom_spectra, led_em, pen_depth, ref_cube, dark_cube)
    # 2. Build solver matrix (A = overlap or absorption depending on method)
    # 3. For each sample:
    #    - load sample_cube, compute reflectance, compute OD
    #    - call solve_unmixing(...) or solve_unmixing_iterative(...)
    #    - compute derived maps, diagnostics
    # 4. Pack results into dict with stable keys
```

**KM plug-in point:** After `compute_reflectance()`, the KM solver needs
reflectance (not OD) and should return `(concentrations, rmse_map, fitted_od)`.
For compatibility, compute `fitted_od = -log10(R_KM + ε)` internally.

### 3.5 Result Payload Keys

Each sample result dict (per the pipeline adapter) must include:

```python
{
    "sample_cube": np.ndarray,        # (H,W,N_bands) original intensities
    "reflectance": np.ndarray,        # (H,W,N_bands)
    "od_cube": np.ndarray,            # (H,W,N_bands) from compute_optical_density
    "concentrations": np.ndarray,     # (H,W,n_components) ★ panels consume this
    "fitted_od": np.ndarray,          # (H,W,N_bands) ★ panels consume this
    "rmse_map": np.ndarray,           # (H,W) ★ panels and diagnostics consume this
    "derived": dict,                  # {"THb": ..., "StO2": ...}
    "derived_maps": dict,             # same as derived (duplicate for compatibility)
    "diagnostics": dict,              # from compute_diagnostics
    "A": np.ndarray,                  # solver matrix
    "chromophore_names": list[str],
    "include_background": bool,
    "background_value": float,
    "background_parameters": dict,
    "scattering_parameters": dict,
    "iterative_parameters": dict,
    "solver_info": dict | None,       # KM metadata (parameters, fit stats)
    "solver_method": str,
    "wavelengths": list[int],
}
```

All keys must be present for panels (`maps_panel.show_results()`, `inspector_panel.set_data()`,
`stats_panel.set_data()`) to work without modification.  `concentrations`, `rmse_map`,
and `fitted_od` are non-optional; others may be empty/None for KM.

### 3.6 Chromophore Menu

The `ChromophoreMenu` widget (`app/gui_qt/widgets/chromophore_menu.py`) creates
checkable actions from filenames in `data/chromophores/*.csv`.  `load_chromophore_spectra()`
returns `{name: (wavelengths_array, extinction_array)}` mapped from CSV basenames.

**Available Agati chromophores:**
- `bili_agat` ← from `bili_agat.csv` (header: `wavelength_nm,extinction_coefficient`, 280 rows, 300–550 nm)
- `hb_agat` ← from `hb_agat.csv` (header: `lambda,extinction_coefficient`, 681 rows, 320–1000 nm)
- `hb_agat_extr` ← from `hb_agat_extr.csv` (header: `lambda,extinction_coefficient`, 681 rows, 320–1000 nm)

**Forcing these in tests/validation:** The menu automatically loads all CSV files.
To restrict to `bili_agat` and `hb_agat_extr`, either:
1. Deselect others in the UI before running, or
2. Pass `chromophore_names=["bili_agat", "hb_agat_extr"]` directly to the matrix builder
   in the pipeline adapter (bypassing the menu selection).

---

## 4. Kubelka-Munk Physical Model

### 4.1 Forward Model

For a semi-infinite homogeneous scattering medium:

```
R∞(λ) = 1 + K(λ)/S(λ) − √((K(λ)/S(λ))² + 2·K(λ)/S(λ))
```

Where:
- `K(λ) = c_hb · ε_hb_agat(λ) + c_bili · ε_bili_agat(λ)`  [absorption-like]
- `S(λ) = s₀ · (λ/λ₀)^(-b)`  [scattering-like; power law]

### 4.2 Band Integration

Follow the same `_normalized_led_profiles()` pattern used by `build_overlap_matrix()`:
1. Area-normalize each LED emission profile `φ_n(λ)`
2. Interpolate chromophore spectra onto the common LED wavelength grid
3. Band-average:
   ```
   ε_k^(n) = ∫ φ_n(λ) · ε_k(λ) dλ
   S^(n)   = ∫ φ_n(λ) · S(λ) dλ
   ```

Then for each pixel, the KM reflectance per LED band is:
```
R_KM^(n) = 1 + K^n/S^n − √((K^n/S^n)² + 2·K^n/S^n)
```

Where `K^n = c_hb · ε_hb^(n) + c_bili · ε_bili^(n)`.

### 4.3 Inverse Problem

For each pixel, fit:
```
x = [c_hb, c_bili, s₀]
```
Constraints: `c_hb ≥ 0`, `c_bili ≥ 0`, `s₀ > 0`, optionally `0.2 ≤ b ≤ 3.0`.

Minimize reflectance residuals:
```
minₓ Σₙ (R_measured^(n) − R_KM^(n)(x))²
```

Use `scipy.optimize.least_squares` with bounds.

### 4.4 Key Differences from Existing Solvers

| Aspect | LS/NNLS/mu_a | KM |
|---|---|---|
| Input domain | OD (optical density) | R (reflectance, 0–1) |
| Forward model | Linear (A·x = y) | Nonlinear (KM equation) |
| Background | OD nuisance column | Handled by scattering S(λ) |
| Scattering | Fixed prior (mu_a solver) | Fitted per-pixel or per-sample (s₀) |
| Solver | `lstsq` / `nnls` / analytic | `least_squares` with bounds |

### 4.5 Output Compatibility

To keep panels working:
```python
fitted_od = -np.log10(R_KM + 1e-10)
```

Use `eps=1e-10` consistent with `compute_optical_density()`.

---

## 5. Test Data

### 5.1 Image Directory

```
liquid_phantoms_for_unmixing_dng_cropped/
├── A1/  A2/  A3/  A4/  A5/  A6/    # samples (PNG files, 50×50 px)
├── ref/                              # white reference
└── dark_ref/                         # dark frame
```

Each A* folder contains 8 PNG files named `450nm.png`, `517nm.png`, etc.
Image resolution: **50×50 px** (850×678 in the JPEG set).

### 5.2 Wavelengths

```
450, 517, 671, 775, 803, 851, 888, 939 nm
```

### 5.3 Phantom Ground Truth

| Sample | Hb (µM) | Bilirubin (µM) |
|---|---:|:---:|
| A1 | 100 | 270 |
| A2 | 100 | 135 |
| A3 | 100 | 67.5 |
| A4 | 100 | 33.75 |
| A5 | 100 | 16.875 |
| A6 | 100 | 8.4375 |

Bilirubin **halves** each step (A1→A2→A3→…).  Hb is **constant**.

### 5.4 Spectral Data

Use these chromophore spectra from `data/chromophores/`:

| File | Name in dict | Wavelength range | Points |
|---|---|---|---|
| `hb_agat_extr.csv` | `hb_agat_extr` | 320–1000 nm | 681 |
| `bili_agat.csv` | `bili_agat` | 300–550 nm | 280 |

**Important:** `bili_agat.csv` has a *different* column header (`wavelength_nm,extinction_coefficient`)
from most other chromophores (`lambda,extinction_coefficient`), but `_load_two_column_csv()` skips
the header and reads float columns regardless — this is handled transparently.

`bili_agat` spectrum ends at 550 nm. The LED bands at 671+ nm will need `fill_value="extrapolate"`
from `scipy.interpolate.interp1d` (already the default in `_interpolate_chromophore_spectra`).

---

## 6. Integration Checklist (Processing Module)

### 6.1 New Functions in `app/core/processing.py`

```python
# 1. KM-specific band basis builder
def build_km_band_basis(
    led_emission_wl,        # (M,) common wavelength grid
    led_emission,           # {led_nm: (M,) emission}
    chromophore_spectra,    # {name: (wl, coeff)}
    led_wavelengths,        # [450, 517, ...]
    chromophore_names,      # e.g. ["hb_agat_extr", "bili_agat"]
) -> tuple:
    """
    Returns (E_band, wavelengths) where E_band[n,k] = band-averaged ε_k^n.
    Follows _normalized_led_profiles + _interpolate_chromophore_spectra pattern.
    """

# 2. KM scattering model (band-averaged)
def build_km_scattering_profile(
    led_emission_wl,
    led_emission,
    led_wavelengths,
    s0,                     # scattering amplitude
    lambda0_nm=500.0,
    power_b=1.0,
) -> np.ndarray:
    """
    Returns S_band[n] = ∫ φ_n(λ) · s0 · (λ/λ0)^{-b} dλ
    """

# 3. KM forward reflectance
def km_reflectance_bulk(
    K_band,                 # (N_pixels, N_bands) band-averaged absorption per pixel
    S_band,                 # (N_bands,) band-averaged scattering
    eps=1e-10,
) -> np.ndarray:
    """
    Returns R_KM (N_pixels, N_bands).
    Vectorized KM equation: R = 1 + K/S - sqrt((K/S)² + 2·K/S)
    """

# 4. KM solver (per-pixel nonlinear fit)
def solve_unmixing_km(
    reflectance,            # (H,W,N_bands)
    E_band,                 # (N_bands,N_chrom) band-averaged extinctions
    led_emission_wl,
    led_emission,
    led_wavelengths,
    chromophore_names,
    scattering_parameters,  # λ0, b defaults
    s0_initial=120.0,
    **kwargs,
) -> tuple:
    """
    Returns (concentrations, rmse_map, fitted_od, solver_info).
    """
```

### 6.2 KM Parameter Validation

Mirror the pattern from `validate_scattering_parameters()`:
```python
KM_SCATTERING_S0_DEFAULT = 120.0
KM_SCATTERING_POWER_B_DEFAULT = 1.0
KM_SCATTERING_LAMBDA0_DEFAULT = 500.0

def get_default_km_parameters() -> dict:
    ...

def validate_km_parameters(params: dict) -> dict:
    ...
```

### 6.3 Solver Registration

Either:
- Add `"km"` to `SUPPORTED_UNMIXING_METHODS` and branch in `solve_unmixing()`, or
- Create a standalone entry point like `solve_unmixing_iterative()` and call it
  directly from the pipeline adapter.

The standalone approach (`solve_unmixing_km(...)`) matches the iterative solver
pattern and avoids modifying the existing dispatcher.

---

## 7. Integration Checklist (Main Window)

### 7.1 Solver Combo Entry

```python
# In _build_toolbar(), line ~397:
solver_combo.addItems(["ls", "nnls", "mu_a", "iterative", "km"])
```

### 7.2 Control Visibility

In `_set_solver_dependent_controls()`:
```python
use_km_controls = solver_method == "km"
# Show scattering toolbar for KM, hide background + iterative
```

Optionally, add a dedicated KM toolbar row with `s₀`, `b`, `λ₀` entries,
mirroring `_build_scattering_toolbar()`.

### 7.3 Configuration Snapshot

In `_build_config_snapshot()`, handle `solver_method == "km"`:
- Skip background parameters
- Capture KM-specific scattering parameters
- Allow `chromophore_names` to be overridden to `["hb_agat_extr", "bili_agat"]`

### 7.4 Pipeline Adapter Branch

In `_make_pipeline_adapter()`, add a branch for `solver_method == "km"`:
```python
elif snapshot["solver_method"] == "km":
    # Build KM basis
    km_E, chrom_names = processing.build_km_band_basis(
        led_wl, led_em, chrom_spectra, wls,
        chromophore_names=snapshot["selected_chromophores"],
    )
    # ... per sample:
    reflectance = processing.compute_reflectance(...)
    concentrations, rmse_map, fitted_od, solver_info = processing.solve_unmixing_km(
        reflectance, km_E, led_wl, led_em, wls, chrom_names,
        scattering_parameters=snapshot["scattering_parameters"],
    )
    # compute derived, diagnostics...
```

---

## 8. Testing Patterns

### 8.1 Core Math Tests

Follow `tests/test_processing_fixed_scattering.py` patterns:

```python
class TestKubelkaMunkSolver(unittest.TestCase):
    def test_km_reflectance_decreases_with_absorption(self): ...
    def test_km_reflectance_increases_with_scattering(self): ...
    def test_km_reflectance_bounded_0_1(self): ...
    def test_band_basis_matches_manual_integration(self): ...
    def test_km_solver_recovers_synthetic_concentrations(self): ...
    def test_km_solver_enforces_nonnegativity(self): ...
    def test_km_solver_handles_extrapolated_bili_agat_spectrum(self): ...
    def test_bili_agat_spectrum_ends_at_550nm(self): ...
```

### 8.2 Synthetic Recovery Test Pattern

```python
def test_km_solver_recovers_synthetic_concentrations(self):
    # 1. Build synthetic band extinction (E_band) for hb_agat_extr + bili_agat
    # 2. Choose true [c_hb, c_bili, s0]
    # 3. Compute synthetic reflectance via KM forward model
    # 4. Solve with solve_unmixing_km
    # 5. Assert recovered concentrations within tolerance
```

### 8.3 Phantom Validation (Integration / Script)

For the DNG-derived phantom folder:
- Load A1–A6, compute per-sample median or ROI-mean `c_hb` and `c_bili`.
- Assert bilirubin monotonically decreases: `A1 > A2 > A3 > A4 > A5 > A6`.
- Assert `log2(c_bili_Ai / c_bili_A(i+1)) ≈ 1` (halving factor).
- Assert Hb varies less than bilirubin across the series.
- Assert no NaN/inf results.

### 8.4 Qt Integration Tests

Follow `tests/test_main_window_qt013_callbacks.py` patterns:
- Test that `"km"` appears in the solver combo.
- Test that selecting `"km"` shows scattering toolbar, hides background.
- Test that running with KM produces a valid result payload (all keys present).

---

## 9. Risks and Edge Cases

### 9.1 Spectrum Range Mismatch

`bili_agat.csv` only covers 300–550 nm. The LED bands include 671, 775, 803, 851, 888, 939 nm.
`_interpolate_chromophore_spectra()` uses `fill_value="extrapolate"`, so bilirubin extinction
will be extrapolated to near-zero at long wavelengths. This is physically reasonable
(bilirubin absorbs negligibly above 550 nm), but may create extrapolation artifacts.

### 9.2 Units and Calibration

The Agati extinction coefficients in the CSV files are in **(cm⁻¹/M)** units.
Concentrations from KM fitting will be in the same units as the extinction coefficients
(typically M, assuming K encodes the same scale). A calibration factor may be needed
to convert fitted values to µM.

### 9.3 LED Band Count

With only 8 bands and 3 parameters per pixel (c_hb, c_bili, s₀), the problem is
well-posed, but bilirubin sensitivity is limited to only 2–3 blue/green bands
(450 and 517 nm). The 671–939 nm bands contribute mainly to scattering estimation.

### 9.4 Per-Pixel Optimization Cost

`scipy.optimize.least_squares` per pixel on a 50×50 image (2500 pixels) with
3 parameters each = ~7500 optimizations. This may be slow. Consider:
- Stage 1: fit scattering (`s₀`) from sample-level ROI averages
- Stage 2: solve concentrations per pixel with fixed scattering (reduces per-pixel problem to 2 params)
- Stage 3: full per-pixel fit for final validation

### 9.5 Reflectance Calibration

KM expects diffuse reflectance (0–1). The current `compute_reflectance()` returns
`(I - Idark) / (I0 - Idark)`, which may produce values > 1 or < 0 due to noise.
Clip or handle out-of-range values before KM fitting.

### 9.6 KM Coefficient Identity

KM `K` and `S` are phenomenological, not directly equal to physical `μa` and `μs'`.
The empirical relationship `K ≈ 2·μa`, `S ≈ μs'` holds approximately in the diffuse
regime but is not exact. For concentration estimation, this is acceptable; for
absolute optical property recovery, it may introduce systematic bias.

---

## 10. Key Files with Line References

| File | Lines | Content |
|---|---|---|
| `app/core/processing.py:14-16` | `SUPPORTED_UNMIXING_METHODS` tuple | Add `"km"` here if using dispatcher |
| `app/core/processing.py:19-24` | Scattering defaults | Reuse or extend for KM |
| `app/core/processing.py:349-374` | `_normalized_led_profiles()` | Band integration helper to reuse |
| `app/core/processing.py:377-404` | `_interpolate_chromophore_spectra()` | Chromophore interpolation to reuse |
| `app/core/processing.py:537-552` | `solve_unmixing()` dispatcher | Branch point if using dispatcher pattern |
| `app/core/processing.py:149-181` | `build_fixed_scattering_spectrum()` | Pattern for scattering profile builder |
| `app/gui_qt/main_window.py:~397` | Solver combo items | Add `"km"` |
| `app/gui_qt/main_window.py:~1640` | `_set_solver_dependent_controls()` | KM visibility rules |
| `app/gui_qt/main_window.py:~1335` | `_build_config_snapshot()` | KM config capture |
| `app/gui_qt/main_window.py:~1400-1520` | `_make_pipeline_adapter()` | KM pipeline branch |
| `app/core/io.py:150-155` | `load_chromophore_spectra()` | How CSV→name mapping works |
| `app/core/io.py:179-191` | `_load_two_column_csv()` | CSV parser (header skipped) |

---

## 11. Unresolved Questions

1. **Calibration factor:** Do the Agati extinction coefficients need a multiplicative
   calibration to match the phantom concentration scale (µM)?
2. **s₀ per-pixel vs per-sample:** Should `s₀` be fitted per-pixel, per-sample, or
   globally across all A1–A6?
3. **Scattering exponent b:** Should `b` be fixed at 1.0 or fitted? Fitting adds
   a 4th parameter and may be underconstrained with only 8 bands.
4. **Reflectance saturation:** Are there pixels in the DNG images where R ≈ 0 or
   R ≈ 1 that would break the KM equation?
5. **KM solver name:** Use `"km"`, `"kubelka_munk"`, or something else in the UI?
   The feature doc says `km`.
