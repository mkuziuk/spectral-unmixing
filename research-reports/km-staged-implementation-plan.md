# Staged Implementation & Validation Plan: Kubelka-Munk Solver

## Goal

Add a `"km"` solver method to the existing PySide6 spectral unmixing app that uses the Kubelka-Munk remission function with a known Lipofundin scattering prior to recover chromophore concentrations from diffuse reflectance, then validate it against the DNG liquid-phantom dataset using `bili_agat` and `hb_agat_extr` spectra with known ground truth (Hb = 100 µM constant, bilirubin A1 = 270 µM, halving each subsequent phantom).

---

## Background

### Why Kubelka-Munk

The research in `research-reports/blb-alternatives.md` identifies Kubelka-Munk (KM) as the model most directly validated for Hb, HbO₂, and bilirubin extraction from diffuse reflectance in turbid media (Seroul et al. 2016, Doi et al. 2004). The KM two-flux model produces a remission function that, when combined with a known scattering prior, yields a linear relationship between absorption and chromophore concentration — directly compatible with the existing NNLS pixelwise solver.

### KM Model Summary

For a semi-infinite, homogeneous, diffusely illuminated layer the KM remission function is:

```
K/S = (1 − R)² / (2R)
```

where `K` ≈ 2μa (absorption coefficient) and `S` ≈ μs′ (reduced scattering).  
Given a known scattering spectrum `S(λ)`, we recover:

```
μa_KM(λ) = F(R) · S(λ) / 2
```

Chromophore concentrations `c_k` are then solved from the standard linear model:

```
μa_KM(λ) ≈ Σ_k c_k · ε_k(λ)
```

via band-averaging over the LED emission profiles (reusing the existing `build_absorption_matrix` and `build_fixed_scattering_profile` infrastructure).

### Relationship to Existing Solvers

| Solver | Forward model | Scattering | Background | Non-neg |
|--------|--------------|------------|------------|---------|
| `"ls"` | A·x (overlap matrix) | via penetration depth | ✓ | ✗ |
| `"nnls"` | A·x (overlap matrix) | via penetration depth | ✓ | ✓ |
| `"mu_a"` | OD → μa (diffusion inversion) | fixed μs′ prior | ✗ | ✓ |
| `"iterative"` | A·x with updated pathlength | fixed μs′ prior | ✓ | ✓ |
| **`"km"` (new)** | **KM remission → μa** | **fixed μs′ prior** | **✗** | **✓** |

The `"km"` solver is structurally closest to `"mu_a"`: both are two-stage methods (reflectance → absorption → chromophore fit) using the same scattering prior. The difference is the mathematical conversion from reflectance to absorption.

---

## Tasks

### Stage 1 — Core KM Math (app/core/processing.py)

#### 1.1 Add `"km"` to `SUPPORTED_UNMIXING_METHODS`

- **File:** `app/core/processing.py`, line 16
- **Change:** Update the tuple from `("ls", "nnls", "mu_a")` to `("ls", "nnls", "mu_a", "km")`.
- **Acceptance:** `"km" in processing.SUPPORTED_UNMIXING_METHODS` is `True`.

#### 1.2 Implement KM remission function `_reflectance_to_mu_a_km`

- **File:** `app/core/processing.py`, new function near the existing `_od_to_mu_a` (line ~533)
- **Signature:** `_reflectance_to_mu_a_km(reflectance: np.ndarray, S: np.ndarray, eps: float = 1e-10) -> tuple[np.ndarray, np.ndarray]`
- **Logic:**
  ```python
  def _reflectance_to_mu_a_km(reflectance, S, eps=1e-10):
      R_clipped = np.clip(reflectance, eps, 1.0 - eps)
      # KM remission: F(R) = K/S = (1-R)² / (2R)
      F = (1.0 - R_clipped) ** 2 / (2.0 * R_clipped)
      # K ≈ 2μa, S ≈ μs′  →  μa ≈ K/2 = F·S/2
      mu_a = F * np.asarray(S, dtype=float) / 2.0
      valid = np.isfinite(mu_a) & (mu_a >= 0)
      return np.maximum(mu_a, 0.0), valid
  ```
