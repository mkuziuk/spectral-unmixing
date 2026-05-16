# Two-Band Bilirubin Index — Implementation-Ready Plan

**Date:** 2026-05-16  
**Context:** The DNG A1–A6 phantom series has Hb = 100 µM constant, bilirubin halving from 270 → 8.4 µM.  
The existing KM solver (`solve_unmixing_km`, `feature/kubelka-munk-solver` branch) performs full 2-chromophore NNLS across 8 bands but suffers spectral overlap in the 2 blue/green bands. A simpler, model-free ratiometric index is needed as an orthogonal diagnostic — faster to compute, easier to calibrate, and defensible as a "bilirubin index" rather than an absolute bilirubin concentration.

---

## 1. Goal

Produce a **per-pixel bilirubin index map** using only two LED-band reflectance values, calibrated against the known A1–A6 halving series, with an Hb-correction term derived from a bilirubin-free reference band. Expose the index as an additional derived map in the GUI panels, with a companion calibration report that does not overclaim absolute unmixing accuracy.

---

## 2. Index Candidates — Data-Driven Selection

### 2.1 Reflectance at 450 nm and 517 nm (raw values)

Measured median reflectance across the 50×50 px DNG-derived images (after `compute_reflectance` with ref/dark correction):

| Sample | [Bili] µM | R450 | R517 | R671 |
|--------|----------:|-----:|-----:|-----:|
| A1     | 270.0    | 0.336 | 0.366 | 0.574 |
| A2     | 135.0    | 0.360 | 0.385 | 0.592 |
| A3     | 67.5     | 0.371 | 0.392 | 0.596 |
| A4     | 33.75    | 0.377 | 0.394 | 0.604 |
| A5     | 16.88    | 0.376 | 0.391 | 0.603 |
| A6     | 8.44     | 0.378 | 0.392 | 0.605 |

### 2.2 Candidate Formulas

For each pixel, the following candidate indices were computed:

| Index Name | Formula | Dynamic Range (A1→A6) | Pearson r vs log₁₀([Bili]) |
|------------|---------|----------------------:|--------------------------:|
| `R517/R450` | R(517) / R(450) | 1.088 → 1.035 (4.9%) | 0.969 |
| `OD₄₅₀ − OD₅₁₇` | −log₁₀ R₄₅₀ + log₁₀ R₅₁₇ | 0.0365 → 0.0148 (2.5×) | 0.971 |
| `F₄₅₀/F₅₁₇` | KM remission ratio | 1.191 → 1.079 (9.4%) | **0.980** |
| `R450` alone | R(450) | 0.336 → 0.378 (12.5%) | −0.867 |

### 2.3 Recommendation

**Primary index: `OD₄₅₀ − OD₅₁₇`** (optical-density difference).

Rationale:
1. **Good log-linear correlation** (r = 0.971) with known [Bili].
2. **Largest dynamic range in ratio terms** — 2.5× change from A1→A6, compared to ~5–10% for direct reflectance ratios. This gives it the most resolving power at low bilirubin.
3. **Physically interpretable**: OD difference approximates Δμₐ·Lₑff, directly proportional to bilirubin's differential absorption between the two bands.
4. **Simple to compute** — uses `compute_optical_density` which already exists; no KM transform needed.
5. **Avoids the KM F(R) amplification** of near-zero reflectance noise (R450 drops to ~0.34 at A1, F(R) amplifies measurement noise).

**Secondary/validation index: `F₄₅₀/F₅₁₇`** (KM remission ratio) — has slightly better correlation (r = 0.980) and is worth computing as a cross-check, but adds complexity with no strong gain over the OD difference.

### 2.4 Extinction-Coefficient Sanity Check

From `bili_agat.csv` and `hb_agat_extr.csv` at the two key wavelengths:

| Wavelength | ε_bili (cm⁻¹/M) | ε_hb (cm⁻¹/M) | ε_bili/ε_hb |
|------------|-----------------:|--------------:|-----------:|
| 450 nm     | 44,318           | 40,882        | 1.08      |
| 517 nm     | 8,459            | 25,801        | 0.33      |

