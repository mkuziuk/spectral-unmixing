# Algorithm Internals — Spectral Unmixing Methods

## Overview

The codebase implements four solver methods (`ls`, `nnls`, `mu_a`, `iterative`) in `app/core/processing.py` (lines 1–680). All methods share the same upstream pipeline:

```
raw image cube → reflectance → optical density (OD) → model matrix → solver → concentration maps
```

Data loading (I/O) lives in `app/core/io.py`. The pipeline adapter in `app/gui_qt/main_window.py` (lines 1507–1658) wires everything together. Chromophore extinction spectra, LED emission profiles, and penetration depth are interpolated onto a common wavelength grid before matrix construction.

---

## 1. Reflectance & Optical Density (Phase 1 — always identical)

### `compute_reflectance` (processing.py, lines 160–197)

**Math:**
```
R(i,j,λ) = (I_sample − I_dark) / (I_ref − I_dark + ε)
```
- **Inputs:** `sample_cube`, `ref_cube`, `dark_cube` — each shape `(H, W, N_bands)`, float.
- **Output:** `reflectance` — same shape, float.
- **Constraints:** All three cubes must have identical shape, be 3-D, have ≥1 band, and non-zero spatial dimensions. A tiny `eps=1e-10` prevents division by zero.
- **Location:** `app/core/processing.py:160–197`

### `compute_optical_density` (processing.py, lines 203–208)

**Math:**
```
OD(i,j,λ) = −log₁₀(R(i,j,λ) + ε)
```
- **Inputs:** `reflectance` `(H, W, N_bands)`.
- **Output:** `od_cube` — same shape, float.
- **Constraint:** Clipped below at `eps=1e-10` to avoid log(0).
- **Location:** `app/core/processing.py:203–208`

---

## 2. Model Matrices (Phase 2 — method-dependent)

### 2a. Overlap Matrix — used by `ls`, `nnls`, `iterative`

**Function:** `build_overlap_matrix` (processing.py, lines 253–336)

**Steps:**
1. Common wavelength grid from LED emission data.
2. Area-normalize each LED spectrum: `φ̂ₙ(λ) = φₙ(λ) / ∫φₙ(λ)dλ`.
3. Interpolate **penetration depth** `l(λ)` onto the grid (linear, extrapolate).
4. Interpolate chromophore **extinction spectra** `εₖ(λ)` onto the grid (linear, extrapolate).
5. For each LED band `n`:
   - Overlap pathlength: `lⁿ = ∫ φ̂ₙ(λ) · l(λ) dλ`
   - Overlap extinction: `εₖⁿ = ∫ φ̂ₙ(λ) · εₖ(λ) dλ`
   - Matrix entry: `A[n, k] = lⁿ · εₖⁿ`
6. Optionally append a **background column** (constant, exponential, or slope shape across LED bands).

**Output:** `A ∈ ℝ^{N_LED × N_components}` and `chromophore_names`.

**Location:** `app/core/processing.py:253–336`

#### Background column variants

**Constant** (default): `A[i, -1] = background_value` (default 2500.0). This is a flat offset across all LED bands.

**Exponential:** A profile shaped as:
```
profile(λ) = offset + exp_start · (exp_end/exp_start)^{t^shape}
```
where `t = (λ − λ_min) / (λ_max − λ_min)`.

**Slope:** Linear interpolation between `slope_start` at the shortest LED and `slope_end` at the longest.

**Key insight (from `features/background_model_research.md`):** A constant background column is mathematically indistinguishable from a rescaled constant — the coefficient simply absorbs the scaling. The background value acts as a binary switch (zero vs nonzero) rather than a continuous parameter. The exponential and slope variants provide genuine spectral structure, making the background basis non-trivial.

### 2b. Absorption Matrix — used by `mu_a` solver

**Function:** `build_absorption_matrix` (processing.py, lines 338–358)

**Math:** `E[n, k] = ∫ φ̂ₙ(λ) · εₖ(λ) dλ`

This is the same as the overlap matrix **without** pathlength weighting and without background. It directly represents LED-weighted extinction.

### 2c. Fixed Scattering Profile — used by `mu_a` and `iterative` solvers

**Function:** `build_fixed_scattering_profile` (processing.py, lines 360–384)

Delegates to `build_fixed_scattering_spectrum` (processing.py, lines 122–151) which computes:

```
μₛ(λ) = μₛ,500 · (λ / λ₀)^{−b} · f_lipo        (Mie scattering power law)
μₛ′(λ) = μₛ(λ) · (1 − g)                        (reduced scattering)
```