- **Acceptance:** Unit test with known R and S produces expected μa. Verify NaN/inf/negative handling.

#### 1.3 Implement `_solve_unmixing_km` function

- **File:** `app/core/processing.py`, new function after `_solve_unmixing_mu_a` (line ~680)
- **Signature:** `_solve_unmixing_km(od_cube_unused: np.ndarray, A: np.ndarray, reflectance: np.ndarray, mus_prime: np.ndarray) -> tuple`
- **Logic:**
  1. Reshape reflectance and μs′ for pixelwise operation.
  2. For each pixel, call `_reflectance_to_mu_a_km` to convert reflectance → μa.
  3. Solve `A @ x = μa_KM` via `scipy.optimize.nnls` (identical to `mu_a` pattern).
  4. Reconstruct fitted μa and back-convert to reconstructed reflectance for residual (optional, or compute residual in μa-space).
  5. Return `(concentrations, rmse_map, fitted_mu_a_od_or_reflectance)`.
- **Acceptance:** Call from a unit test with synthetic perfectly-KM-consistent data and recover known concentrations.

#### 1.4 Add `"km"` branch to `solve_unmixing` dispatcher

- **File:** `app/core/processing.py`, `solve_unmixing` function (line ~1019)
- **Change:** Add `if method == "km":` branch that calls `_solve_unmixing_km`. The call must also accept `reflectance` and `mus_prime` as parameters.
- **Design decision (needs resolution):** The current `solve_unmixing` signature only takes `(od_cube, A, method, mus_prime)`. The KM solver needs `reflectance`, not `od_cube`. Options:
  - **A.** Extend `solve_unmixing` to accept an optional `reflectance` parameter.
  - **B.** Create a separate top-level function `solve_unmixing_km(reflectance, A, mus_prime)` that bypasses `solve_unmixing`.
  - **C.** Have `solve_unmixing` call `_solve_unmixing_km` passing `od_cube` as both the od and a placeholder, or repurpose `od_cube` to hold reflectance when `method="km"`.

  **Recommendation: Option B** — create a clean `solve_unmixing_km` public function that takes `reflectance` directly. The pipeline adapter in `main_window.py` already has a per-solver-method branch; it is safer and more readable to route the KM path explicitly there rather than contort the generic dispatcher.
- **Acceptance:** Existing solver tests (`test_processing_fixed_scattering.py`) continue to pass. Importing `solve_unmixing_km` works.

### Stage 2 — GUI Integration (app/gui_qt/main_window.py)

#### 2.1 Register `"km"` in the solver combo box

- **File:** `app/gui_qt/main_window.py`, `_build_toolbar` method (line ~383)
- **Change:** `solver_combo.addItems(["ls", "nnls", "mu_a", "iterative", "km"])`
- **Acceptance:** Launch the app, dropdown shows "km" as the 5th entry.

#### 2.2 Configure solver-dependent toolbar visibility for `"km"`

- **File:** `app/gui_qt/main_window.py`, `_uses_fixed_scattering_solver` (line ~1560)
- **Change:** Add `"km"` to the set so that `"km"` shows scattering toolbars and hides the background toolbar (KM does not support background, like `mu_a`).
  ```python
  return solver_method in {"mu_a", "iterative", "km"}
  ```
- **Acceptance:** Selecting "km" in solver dropdown shows scattering toolbar, hides background toolbar and iterative toolbar.

#### 2.3 Handle `"km"` in `_build_config_snapshot`

- **File:** `app/gui_qt/main_window.py`, `_build_config_snapshot` method (line ~1335)
- **Change:** In the scattering-parameters block, extend to include `"km"`:
  ```python
  if use_fixed_scattering:
      # includes mu_a, iterative, AND km
      ...
  ```
  Also ensure `include_background = False` when `solver_method == "km"` (it already is for `mu_a` — just extend the condition).