The bilirubin differential extinction Δε = ε_bili(450) − ε_bili(517) = 35,859 cm⁻¹/M.  
The hemoglobin differential extinction Δε = ε_hb(450) − ε_hb(517) = 15,081 cm⁻¹/M.

At A1 (270 µM bilirubin, 100 µM Hb): bilirubin contributes 270·35859 ≈ 9.68×10⁶, Hb contributes 100·15081 ≈ 1.51×10⁶ — bilirubin is 6.4× the Hb signal.  
At A6 (8.44 µM bilirubin, 100 µM Hb): bilirubin contributes 8.44·35859 ≈ 3.03×10⁵, Hb contributes 1.51×10⁶ — Hb is 5.0× the bilirubin signal.

The OD difference crosses below the Hb-background around 42 µM bilirubin, which is between A3 (67.5 µM) and A4 (33.75 µM). This matches the observed flattening of the index at lower concentrations.

---

## 3. Calibration Against the A1–A6 Halving Series

### 3.1 Calibration Model

Fit a power-law or exponential curve:

```
[Bili]_index = A · (OD₄₅₀ − OD₅₁₇)^γ
```

or alternatively calibrate as a dimensionless index:

```
BI = k · (OD₄₅₀ − OD₅₁₇ − Hb_baseline) / Hb_baseline
```

where `Hb_baseline` is the expected OD difference from 100 µM Hb alone.

### 3.2 Calibration Procedure

1. **Extract per-pixel OD difference maps** for all 6 samples:
   ```
   OD_diff_map = OD[:,:,0] − OD[:,:,1]
   ```

2. **Compute sample-level statistics** (median, IQR) for each sample's `OD_diff_map`.

3. **Fit calibration curve** using the 6 median values:
   - Independent variable: `log₁₀([Bili]_true)` ∈ [0.926, 2.431]
   - Dependent variable: `OD_diff_median` ∈ [0.0148, 0.0365]
   - Fit model: `OD_diff = α · log₁₀([Bili]) + β` (log-linear, given the near-log-linear correlation)
   
   Expected coefficients from the data:
   ```
   α ≈ 0.0145   (slope per decade of [Bili])
   β ≈ 0.0015   (intercept, near-zero because Hb background subtracts)
   ```

4. **Invert for prediction**: `log₁₀([Bili]_predicted) = (OD_diff − β) / α`

5. **Report residuals**: RMSE in log₁₀ space and in linear µM.

### 3.3 Calibration Validation

- **Monotonicity**: OD_diff_mean(A1) > OD_diff_mean(A2) > … > OD_diff_mean(A6).  
  **Status from data: ✓ PASS** — values are strictly decreasing.

- **Approximate halving tracking**: For a true halving series, OD_diff ideally follows:
  ```
  OD_diff(Ai) − OD_diff(A(i+1)) ≈ constant = α · log₁₀(2) ≈ 0.0044
  ```
  Observed differences: 0.0081, 0.0039, 0.0057, 0.0017, 0.0022 — the average is ~0.0043, consistent but with noise at low concentrations.

- **Cross-validation**: Leave-one-out across the 6 samples. At 6 points this is crude but useful to detect overfitting.

---

## 4. Hb-Constant Correction

### 4.1 The Problem

In the A1–A6 series, Hb is constant at 100 µM. But in a real diagnostic scenario, Hb varies between samples (or between pixels within a sample). The OD difference at 450–517 nm has an Hb contribution of ~0.015 per 100 µM Hb (estimated from extinction coefficients), which is comparable to the entire bilirubin signal at low bilirubin levels. A correction is needed.

### 4.2 Hb Proxy Band Selection

A bilirubin-free reference band must meet two criteria:
1. **Negligible bilirubin absorption** — ε_bili ≈ 0.
2. **Non-negligible hemoglobin absorption** — ε_hb > 0 so it carries Hb information.

Candidates from the 8-band set:

| Band | ε_bili | ε_hb | Suitability |
|------|-------:|-----:|-------------|
| 671 nm | ~297 | 1,086 | Good — modest Hb signal, zero bili |
| 775 nm | ~297 | 866 | Good — similar to 671 nm |
| 803 nm | ~297 | 1,107 | Good |
| 851 nm | ~297 | 1,525 | OK — higher Hb but also more water |
| 888 nm | ~297 | 1,789 | Borderline — water absorption rising |
| 939 nm | ~297 | 1,993 | Borderline — water absorption significant |