**Default parameters** (processing.py, lines 18–25):
| Parameter | Symbol | Default | Meaning |
|-----------|--------|---------|---------|
| `lambda0_nm` | λ₀ | 500 nm | Reference wavelength |
| `mu_s_500_cm1` | μₛ,500 | 120 cm⁻¹ | Scattering coefficient at reference |
| `power_b` | b | 1.0 | Power-law exponent |
| `lipofundin_fraction` | f_lipo | 0.25 | Lipofundin fraction |
| `anisotropy_g` | g | 0.8 | Anisotropy factor |

Then band-averages via integration with normalized LED profiles.

**Constraints:** λ₀ > 0, μₛ,500 > 0, f_lipo ≥ 0, 0 ≤ g < 1. Non-finite values are replaced with 0.0 with a warning.

---

## 3. Solver Methods (Phase 3)

### 3a. `ls` — Unconstrained Least-Squares

**Function:** `_solve_unmixing_ls` (processing.py, lines 415–435)

**Math:** For each pixel `p`:
```
x̂ₚ = argminₓ ‖A·x − yₚ‖²      via numpy.linalg.lstsq
```
**Inputs:**
- `od_cube` `(H, W, N_bands)`
- `A` — overlap matrix `(N_bands, N_components)`

**Outputs:**
- `concentrations` `(H, W, N_components)` — can contain negative values
- `rmse_map` `(H, W)` — per-pixel RMSE
- `fitted_od` `(H, W, N_bands)` — reconstructed OD

**Implementation detail:** Reshapes the cube to `(H·W, N_bands)`, solves in one batch via `np.linalg.lstsq(A, Y.T)`.

**Constraints:** None on concentrations. The matrix `A` must be full column rank (or at least have more rows than columns) for a unique solution.

### 3b. `nnls` — Non-Negative Least-Squares

**Function:** `_solve_unmixing_nnls` (processing.py, lines 437–460)

**Math:** For each pixel `p`:
```
x̂ₚ = argminₓ ‖A·x − yₚ‖²   subject to  x ≥ 0     via scipy.optimize.nnls
```
**Inputs/Outputs:** Same as `ls` except no negative concentrations.

**Implementation detail:** Loops over all `H·W` pixels calling `scipy.optimize.nnls(A, yₚ[i])` one at a time. This is the performance bottleneck — vectorized NNLS is not available in SciPy.

**Constraints:** All concentrations are non-negative. The background coefficient (when background is included) is also constrained non-negative.

### 3c. `mu_a` — Fixed-Scattering `OD` → `μₐ` Inversion + NNLS

**Function:** `_solve_unmixing_mu_a` (processing.py, lines 500–530)

**Two-stage pipeline:**

**Stage 1 — OD to absorption (per pixel, per band):**
```
OD_nonneg = max(OD, 0)
μₐ(λ) = 3 · μₛ′(λ) · OD_nonneg² / (1 − 3 · OD_nonneg²)
```
Only valid where `1 − 3·OD² > ε` (i.e., `OD < 1/√3 ≈ 0.577`). Invalid bands (e.g., negative OD, zero `μₛ′`, or `OD ≥ 0.577`) are masked out per pixel.

**Stage 2 — Linear absorption fit (per pixel):**
```
μₐ(λ) ≈ E(λ) · c    via scipy.optimize.nnls (non-negative)
```
Only the valid bands from Stage 1 participate in the fit.

**Then:** Reconstruct `μₐ` from fitted concentrations, map back to OD via:
```
OD = √( μₐ / (3 · (μₐ + μₛ′) + ε) )
```
(implemented as `_mu_a_to_od`, processing.py lines 486–498).

**Inputs:**
- `od_cube` `(H, W, N_bands)`
- `A` — absorption matrix `(N_bands, N_components)` (from `build_absorption_matrix`)
- `mus_prime` — band-averaged reduced scattering `(N_bands,)`

**Outputs:** Same as `ls`/`nnls`.

**Constraints:**
- No background column supported (raises `ValueError` in `_make_pipeline_adapter` if background enabled).
- Requires `mus_prime` (raises `ValueError` if missing).
- Absorption matrix must have same number of rows as OD bands.
- Physically unstable when `OD → 0.577` (diffuse reflectance model singularity).

### 3d. `iterative` — Pathlength-Updated NNLS (Iterative Solver)