- **Acceptance:** Clicking "Run" with `"km"` selected and valid scattering params does not raise a config error.

#### 2.4 Handle `"km"` in `_make_pipeline_adapter`

- **File:** `app/gui_qt/main_window.py`, `_make_pipeline_adapter` method (line ~1400)
- **Change:** Add an `elif snapshot["solver_method"] == "km":` branch in the matrix-building section that:
  1. Builds the absorption matrix `A` via `processing.build_absorption_matrix(...)` (same as `mu_a`).
  2. Builds `mus_prime` via `processing.build_fixed_scattering_profile(...)` (same as `mu_a`).
  
  Then in the per-sample loop, add a branch:
  ```python
  elif snapshot["solver_method"] == "km":
      concentrations, rmse_map, fitted_od = processing.solve_unmixing_km(
          reflectance,   # reflectance cube, not OD
          A,
          mus_prime,
      )
      # For RMSE computation: use fitted reflectance reconstructed from fitted μa
      # or compute RMSE in μa-space.  Use fitted_od as placeholder for reconstructed reflectance.
  ```
- **Design note:** `solve_unmixing_km` returns `(concentrations, rmse_map, fitted_reflectance_or_placeholder)`. The diagnostics and panel code expect `fitted_od` in the result dict. We can store the reconstructed reflectance as `fitted_od` or add a new key. For backward compatibility, store the reconstructed reflectance in `fitted_od`, since the pixel inspector will plot it against the measured reflectance.
- **Acceptance:** Full GUI pipeline runs for DNG phantoms with `"km"` selected, no crash.

#### 2.5 Update `_set_solver_dependent_controls` for `"km"`

- **File:** `app/gui_qt/main_window.py`, `_set_solver_dependent_controls` (line ~1640)
- **Change:** `use_background_controls = solver_method != "mu_a"` → `use_background_controls = solver_method not in {"mu_a", "km"}`.
- **Acceptance:** Background toolbar hidden for "km" solver.

### Stage 3 — Core Unit Tests

#### 3.1 Unit test: `_reflectance_to_mu_a_km` correctness

- **File:** `tests/test_processing_fixed_scattering.py` (or new `tests/test_kubelka_munk.py`)
- **Test cases:**
  1. **Known R, known S → correct μa:** For R=0.5, S=10, expect F=(0.5)²/(2·0.5)=0.25/1.0=0.25, μa=0.25·10/2=1.25.
  2. **R close to 0:** R=eps → F large but finite, μa finite.
  3. **R close to 1:** R=1-eps → F≈eps, μa≈0.
  4. **Negative R:** Clipped to eps.
  5. **S array shape matches reflectance bands.**
- **Acceptance:** All test cases pass.

#### 3.2 Unit test: `solve_unmixing_km` recovers known concentrations

- **File:** `tests/test_kubelka_munk.py`
- **Test:** Synthetic data test similar to `test_mu_a_solver_recovers_known_concentrations` but using the KM forward model:
  1. Choose known concentrations `c_true`.
  2. Compute `μa_true = E @ c_true`.
  3. Choose `S` (μs′ spectrum) and compute `R = 1 + (μa/S) - sqrt((μa/S)² + 2·μa/S)` (inverse KM).
  4. Call `solve_unmixing_km(R, E, S)`.
  5. Assert `c_recovered ≈ c_true`.
- **Acceptance:** Concentrations recovered within 1e-8 tolerance.

#### 3.3 Unit test: `solve_unmixing_km` enforces non-negativity

- **File:** `tests/test_kubelka_munk.py`
- **Test:** Generate reflectance from μa where one chromophore has zero true concentration. Verify recovered concentration ≥ 0.
- **Acceptance:** Non-negative concentrations enforced.

#### 3.4 Unit test: `solve_unmixing_km` requires scattering profile