**Recommendation: 671 nm** — earliest band with zero bilirubin contribution, Hb extinction ~1,086 cm⁻¹/M, water absorption negligible.

### 4.3 Correction Formula

The OD difference can be decomposed:

```
OD₄₅₀ − OD₅₁₇ = Lₑff · [C_bili · Δε_bili + C_hb · Δε_hb + (scattering-cross-term)]
```

where Δε_bili = ε_bili(450) − ε_bili(517) ≈ 35,859 cm⁻¹/M, Δε_hb = ε_hb(450) − ε_hb(517) ≈ 15,081 cm⁻¹/M.

Using the 671 nm reference:
```
OD₆₇₁ ≈ Lₑff · [C_hb · ε_hb(671)]   (C_bili term ≈ 0)
```

The Hb-corrected bilirubin index is:

```
BI_corrected = OD₄₅₀ − OD₅₁₇ − k · OD₆₇₁
```

where `k = Δε_hb / ε_hb(671)` is the expected ratio of Hb-related OD difference at 450–517 to OD at 671 nm.

From the Agati extinction data:
```
k_theoretical = 15,081 / 1,086 ≈ 13.89
```

But the effective pathlength Lₑff may differ between the blue and NIR bands, so `k` should be calibrated from the data — or at least bounded. For the A1–A6 series with constant Hb, `k` can be validated: after correction, all samples should show the same residual from Hb (ideally near zero), leaving only bilirubin variation.

### 4.4 Correction Validation

1. **Constant-Hb check**: With Hb = 100 µM constant across A1–A6, the corrected index should show a consistent bilirubin trend but not lose the halving pattern (i.e., `k` should not be so large that it removes the bilirubin signal).
2. **k calibration**: Compute `k_empirical = (OD₄₅₀ − OD₅₁₇ at sample with zero bilirubin) / (OD₆₇₁ at same sample)`. Since no zero-bilirubin sample exists, extrapolate from the regression of OD_diff vs. log₁₀([Bili]) to find the intercept β (the "Hb-only" OD difference). Then `k = β / median(OD₆₇₁ across A1–A6)`.

   From the data: β ≈ 0.004, OD₆₇₁_median ≈ 0.24, so k_empirical ≈ 0.017. This is much smaller than the theoretical 13.89, indicating that the effective pathlength at 671 nm is ~800× larger than the differential pathlength at 450–517 nm. This is physically expected — light penetrates much deeper at NIR wavelengths where absorption is lower.

   **This is a critical finding**: the effective pathlength ratio between blue and NIR bands is extreme (~800×), so `k` must be calibrated empirically, not from extinction ratios.

---

## 5. Implementation Design

### 5.1 Core Computation (`app/core/processing.py`)

Add a new function `compute_bilirubin_index`:

```python
def compute_bilirubin_index(
    reflectance: np.ndarray,  # (H, W, N_bands)
    wavelength_index_450: int = 0,
    wavelength_index_517: int = 1,
    wavelength_index_ref: int = 2,  # 671 nm
    k_hb_correction: float | None = None,  # None = no Hb correction
    eps: float = 1e-10,
) -> dict:
    """
    Compute a two-band bilirubin index from diffuse reflectance.
    
    Returns dict with:
        'bi_raw': (H,W) — OD₄₅₀ − OD₅₁₇ (uncorrected)
        'bi_corrected': (H,W) — Hb-corrected index (if k_hb_correction is not None)
        'od_ref': (H,W) — OD at the reference band (e.g., 671 nm)
        'wavelengths_used': list — the wavelengths involved
        'k_hb_correction': float — correction factor used
    """
```

### 5.2 Calibration Function

Add `calibrate_bilirubin_index`:

```python
def calibrate_bilirubin_index(
    bi_raw_values: np.ndarray,   # (N_samples,) median OD_diff per sample
    bili_true_uM: np.ndarray,    # (N_samples,) known [Bili] in µM
) -> dict:
    """
    Fit OD_diff = α·log₁₀([Bili]_true) + β.
    
    Returns dict with:
        'alpha': slope
        'beta': intercept (Hb baseline)
        'r_squared': fit quality
        'rmse_log10': RMSE in log₁₀ space
        'predicted_uM': fitted [Bili] at each calibration point
        'residuals_uM': residual errors in µM
    """
```

### 5.3 Pipeline Integration (`app/gui_qt/main_window.py`)

Two approaches are possible. **Approach B (below) is recommended** — it does not require a solver to be selected, and can be computed alongside any existing solver.

#### Approach A: As a new solver method

Add `"bi"` (bilirubin index) to the solver combo. Selecting it would compute the bilirubin index only (no full unmixing). This requires:
- A new pipeline branch that builds no absorption matrix
- Derived maps containing the bilirubin index
- `concentrations` placeholder (zeros or empty)
- Background/scattering controls hidden

**Con: bloats the solver dropdown; bilirubin index is an adjunct, not a solver.**

#### Approach B (RECOMMENDED): As an optional derived map piggybacking on any solver

Add a checkbox or toggle in the toolbar: `☑ Compute bilirubin index`. When checked, after any solver run (ls, nnls, mu_a, km, iterative), the pipeline additionally computes the bilirubin index and adds it to `derived`/`derived_maps`. This way:
- The bilirubin index appears in the Maps panel alongside THb/StO2
- It's exported alongside other derived maps
- It's clearly annotated as "Bilirubin Index (2-band)" not "Bilirubin Concentration"
- It adds value with minimal code

#### Implementation (Approach B):

1. **In `_build_config_snapshot`**: capture a `compute_bilirubin_index: bool` flag.
2. **In `_make_pipeline_adapter`**: after the per-sample solver run (in the `results[sample_name]` block), if `compute_bilirubin_index` is True:
   ```python
   bi_result = processing.compute_bilirubin_index(
       reflectance,
       k_hb_correction=bilirubin_index_params.get("k_hb_correction"),
   )
   derived["Bilirubin Index"] = bi_result["bi_corrected"]
   derived["Bili Idx (raw)"] = bi_result["bi_raw"]
   ```
3. **In `_compute_global_scales`**: extend the derived-scales loop to include `"Bilirubin Index"` (currently hardcoded to `["THb", "StO2"]`).

### 5.4 Calibration Report Script

Add `scripts/calibrate_bilirubin_index.py` that:
1. Loads A1–A6 DNG data
2. Computes per-sample median OD_diff
3. Fits the calibration curve
4. Prints a formatted report with:
   - Calibration coefficients (α, β)
   - r² and RMSE
   - Table of predicted vs. actual [Bili]
   - Halving ratio check
   - k_empirical estimate for Hb correction
5. Outputs a JSON file to `research-reports/bilirubin_index_calibration.json`

### 5.5 Tests

#### Unit Tests (`tests/test_bilirubin_index.py`)

```python
class TestBilirubinIndex(unittest.TestCase):
    def test_od_diff_increases_with_bilirubin(self):
        """Synthetic: higher bili → higher OD₄₅₀−OD₅₁₇"""
    
    def test_hb_correction_reduces_constant_hb_baseline(self):
        """Synthetic: constant Hb, varying bili → raw index shows Hb offset,
           corrected index removes it"""
    
    def test_k_correction_is_positive_and_finite(self):
        """The correction factor must be non-negative"""
    
    def test_calibration_fit_recovers_log_linear_slope(self):
        """Synthetic log-linear data → calibration recovers α, β within tolerance"""
    
    def test_zero_bilirubin_gives_near_zero_corrected_index(self):
        """Synthetic zero-bilirubin, Hb-only sample → corrected index ≈ 0"""
```

#### Integration Test (`tests/test_km_phantom_validation.py` — extend)

Add to the existing phantom validation test:
```python
def test_bilirubin_index_tracks_halving_series(self):
    """OD_diff median strictly decreasing A1→A6;
       halving ratios (adjacent OD_diff ratios) cluster near log₁₀(2)/α"""
```

---