**Function:** `solve_unmixing_iterative` (processing.py, lines 396–411)

This is the most complex solver. It iteratively:
1. Estimates effective pathlength `l(λ)` from current concentration estimates.
2. Rebuilds the overlap matrix with the updated pathlength.
3. Solves NNLS.
4. Updates concentration estimates.
5. Repeats until convergence.

**Initial condition:** Uniform concentration `c₀ = initial_concentration` (default `1e-4`) for each chromophore.

**Per iteration `t`:**

1. **Estimate effective pathlength** via `estimate_effective_pathlength` (processing.py, lines 463–505):
   ```
   μₐ(λ) = Σₖ max(c̄ₖ, 0) · εₖ(λ)     (mean chromophore absorption)
   μₑff(λ) = √(3 · μₐ(λ) · (μₐ(λ) + μₛ′(λ)))
   l_eff(λ) = 1 / μₑff(λ)
   ```
   Uses fixed scattering parameters (defaults above).

2. **Rebuild overlap matrix** with `lⁿ = ∫ φ̂ₙ(λ) · l_eff(λ) dλ` for the pathlength row.

3. **Solve NNLS:** `_solve_unmixing_nnls(od_cube, A_iter)`.

4. **Damped update:**
   ```
   l_curr ← (1 − damping) · l_curr + damping · l_model
   ```
   Default `damping = 0.5`.

5. **Check convergence:**
   - `‖l_next − l_curr‖ / ‖l_curr‖ < tol_rel` (default `1e-4`)
   - Mean RMSE improvement < `tol_rmse` (default `1e-6`)
   - Max iteration count (default 25)

**Fallback logic:**
- If an error occurs mid-iteration, the best iterate (lowest mean RMSE) so far is returned.
- If even the first iteration fails, falls back to static overlap matrix (built with `l = ones` via `np.ones_like(common_wl)`).
- If the fallback also fails, raises `RuntimeError`.

**Solver info metadata** returned alongside concentrations includes: `method`, `base_method` (always `"nnls"`), `stop_reason`, `fallback_used`, `iterative_error`, `n_iter`, `best_iter`, `best_mean_rmse`, convergence history, final `A_used`, `pathlength_spectrum`, and all scattering/background parameters used.

**Inputs:** Same as overlap-matrix solvers plus iterative control parameters and optional `scattering_parameters` dict.

**Outputs:** `(concentrations, rmse_map, fitted_od, solver_info)`.

---

## 4. Derived Maps

**Function:** `compute_derived_maps` (processing.py, lines 541–561)

```
THb  = [HbO₂] + [Hb]
StO₂ = [HbO₂] / (THb + ε)
```
Only computed when both `"HbO₂"` and `"Hb"` are in `chromophore_names`. Otherwise returns zero-filled maps.

---

## 5. Quality Diagnostics

**Function:** `compute_diagnostics` (processing.py, lines 567–600)

Computes:
- `global_rmse`: mean of RMSE map
- `n_nan_pixels`: count of NaN entries in RMSE map
- `n_negative_reflectance`: count of reflectance < 0
- `condition_number`: `np.linalg.cond(A)`
- `warnings`: list of human-readable warnings (high condition number, NaN pixels, negative reflectance)

---

## 6. Data Flow & Callers

```
app/main.py
  └─ app/gui_qt/main_window.py::SpectralUnmixingMainWindow
       ├─ _make_pipeline_adapter()  [lines 1507–1658]
       │    ├─ app.core.io.load_image_cube()        — loads raw images
       │    ├─ app.core.io.load_chromophore_spectra() — CSV → dict of (wl, coeff)
       │    ├─ app.core.io.load_led_emission()       — CSV → common_wl + dict
       │    ├─ app.core.io.load_penetration_depth()  — CSV → (wl, depth)
       │    ├─ app.core.processing.compute_reflectance()
       │    ├─ app.core.processing.compute_optical_density()
       │    ├─ app.core.processing.build_overlap_matrix()   — for ls/nnls/iterative
       │    ├─ app.core.processing.build_absorption_matrix() — for mu_a
       │    ├─ app.core.processing.build_fixed_scattering_profile() — for mu_a/iterative
       │    ├─ app.core.processing.solve_unmixing()          — for ls/nnls/mu_a
       │    ├─ app.core.processing.solve_unmixing_iterative() — for iterative
       │    ├─ app.core.processing.compute_derived_maps()
       │    └─ app.core.processing.compute_diagnostics()
       ├─ _build_config_snapshot()   [lines 1427–1478]  — captures UI state
       └─ _start_pipeline()          [lines 1366–1397]  — QThread launch
```