- **File:** `tests/test_kubelka_munk.py`
- **Test:** Call `solve_unmixing_km` with `mus_prime=None`, expect `ValueError`.
- **Acceptance:** Clear error message.

### Stage 4 — Integration / Ground-Truth Validation Test

#### 4.1 Create validation test script

- **File:** `tests/test_km_phantom_validation.py`
- **Purpose:** End-to-end validation using the DNG liquid phantom dataset and `bili_agat` + `hb_agat_extr` spectra.
- **Setup (one-time per test session):**
  1. Load DNG sample folder: `liquid_phantoms_for_unmixing_dng_cropped/`
  2. Detect folders → 6 samples (A1–A6) + ref + dark_ref.
  3. Load `ref` and `dark_ref` cubes.
  4. Load chromophore spectra from `data/chromophores/`, selecting only `bili_agat` and `hb_agat_extr`.
  5. Load LED emission data.
  6. Build absorption matrix `E` (2 columns: bili_agat, hb_agat_extr; 8 LED bands).
  7. Build fixed scattering profile `mus_prime` using default parameters.
- **Per-sample processing (A1–A6):**
  1. Load sample image cube.
  2. Compute `reflectance` via `processing.compute_reflectance(sample, ref_cube, dark_cube)`.
  3. Call `processing.solve_unmixing_km(reflectance, E, mus_prime)`.
  4. Extract per-pixel concentration maps for bili_agat and hb_agat_extr.
  5. Compute spatial-mean concentration per chromophore per phantom (excluding NaN/inf pixels).
- **Validation assertions:**
  1. **Hb constancy:** The 6 mean Hb concentrations should all be close to 100 µM. Define acceptance: the coefficient of variation (std/mean) across A1–A6 ≤ 30%, AND the absolute deviation of each mean from 100 µM ≤ 50 µM.
  2. **Bilirubin halving:** Let `B_i` be the mean bilirubin concentration for phantom A_i. Verify:
     - `B_1 ≥ B_2 ≥ B_3 ≥ B_4 ≥ B_5 ≥ B_6` (monotonically decreasing)
     - `B_1 ≈ 270 µM` (within factor 2: 135–540 µM)
     - `B_i / B_{i+1} ≈ 2.0` for i=1..5 (each ratio within [1.3, 3.0])
  3. **RMSE sanity:** Per-sample mean RMSE ≤ 0.2 (OD units equivalent), no NaN pixels.
  4. **Condition number:** Absorption matrix condition number < 200 for numerical stability.
- **Output:** Log the mean, median, std for each chromophore per phantom in a structured format printed to stdout, for manual inspection. Print a summary PASS/FAIL per criteria.
- **Acceptance:** Test passes (or documents specific quantifiable deviations with explanations).

#### 4.2 Determine whether `hb_agat_extr` vs `hb_agat` affects results

- **File:** `tests/test_km_phantom_validation.py`
- **Add a parameterised sub-test:** Run the same validation using `hb_agat` (the non-extr version) and compare mean Hb values. Document whether the `extr` variant gives better Hb constancy.
- **Acceptance:** Output printed; no assertion required (informational comparison).

### Stage 5 — Documentation & Edge Cases

#### 5.1 Update README with KM solver description

- **File:** `README.md`
- **Change:** In the "The Math and Physics Model" section, add a subsection for the Kubelka-Munk solver, including the remission function formula, relationship to existing solvers, and the physical assumptions (diffuse illumination, semi-infinite medium, known scattering prior).
- **Acceptance:** README accurately describes the new solver.

#### 5.2 Ensure `export.py` works with KM results

- **File:** `app/core/export.py`
- **Check:** The `save_results` function expects keys like `concentrations`, `rmse_map`, `derived`, `diagnostics` — all of which the KM pipeline adapter produces. The `fitted_od` key may hold reconstructed reflectance instead of OD for KM. Ensure the export doesn't break when `fitted_od` data ranges differ (export uses it only for the metrics; the fitted_od array is not directly exported as a map unless explicitly requested, which it currently isn't).
- **Acceptance:** Save button works after a KM run; maps folder populated with PNGs; no crash.