## 6. Exposure as Diagnostic Report / Derived Map

### 6.1 GUI Maps Panel

The bilirubin index appears as a derived map alongside THb and StO2. Key display choices:

- **Colormap**: `plasma` or `inferno` (perceptually uniform, colorblind-friendly).
- **Title**: `"Bilirubin Index (OD₄₅₀−OD₅₁₇)"` — makes the formula explicit.
- **Colorbar label**: Dimensionless or "arb. units" — not "µM".
- **Tooltip**: When hovering, the Pixel Inspector shows the raw OD difference value (not a converted µM).

### 6.2 Calibration Overlay

If the calibration coefficients (α, β) are provided in `solver_info`, the pixel inspector can show:
```
Measured OD_diff: 0.0245
Estimated [Bili]: ~68 µM (± calibration uncertainty)
```

This conversion should be:
- In a separate line, labeled "approx. [Bili] (from calibration)".
- Annotated with "⚠ Calibrated on A1–A6 phantom series; Hb = 100 µM assumed."

### 6.3 Export

The `save_results` export function in `app/core/export.py` already handles all keys in the `derived` dict. The bilirubin index map is saved as:
- `maps/Bilirubin Index (OD450-OD517).png`
- `arrays/Bilirubin Index (OD450-OD517).npy`

No changes needed in the export module.

### 6.4 Calibration Report (Standalone Document)

A markdown report saved to `research-reports/bilirubin-index-validation.md` containing:
1. The calibration curve (α, β, r²).
2. Table: sample, true [Bili], predicted [Bili], residual, % error.
3. The halving ratio table.
4. Hb correction factor k and its empirical derivation.
5. Limitation statements: "This index is calibrated on liquid phantoms with constant Hb and may not transfer to variable-Hb or in-vivo measurements. It indicates bilirubin trends, not absolute concentration."
6. Comparison with the full KM solver results (from `test_km_phantom_validation.py`), showing which approach gives more reliable trends.

---

## 7. Non-Overclaiming Guardrails

### 7.1 What This Index IS

- A **dimensionless scalar** proportional to bilirubin concentration when Hb is fixed.
- A **trend indicator** — monotonic with bilirubin in the A1–A6 series.
- A **complement to the full KM solver** — if both agree on bilirubin trends, confidence increases.
- **Calibratable** against a known standard series.

### 7.2 What This Index IS NOT

- **Not an absolute bilirubin concentration** — it depends on Hb level, scattering, and tissue geometry.
- **Not a replacement for spectral unmixing** — it uses only 2 of 8 bands.
- **Not validated for variable Hb** — the Hb correction is empirical and approximate.
- **Not validated for in-vivo use** — phantom scattering may differ from tissue.

### 7.3 Language for GUI/Reports

In the UI, always refer to it as "Bilirubin Index" or "Bili Index (OD450−OD517)" — never "Bilirubin Concentration" or "[Bili] µM". If an approximate µM conversion is shown, prefix with "est." and annotate with the calibration source.

In exports, include a `bilirubin_index_readme.md` or metadata entry that states:

> The Bilirubin Index is a dimensionless ratiometric indicator computed as OD₄₅₀ − OD₅₁₇ from diffuse reflectance. It was calibrated against a liquid phantom halving series (Hb = 100 µM, [Bili] = 8.4–270 µM). The index correlates with bilirubin concentration (r = 0.97, log-linear fit) but should not be interpreted as an absolute concentration measurement. Hb variation between samples will affect the index; an approximate Hb correction using the 671 nm reference band is applied but has not been independently validated.

---