---

## 7. Parameter Defaults Summary

| Parameter group | Key | Default | Validated in |
|----------------|-----|---------|--------------|
| **Scattering** | `lambda0_nm` | 500.0 | `validate_scattering_parameters` (l. 40) |
| | `mu_s_500_cm1` | 120.0 | > 0 |
| | `power_b` | 1.0 | (free) |
| | `lipofundin_fraction` | 0.25 | ≥ 0 |
| | `anisotropy_g` | 0.8 | 0 ≤ g < 1 |
| **Background** | `model` | "constant" | `validate_background_parameters` (l. 68) |
| | `value` | 2500.0 | finite |
| | `exp_start` / `exp_end` | 1.0 / 0.1 | > 0 / ≥ 0 |
| | `exp_shape` | 1.0 | > 0 |
| | `exp_offset` | 0.0 | finite |
| | `slope_start` / `slope_end` | 1.0 / 0.1 | finite |
| **Iterative solver** | `max_iter` | 25 | ≥ 1, integer |
| | `tol_rel` | 1e-4 | > 0 |
| | `tol_rmse` | 1e-6 | ≥ 0 |
| | `damping` | 0.5 | 0 < damping ≤ 1 |
| | `initial_concentration` | 1e-4 | ≥ 0 |

---

## 8. Key Constraints & Risks

| Constraint | Where enforced | Notes |
|-----------|---------------|-------|
| Chromophore CSV header mismatch | `io.load_chromophore_spectra` | bilirubin uses `wavelength_nm`; all others use `lambda`. Must have 2 numeric columns. |
| LED CSV ragged rows | `io.load_led_emission` line 184 | Raises `ValueError` if a row has fewer columns than expected from header. |
| Penetration depth non-finite | `processing.build_overlap_matrix` line 299 | Raises `ValueError` if NaN/inf in depth arrays. |
| OD → μₐ singularity | `processing._od_to_mu_a` line 473 | Masks bands where `OD ≥ 1/√3` or `μₛ′ ≤ 0`. These bands are excluded from the NNLS fit. |
| NNLS per-pixel loop | `processing._solve_unmixing_nnls` | O(H·W) Python loop over `scipy.optimize.nnls`. This is the main performance bottleneck. |
| Static overlap fallback | `processing.solve_unmixing_iterative` | If pathlength estimation fails on first iteration, reverts to `l(λ) = 1` (uniform pathlength), which may be physically wrong. |
| Background constant column | processing.py lines 329, 337 | Constant value is directionally identical regardless of scale — the coefficient absorbs scaling. Only zero vs nonzero matters for constant model. |
| 1+ chromophore required | `_make_pipeline_adapter` | Raises error if no chromophores selected and background disabled. For `mu_a`, background is always disabled. |

---

## 9. Files That Likely Need Changes

| File | Reason |
|------|--------|
| `app/core/processing.py` | All solver math, matrix builders, validators — primary change target |
| `app/core/io.py` | Data loading, CSV format handling — if chromophore or LED data format changes |
| `app/gui_qt/main_window.py` | Pipeline adapter, solver wiring, toolbar controls — if solver signature or parameters change |
| `app/core/export.py` | Output format — if result payload structure changes |
| `app/gui_qt/panels/` | Display panels consuming result payload — if keys change |
| `features/background_model_research.md` | Documents the planned background model evolution (constant → basis → scattering) |
| `tests/test_processing_fixed_scattering.py` | Tests for `mu_a` and `iterative` solvers — must update if solver behavior changes |
| `tests/test_background_consistency.py` | End-to-end tests with real data |

---

## 10. Start Here

**`app/core/processing.py`** — This is the single most important file. It contains all four solver implementations, matrix construction, validation logic, derived maps, and diagnostics. Understanding lines 1–680 gives the complete algorithmic picture.

To trace a specific method:
- **`ls` / `nnls`:** Start at `solve_unmixing()` (line 381), follow to `_solve_unmixing_ls` (line 415) or `_solve_unmixing_nnls` (line 437).
- **`mu_a`:** Start at `solve_unmixing()` → `_solve_unmixing_mu_a` (line 500), then `_od_to_mu_a` (line 473).
- **`iterative`:** Start at `solve_unmixing_iterative` (line 396), then `estimate_effective_pathlength` (line 463).