#### 5.3 Pixel Inspector compatibility

- **File:** `app/gui_qt/panels/inspector_panel.py`
- **Check:** The inspector shows `measured OD spectrum` vs `fitted OD spectrum`. For KM, the "OD" is actually reflectance. Either:
  - Document that the inspector shows reflectance spectra when KM is active, OR
  - Compute OD from KM reflectance and store both in results so the inspector works normally.
  
  **Recommendation:** For the initial implementation, accept that the inspector shows reflectance spectra for KM. This is documented behaviour. A follow-up could add a dual-display mode.
- **Acceptance:** Inspector panel does not crash when displaying KM results.

#### 5.4 Diagnostics panel compatibility

- **File:** `app/gui_qt/panels/diagnostics_panel.py` and `app/core/processing.py::compute_diagnostics`
- **Check:** The `compute_diagnostics` function receives `reflectance`, `od_cube`, `rmse_map`, and `A`. For KM, `od_cube` would be the reflectance cube instead. The diagnostics check for negative reflectance will always report 0 (because we pass reflectance as both args). This is acceptable — adjust the call in the KM pipeline adapter to pass `reflectance` for both `reflectance` and `od_cube` args.
- **Acceptance:** Diagnostics tab shows reasonable numbers, no NaN in condition number.

---

## Files to Modify

| File | Stage | Changes |
|------|-------|---------|
| `app/core/processing.py` | 1, 3 | Add `"km"` to `SUPPORTED_UNMIXING_METHODS`; add `_reflectance_to_mu_a_km`; add `_solve_unmixing_km` (or `solve_unmixing_km` public); add `"km"` to `solve_unmixing` dispatcher |
| `app/gui_qt/main_window.py` | 2 | Add `"km"` to solver_combo; extend `_uses_fixed_scattering_solver`; extend `_set_solver_dependent_controls`; extend `_build_config_snapshot`; add KM branch in `_make_pipeline_adapter` |
| `README.md` | 5 | Document KM solver and physical assumptions |
| `tests/test_kubelka_munk.py` | 3 | New unit tests for `_reflectance_to_mu_a_km` and `_solve_unmixing_km` |
| `tests/test_km_phantom_validation.py` | 4 | New integration test for ground-truth validation on DNG phantoms |

## New Files

| File | Purpose |
|------|---------|
| `tests/test_kubelka_munk.py` | Unit tests for core KM math |
| `tests/test_km_phantom_validation.py` | End-to-end validation against ground truth |

---

## Dependencies

```
Stage 1 (Core math) ──────────────► Stage 2 (GUI) ──► Stage 5 (Docs)
         │
         └──► Stage 3 (Unit tests)
                    │
                    └──► Stage 4 (Validation test)
```

- Stage 2 depends on Stage 1 (the GUI needs the new functions to exist).
- Stage 3 depends on Stage 1 (the tests import the new functions).
- Stage 4 depends on Stage 1 and 3 (validation test imports the same functions).
- Stage 5 can proceed in parallel with Stages 3–4 after Stage 2 is done.

---

## Risks

### Mathematical Risks

1. **KM validity for LEDs:** The Kubelka-Munk model assumes diffuse illumination. The LED-based imaging system may have partially collimated illumination. A Saunderson correction (Fresnel reflection at the air-medium interface) may be needed. **Mitigation:** Test with/without correction; document limitations.

2. **Semi-infinite assumption:** KM for `R∞` is valid when the sample is optically thick. If the cuvette bottom reflects, the model is wrong. **Mitigation:** Check if reflectance is consistent across phantoms; flag if RMSE is systematically high.

3. **Band-averaging:** The KM remission function `F(R) = (1-R)²/(2R)` is nonlinear in R, so band-averaging `F(R)` is not the same as `F(average R)`. **Mitigation:** Apply the KM transform before LED-band integration (i.e., at the full wavelength level after re-interpolating reflectance to the common wavelength grid). This is more physically correct. However, since we only have 8 band measurements (not a full spectrum), we must work at band level. Accept this as a limitation.