## 8. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| OD_diff dynamic range too small for per-pixel resolution | Medium | High — noise dominates at low [Bili] | Use spatial binning (2×2 or 3×3) to reduce noise; report SNR per sample |
| Hb correction factor `k` is unstable because effective pathlength differs between blue and NIR | High | Medium — corrected index could amplify noise | Calibrate k empirically from A1–A6; clamp k to [0, 0.1]; make correction optional |
| Users interpret the index as absolute [Bili] | High | Medium — clinical misinterpretation risk | Strong UI labeling; "arb. units" colorbar; calibration caveats in every report |
| R671 varies across A1–A6 (0.574 → 0.605) despite constant Hb — suggests scattering or camera drift | Medium | Low — the Hb correction uses R671 as a proxy, and its variation is modest | Use R775 or R803 as fallback reference bands; test sensitivity to reference band choice |
| Bilirubin absorption tail at 517 nm (ε = 8,459) means R517 is not a pure Hb reference | Low | Low — acceptable because the OD difference subtracts the 517 nm bilirubin contribution | The OD difference still isolates bilirubin because Δε_bili >> Δε_hb; just don't call 517 nm "Hb-only" |
| Camera or illumination non-linearity at low reflectance (R450 drops to 0.34) | Low | Medium — could compress the index dynamic range | Check linearity of the camera response; if needed, apply a gamma correction before OD computation |

---

## 9. Implementation Sequence

### Phase 1 — Core computation (1 file, ~60 lines)
- `app/core/processing.py`: add `compute_bilirubin_index()` and `calibrate_bilirubin_index()`.
- `tests/test_bilirubin_index.py`: 5 unit tests.
- Target: ~2 hours.

### Phase 2 — Calibration script (~80 lines)
- `scripts/calibrate_bilirubin_index.py`: load A1–A6, compute calibration, print report.
- Output: `research-reports/bilirubin-index-calibration.json` and console table.
- Target: ~1 hour.

### Phase 3 — GUI integration (~40 lines in main_window.py)
- Checkbox in toolbar for "Compute Bilirubin Index".
- Pipeline adapter: compute index and add to derived maps.
- `_compute_global_scales`: add "Bilirubin Index" to derived scale computation.
- Target: ~2 hours.

### Phase 4 — Validation report (~200 lines markdown)
- `research-reports/bilirubin-index-validation.md`: full calibration table, comparison with KM solver, caveats.
- Target: ~1 hour.

### Phase 5 — Integration testing
- Extend `tests/test_km_phantom_validation.py` with bilirubin index assertions.
- GUI smoke test: run any solver with checkbox → verify bilirubin index map appears.
- Target: ~1 hour.

**Total estimated effort: ~7 hours.**

---

## 10. Key Files Reference

| File | What to Change |
|------|---------------|
| `app/core/processing.py` | Add `compute_bilirubin_index()`, `calibrate_bilirubin_index()` |
| `app/gui_qt/main_window.py:1426-1427` | Extend `_compute_global_scales` to include bilirubin index |
| `app/gui_qt/main_window.py:1555-1630` | Add bilirubin index computation in pipeline adapter's per-sample loop |
| `app/gui_qt/main_window.py:1335-1400` | `_build_config_snapshot`: capture `compute_bilirubin_index` flag |
| `app/gui_qt/main_window.py:1640+` | `_set_solver_dependent_controls`: add bilirubin-index checkbox visibility |
| `app/gui_qt/main_window.py:~397` | Toolbar: add checkbox for bilirubin index computation |
| `tests/test_bilirubin_index.py` | New file — 5 unit tests |
| `tests/test_km_phantom_validation.py:88+` | Add bilirubin-index halving assertions |
| `scripts/calibrate_bilirubin_index.py` | New file — calibration report generator |
| `data/chromophores/bili_agat.csv` | Reference spectrum (no changes needed) |
| `data/chromophores/hb_agat_extr.csv` | Reference spectrum (no changes needed) |
| `liquid_phantoms_for_unmixing_dng_cropped/A{1-6}/` | Calibration data (no changes) |

---

## 11. Resolved Design Decisions

| Decision | Resolution |
|----------|-----------|
| Primary index formula | `OD₄₅₀ − OD₅₁₇` |
| Hb reference band | 671 nm (bilirubin-free, modest Hb absorption) |
| Calibration model | Log-linear: `OD_diff = α·log₁₀([Bili]) + β` |
| Hb correction factor | Empirically calibrated, not from extinction ratios |
| UI exposure | Checkbox alongside solver, not a new solver method |
| Derived map key | `"Bilirubin Index (OD450−OD517)"` |
| Concentration claim | Index only; approximate µM conversion with caveats |
| Integration with KM solver | Independent (computed alongside any solver) |
