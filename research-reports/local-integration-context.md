# Integration Context: Physical Forward Models for Lipofundin Phantoms

## 1. Repository Snapshot

**Purpose:** Biomedical hyperspectral unmixing — convert 8-band LED image cubes into chromophore concentration maps.
**Current version:** 0.2.2 (PySide6-only desktop app).
**Data:** Lipofundin-based liquid phantoms (A1–A6) imaged at 8 LED wavelengths: **450, 517, 671, 775, 803, 851, 888, 939 nm**. Chromophores: HbO₂, Hb, bilirubin, melanin, water (spectra 250–1000 nm, 376 points each).

---

## 2. Current Pipeline (Data Flow)

```
Root folder (samples/ + ref/ + dark_ref/)
    │
    ├── io.load_image_cube(folder, wavelengths) → (H, W, 8) float64
    │
    ├── processing.compute_reflectance(sample, ref, dark) → R(i,j,λ)
    │       R = (I - I_dark) / (I0 - I_dark + ε)
    │
    ├── processing.compute_optical_density(R) → OD(i,j,λ)
    │       OD = -log10(R + ε)
    │
    ├── build_overlap_matrix(...) → A ∈ ℝ^{8 × (n_chrom + 1_bg)}
    │       A[n,k] = ∫ φ_n(λ) · l(λ) dλ  ·  ∫ φ_n(λ) · ε_k(λ) dλ
    │   OR
    │   build_absorption_matrix(...) → E ∈ ℝ^{8 × n_chrom}
    │       E[n,k] = ∫ φ_n(λ) · ε_k(λ) dλ
    │
    ├── solve_unmixing(OD, A, method) → concentrations, rmse, fitted_OD
    │       ls   : numpy.linalg.lstsq (unconstrained)
    │       nnls : scipy.optimize.nnls (non-negative)
    │       mu_a : OD→μa inversion via fixed μs'(λ), then nnls on μa
    │       iterative : nnls with iteratively updated pathlength (diffusion-inspired)
    │
    └── compute_derived_maps() → THb, StO₂
        compute_diagnostics() → condition, warnings
```

---

## 3. Current Model Equations

### 3a. Overlap Matrix (LS/NNLS/iterative solvers)

The core forward model is a **modified Beer-Lambert law** using band-integrated quantities:

```
OD^n = l^n · Σ_k c_k · ε_k^n    ( + background_basis^n )

where:
  l^n      = ∫ φ_n(λ) · l(λ) dλ          (band-average pathlength)
  ε_k^n    = ∫ φ_n(λ) · ε_k(λ) dλ         (band-average extinction)
  φ_n(λ)   = area-normalized LED emission profile
  l(λ)     = penetration_depth_digitized.csv (interpolated)
  ε_k(λ)   = chromophore extinction spectra
  c_k      = chromophore concentrations (fitted per pixel)
```

**Matrix form:** `y = A · x`,  `A ∈ ℝ^{8 × (n_chrom + optional_bg)}`

### 3b. μa Inversion (mu_a solver)

A **fixed-scattering diffusion approximation** relating OD to absorption:

```
OD(λ) = μa(λ) / sqrt(3 · μa(λ) · (μa(λ) + μs'(λ)))

Inverted analytically:
  μa(λ) = 3 · μs'(λ) · OD(λ)² / (1 - 3 · OD(λ)²)

Then chromophore fit:
  μa(λ) ≈ Σ_k c_k · ε_k(λ)     (solved via nnls)
```

### 3c. Iterative Solver Pathlength

Uses diffusion-theory effective pathlength:

```
μ_eff = sqrt(3 · μa · (μa + μs'))
l_eff = 1 / μ_eff
```

Iterates: estimate concentrations → compute μa → compute l_eff → rebuild A → re-solve.

### 3d. Scattering Prior Parameters

Hard-coded defaults for Lipofundin phantoms:

| Parameter | Symbol | Default | Description |
|-----------|--------|---------|-------------|
| λ₀ | `lambda0_nm` | 500 nm | Reference wavelength |
| μs(λ₀) | `mu_s_500_cm1` | 120 cm⁻¹ | Scattering coefficient at λ₀ |
| b | `power_b` | 1.0 | Power-law exponent |
| f_lipo | `lipofundin_fraction` | 0.25 | Lipofundin fraction |
| g | `anisotropy_g` | 0.8 | Anisotropy factor |

Scattering law: `μs(λ) = μs(500) · (λ/500)⁻ᵇ · f_lipo`
Reduced scattering: `μs'(λ) = μs(λ) · (1 - g)`

---

## 4. Data Files