4. **K/S vs μa/μs′ relationship:** The conversion `K ≈ 2μa, S ≈ μs′` is an empirical mapping valid in the diffuse regime. Lipofundin phantoms at 450 nm may have μa comparable to μs′, breaking this mapping. **Mitigation:** Accept this as a first-order model; validate via ground truth.

### Codebase Risks

5. **`solve_unmixing` signature:** Adding `reflectance` as a parameter changes a stable public API. **Mitigation:** Use Option B (separate `solve_unmixing_km` function) to avoid signature changes.

6. **Pipeline adapter complexity:** The `_make_pipeline_adapter` is already a long method with per-solver branches. Adding KM adds another. **Mitigation:** Keep the KM branch minimal and follow the existing pattern exactly.

7. **Missing `rawpy` dependency:** The DNG phantoms require `rawpy` to load. Tests must handle `ImportError` gracefully if `rawpy` is not installed. **Mitigation:** Skip DNG validation tests with a clear message if `rawpy` is unavailable.

### Ground-Truth Risks

8. **Concentration units:** The ground truth states Hb = 100 µM and bilirubin A1 = 270 µM. The recovered concentrations from NNLS will be in the same units as the extinction coefficient spectra. If the extinction spectra are in `cm⁻¹/M`, the recovered concentrations are in `M`. We must verify that the `hb_agat_extr` and `bili_agat` extinction coefficients are in compatible units. **Mitigation:** Check CSV files; they list `extinction_coefficient` without explicit units, but the scale (Hb ~ 10⁵ at Soret peak) is consistent with `cm⁻¹/M`. If recovered values differ from ground truth by a constant factor, it's a unit calibration issue, not a model failure. Report both raw and scaled concentrations.

9. **Unknown phantom scattering:** The Lipofundin concentration in the phantoms may differ from the default scattering parameters (μs_500 = 120 cm⁻¹, f_lipo = 0.25). The KM solver is sensitive to the scattering prior. **Mitigation:** Test with a range of scattering parameters; report sensitivity.

10. **Spectral cross-talk:** bili_agat and hb_agat_extr have overlapping absorption features below 500 nm. With only 2 LED bands in this region (450, 517 nm), the solver may misattribute signal between the two chromophores. **Mitigation:** The monotonicity and halving ratio checks are soft (intervals given in Stage 4.1). This test measures whether the method is directionally useful, not whether it's quantitatively perfect.

---

## Acceptance Criteria (Summary)

| Criterion | Verification |
|-----------|-------------|
| KM solver listed in GUI | Dropdown shows "km" |
| Scattering toolbar visible, background hidden for KM | Manual check or smoke test |
| Unit tests pass for `_reflectance_to_mu_a_km` | `pytest tests/test_kubelka_munk.py -q` |
| Unit tests pass for `solve_unmixing_km` with synthetic data | Same test file |
| Existing solver tests still pass | `pytest tests/test_processing_fixed_scattering.py -q` |
| Full GUI pipeline runs without crash | Manual run or GUI smoke test |
| Ground truth: Hb constancy CV ≤ 30% across A1–A6 | `pytest tests/test_km_phantom_validation.py -q` |
| Ground truth: Bilirubin monotonic decreasing | Same test |
| Ground truth: Bilirubin halving ratio ~2.0 (±50%) | Same test |
| Export works after KM run | Manual check or integration test |
| No regressions in LS/NNLS/mu_a/iterative | Full test suite |

---

## Migration / Rollback

- The change is **purely additive**: no existing functions are modified except the `SUPPORTED_UNMIXING_METHODS` tuple and the solver combo items list.
- Rolling back: revert the tuple change and the combo items, remove the new functions and test files. Existing solvers are untouched.
- The new `"km"` method is the **5th entry** in the solver combo, so it does not shift existing indices.