| File | Path | Description |
|------|------|-------------|
| LED emission | `data/leds_emission.csv` | 3649 wavelength points × 8 LED columns (450,517,671,775,803,851,888,939 nm); some negative values present |
| Penetration depth | `data/penetration_depth_digitized.csv` | 628 points, λ ≈ 397–2002 nm, l ≈ 0.34–3.55 cm |
| HbO₂ | `data/chromophores/HbO₂.csv` | 376 points, 250–1000 nm, ε ∈ [273, 524280] |
| Hb | `data/chromophores/Hb.csv` | 376 points, 250–1000 nm, ε ∈ [207, 552160] |
| Bilirubin | `data/chromophores/bilirubin.csv` | 376 points, 250–1000 nm, ε ∈ [55, 54944] |
| Melanin | `data/chromophores/melanin.csv` | 376 points, 250–1000 nm, ε ∈ [93, 5775] |
| Water | `data/chromophores/water.csv` | 376 points, 250–1000 nm, ε ∈ [0, 0.49] |
| Sample images | `liquid_phantoms_for_unmixing_cropped/A{1..6}/` | 850×678 px, JPEG, 8 bands each |
| Reference | `.../ref/` | 8 images |
| Dark ref | `.../dark_ref/` | 8 images |
| DNG version | `liquid_phantoms_for_unmixing_dng_cropped/` | Same structure, DNG raw files |

**Wavelength range of available data:** 250–1000 nm for chromophores, 195–1100+ nm for LEDs. The LED emission CSV goes from ~195 nm to >1100 nm.

---

## 5. Solver Comparison

| Feature | `ls` | `nnls` | `mu_a` | `iterative` |
|---------|------|--------|--------|-------------|
| Background | ✓ | ✓ | ✗ | ✓ |
| Scattering params | ✗ | ✗ | ✓ | ✓ |
| Iterative pathlength | ✗ | ✗ | ✗ | ✓ |
| Non-negativity | ✗ | ✓ | ✓ (via nnls after μa) | ✓ (nnls inner loop) |
| UI solver_combo entry | 0th | 1st | 2nd | 3rd |

**Solver matrix types:**
- LS/NNLS: overlap matrix A (8 × [n_chrom + bg]), uses penetration depth
- mu_a: absorption matrix E (8 × n_chrom), no background
- Iterative: starts with A (overlap), updates pathlength each iteration

---

## 6. Integration Points for Alternative Physical Models

### 6a. Diffusion Approximation (already partially present)

The `mu_a` solver already implements a diffusion-based inversion `OD → μa`. Integration points:

- **Entry:** `app/core/processing.py` lines 383–450 (`_od_to_mu_a`, `_mu_a_to_od`, `_solve_unmixing_mu_a`)
- **Scattering prior:** `build_fixed_scattering_spectrum()` lines 149–181
- **Effective pathlength:** `estimate_effective_pathlength()` lines 479–522 (uses `μ_eff = sqrt(3·μa·(μa+μs'))`)
- **To change:** Replace the inversion formula (currently `OD²/(1-3·OD²)`), add wavelength-dependent refractive index, or use a different diffusion solution (e.g., Farrell diffusion, Kienle Patterson).

### 6b. Kubelka-Munk Model

Not implemented. Integration points:

- **New function in** `app/core/processing.py` — e.g., `solve_kubelka_munk(reflectance, K, S)`
- **Requires:** K(λ) = absorption coefficient (from chromophores), S(λ) = scattering coefficient (from Lipofundin model)
- **KM reflectance:** `R∞ = 1 + K/S - sqrt((K/S)² + 2·K/S)`
- **Pipeline hook:** In `_make_pipeline_adapter()` (main_window.py lines ~1421–1520), after `compute_reflectance()`, route to KM inversion instead of OD.
- **Data needed:** Same chromophore and scattering data already loaded.
- **Constraint:** KM is a two-flux model for diffuse illumination; LED illumination might be partially collimated — may need collimated correction (Saunderson correction).

### 6c. Monte Carlo (MC) Lookup or Surrogate

Not implemented. Integration points:

- **Precomputation:** Generate a lookup table (LUT) or neural-network surrogate for `R(μa, μs', g, n)` using MCX or similar.
- **Inverse:** For each pixel's reflectance spectrum, search/best-fit `μa(λ)`, then chromophore unmix.
- **Integration hook:** Replace `_solve_unmixing_mu_a` with a LUT-based inversion. The `mu_a` solver path is the natural replacement target.
- **Common-MC formats to support:** `μa`, `μs'`, `g`, anisotropy, refractive index `n`.
- **Risk:** 8 bands severely limit degrees of freedom; MC inversion would need strong priors.

### 6d. PLS / Partial Least Squares

Not implemented. Integration points:

- **New function in** `app/core/processing.py` or a new `app/core/pls.py` module.
- **Approach:** Pre-calibrate PLS regression coefficients from phantom measurements with known chromophore concentrations; apply as `c = W · OD_spectrum`.
- **Data need:** Requires training data with ground-truth concentrations.
- **Usage:** Would be a new solver method — add `"pls"` to `SUPPORTED_UNMIXING_METHODS`, new entry in solver_combo, and a branch in `solve_unmixing()`.

---

## 7. UI / Control Flow for New Solvers

### How to add a solver to the GUI:

1. **`app/core/processing.py`:**
   - Add method string to `SUPPORTED_UNMIXING_METHODS` (line 14)
   - Add a `solve_unmixing_<method>()` function with signature matching existing solvers: `(od_cube, A_or_params, ...) → (concentrations, rmse_map, fitted_od)`
   - Add branch in `solve_unmixing()` dispatcher (lines 537–552)

2. **`app/gui_qt/main_window.py`:**
   - Add item to `solver_combo` (line ~397: `["ls", "nnls", "mu_a", "iterative"]`)
   - Optionally add toolbar controls for method-specific parameters (follow `_build_scattering_toolbar` / `_build_iterative_toolbar` pattern)
   - Handle visibility in `_set_solver_dependent_controls()` (lines ~1640–1667)
   - Add parameter reading in `_build_config_snapshot()` (lines ~1335–1394)
   - Add solver call in `_make_pipeline_adapter()` (lines ~1400–1520)

3. **`app/core/export.py`:** No changes needed if signature matches.

### UI visibility rules:

| Solver | Background toolbar | Scattering toolbar | Iterative toolbar |
|--------|-------------------|-------------------|-------------------|
| ls | ✓ | ✗ | ✗ |
| nnls | ✓ | ✗ | ✗ |
| mu_a | ✗ | ✓ | ✗ |
| iterative | ✓ | ✓ | ✓ |
| *(new)* | *if supports bg* | *if needs scattering* | *if iterative* |

---

## 8. Constraints and Risks

### Spectral Constraints
- **Only 8 LED bands** (450, 517, 671, 775, 803, 851, 888, 939 nm) → severely limits model complexity.
- **Current overlap matrix** is at most 8×6 (5 chromophores + background). A more complex model must be low-degree-of-freedom.
- **LED emission profiles** contain some negative values (raw spectrometer data) — currently normalized to area=1, but negative values may cause integration artifacts.
- **Penetration depth** data extends to 2002 nm, but chromophore spectra only to 1000 nm — interpolation beyond range uses `fill_value="extrapolate"`.

### Physical Model Risks
- **Diffusion approximation** (`mu_a` solver) is valid only for `μa << μs'` and far from boundaries. For liquid phantoms with Lipofundin, this may hold at some wavelengths but not all.
- **Current OD→μa formula** (`OD²/(1-3·OD²)`) becomes singular when `3·OD² = 1` (OD ≈ 0.577). Many pixels may approach or exceed this.
- **Constant scattering prior** (`b=1.0`, `μs₅₀₀=120 cm⁻¹`) is a fixed assumption — does not adapt to different phantom batches or concentrations.

### Code Integration Risks
- **Processing.py** is already 700+ lines — adding more models needs careful organization (consider a `models/` subpackage).
- **The iterative solver** has complex convergence logic, fallback paths, and best-iterate tracking — any new iterative scheme should follow the same pattern.
- **The `mu_a` solver** currently handles `OD→μa` per-pixel in Python loop (`_solve_unmixing_mu_a` lines 450–483) — this is slow and would benefit from vectorization before extension.

---

## 9. Recommended Next Files to Read

| File | Why |
|------|-----|
| `app/core/processing.py` | Central math — all solver logic, matrix building, scattering prior |
| `app/gui_qt/main_window.py` (lines 1330–1520) | Pipeline adapter — how solvers are called with UI params |
| `app/gui_qt/main_window.py` (lines 350–600) | Toolbar construction — where new solver controls would go |
| `app/core/io.py` | Data loading — understanding file formats and interpolation |
| `data/leds_emission.csv` | Raw LED spectra — wavelength range, quality, negative values |
| `features/background_model_research.md` | Prior research on scattering vs. background alternatives |
| `tests/test_processing_fixed_scattering.py` | Test patterns for scattering-dependent solvers |

---

## 10. Open Questions

1. Are the phantom formulations documented anywhere? (What are the actual μa, μs', g values per phantom A1–A6?)
2. Is the current penetration_depth_digitized.csv derived from diffusion theory or Monte Carlo for Lipofundin phantoms?
3. Would a hybrid approach (Kubelka-Munk for visible, diffusion for NIR) be appropriate given the 8-band coverage from 450–939 nm?
4. Are there reference measurements (e.g., spectrometer-based μa, μs' characterisation) available for validation?
5. For PLS — is there a calibration phantom set with known chromophore concentrations?
