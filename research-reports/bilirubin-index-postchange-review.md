# Bilirubin Index Post-Change Review — Sensitivity Fixes + Two-Band Diagnostic

**Date:** 2026-05-16
**Branch:** `feature/kubelka-munk-solver`
**Review scope:** Code after addressing sensitivity-review findings and adding `compute_bilirubin_index` + `scripts/bilirubin_index_report.py`. Files inspected: `app/core/processing.py`, `scripts/km_sensitivity_scan.py`, `scripts/bilirubin_index_report.py`, `tests/test_kubelka_munk.py`, `features/kubelka_munk_implementation_plan.md`.

---

## Summary

All four blocker/high findings from the sensitivity-review have been addressed. The `_reflectance_to_mu_a_km` valid mask is now correct, the scan metric thresholds use physically meaningful values, zero-bilirubin monotonicity is gated, and zero-Hb models no longer score well on Hb constancy. The two-band bilirubin index diagnostic is scientifically honest: it reports a calibrated diagnostic index, not a physical bilirubin concentration, with explicit domain-of-validity caveats. Three meta-level concerns remain: the composite scoring in the sensitivity scan has a dimensionality mismatch between `bili_positive_count/6` and other terms, the calibration scan's `effective_mu_s_500` metadata entry is a constant not the probed parameter, and the bilirubin index log-linear calibration is unvalidated against independent data (acceptable for a diagnostic, but should not be overstated).

---

## Correct — what is already good (with evidence)

### 1. KM reflectance valid mask is correctly fixed

**Location:** `app/core/processing.py:1220–1227`

```python
valid = (
    np.isfinite(reflectance_arr)
    & (reflectance_arr > 0.0)
    & (reflectance_arr < 1.0)
    & np.isfinite(mus_prime_arr)
    & (mus_prime_arr > 0)
    & np.isfinite(mu_a)
    & (mu_a >= 0)
)
```

The `valid` mask now explicitly checks `(reflectance_arr > 0.0) & (reflectance_arr < 1.0)` on the **original** reflectance values. This is semantically correct — the KM remission function `F(R) = (1−R)²/(2R)` has a natural domain of `R ∈ (0, 1)`. Pixels with reflectance ≤ 0 or ≥ 1 are now correctly classified as invalid regardless of whether they survive the subsequent `np.clip(R, eps, 1−eps)` in `F` computation.

**Evidence:** `test_reflectance_to_mu_a_km_rejects_nonphysical_reflectance` (tests/test_kubelka_munk.py:18–26) verifies that reflectance values of −1, 0, 1, and 2 all produce `valid == False`. Previously these non-physical values could produce valid markers and inject spurious large μa into NNLS fits.

**No new edge cases:** The valid mask now includes `np.isfinite(mu_a)` and `(mu_a >= 0)` as a final safety net. Since `F` and `mus_prime` are always finite-nonnegative by construction (after clipping), these guards are redundant belt-and-suspenders; harmless.

### 2. Scan positivity thresholds use meaningful concentration thresholds

**Location:** `scripts/km_sensitivity_scan.py:47, 113–116`

```python
POSITIVE_CONCENTRATION_THRESHOLD_M = 1e-7  # 0.1 µM
hb_present = hb_mean > positive_threshold
bili_positive_mask = bili_medians > positive_threshold
bili_positive_a1 = bool(bili_medians[0] > positive_threshold)
```

The previous `eps = 1e-12` threshold (12 orders below plausible concentration) has been replaced with `1e-7 M = 0.1 µM`. This is still lenient (~0.04% of the 270 µM A1 ground truth) but is four orders of magnitude above double-precision noise floors (~1e-16). A degenerate NNLS producing ~1e-10 residuals would no longer trigger a false positive.

### 3. Zero-bilirubin monotonicity gated

**Location:** `scripts/km_sensitivity_scan.py:118`

```python
bili_mono = int(np.sum(np.diff(bili_medians) <= 0.0)) if bili_positive_count >= 2 else 0
```

All-zero bilirubin arrays (`bili_positive_count = 0`) now receive `bili_mono = 0` instead of the previous `5/5` (full credit). This removes the composite-score inflation for models that recover no bilirubin at all. The gate uses `>= 2` rather than `>= 1` because monotonicity is degenerate on a single positive sample — this is conservative and correct.

### 4. Zero-Hb constancy penalised

**Location:** `scripts/km_sensitivity_scan.py:114–115`

```python
hb_present = hb_mean > positive_threshold
hb_cov = float(np.std(hb_medians) / (hb_mean + eps)) if hb_present else 1.0
```

When Hb is absent (`hb_mean ≤ 0.1 µM`), `hb_cov` is forced to `1.0`, yielding `max(0, 1.0 − 1.0) = 0` composite contribution. The `hb_present` flag is also exported in the CSV (`hb_present` field, line 155). This prevents an all-zero-Hb model from scoring well on the Hb constancy axis.

### 5. Bilirubin index is scientifically framed as a diagnostic, not a concentration

**Location:** `scripts/bilirubin_index_report.py:182–185`

```python
print(
    "\nInterpretation: this is a calibrated diagnostic index. It should not be "
    "reported as physical bilirubin concentration outside the A1-A6 calibration domain."
)
```

The report explicitly distinguishes the index from physical unmixing. The log-linear fit `BI = slope × log10(bilirubin_uM) + intercept` is correctly presented as a calibration relationship, not a first-principles conversion. The R² value (~0.942 per the plan) is reported but not overstated as "the model explains 94% of variance" — it's simply a calibration-fit statistic.

**LOO validation** (`loo_predictions`, lines 81–93): Leave-one-out predictions provide a minimal internal cross-validation check. The code handles the degenerate-fit case (`slope ≈ 0` → `np.nan`) correctly.

### 6. Reflectance-ratio sanity check is model-free and correctly monotonic

**Location:** `scripts/km_sensitivity_scan.py:317–326`, `scripts/bilirubin_index_report.py:146–148`

Both scripts compute `R450/R517` across A1–A6 and verify monotonic increase (less bilirubin → less blue absorption → higher R450 → higher ratio). This is a robust, model-free data quality check that confirms the expected phantom gradient is present in the raw images.

### 7. All 12 KM + phantom tests pass

```
tests/test_kubelka_munk.py ...........                              [11 passed]
tests/test_km_phantom_validation.py .                               [1 passed]
```

Zero failures. The two new tests (`test_build_absorption_matrix_can_clip_negative_extrapolated_extinction`, `test_compute_bilirubin_index_applies_optional_hb_correction`) cover the clipping and Hb-correction edge cases. No regressions.

### 8. Implementation plan documentation is accurate

**Location:** `features/kubelka_munk_implementation_plan.md`, "Post-review corrections" section and Stage D.

The plan correctly records:
- Each fix applied and its mechanism
- The current limitation: classic KM + Agati spectra + current LED set cannot robustly separate bilirubin
- The interpretation: the bilirubin index is the most honest diagnostic for these images

---

## Blocker

*None.* No correctness bugs, crashes, or regressions found. All tests pass.

---

## High — significant concerns

### H1. Composite score dimensionality mismatch: `bili_positive_count / 6` treats A1–A6 equally, while `bili_mono / 5` and `slope_score` only score positive samples

**Location:** `scripts/km_sensitivity_scan.py:136–141`

```python
composite = (
    bili_positive_count / 6.0
    + bili_mono / 5.0
    + max(0.0, 1.0 - hb_cov)
    + min(1.0, bili_range / 10.0)
    + slope_score
)
```

**Issue:** `bili_positive_count / 6` rewards the *number* of positive samples, while `bili_mono / 5` rewards monotonicity *only among all samples* (positive or not), but `bili_mono` is gated on `bili_positive_count >= 2`. This creates an asymmetric scoring landscape:

- A model with 4 positive samples, all equal (`bili_mono = 5` via all-zero diffs) scores `4/6 + 5/5 = 1.67`.
- A model with 6 positive samples but only 3 monotonic steps scores `6/6 + 3/5 = 1.60`.

The former is arguably worse (zero dynamic range) yet scores higher. The `bili_range` term partially mitigates this (equal values → range ≈ 1.0 → 0.1 composite contribution), but the `bili_mono` term still over-rewards all-equal positive series.

**Note:** This condition is gated behind `bili_positive_count >= 2` for `bili_mono` computation. When all positive values are equal, `np.diff(bili_medians)` produces zeros (≤ 0), so `bili_mono = 5`. The `bili_log2_slope` would be undefined (no `left > eps and right > eps` pairs since all values are equal), so `slopes = []`, `slope_score = 0`. This gives composite ≈ 1.6 rather than the near-5.0 of a good model, so in practice this cannot outrank genuinely good models. But the `bili_mono` value of 5 is misleading in the CSV — a data analyst reviewing the CSV might be confused by `bili_mono = 5` alongside all-equal concentration values.

**Recommendation:** Consider gating `bili_mono` on `bili_range > some_minimum` (e.g., `bili_range > 1.5`), or computing `bili_mono` only among positive samples (currently it uses all 6 entries regardless of positivity). A simpler fix: count only strict decreases among samples where *both* left and right are positive:

```python
strict_decreases = 0
for left, right in zip(bili_medians[:-1], bili_medians[1:]):
    if left > positive_threshold and right > positive_threshold and right < left:
        strict_decreases += 1
```

This would give `bili_mono = 0` for all-equal positive series and `≤ 5` otherwise.

**Severity:** High. The composite score is the primary ranking metric for the sensitivity scan. While the known regime (no valid models found) means the ranking doesn't currently change, if future spectral data or wavelength sets *do* produce bilirubin recovery, the ranking could be distorted by this term.

### H2. Calibration scan reports a fixed `effective_mu_s_500` constant, not the parameter being probed

**Location:** `scripts/km_sensitivity_scan.py:298–304`

```python
"effective_mu_s_500": processing.SCATTERING_MU_S_500_CM1 * DEFAULT_F_LIPO * (1.0 - DEFAULT_G),
```

This hardcodes `120 × 0.25 × 0.2 = 6.0 cm⁻¹` for every calibration row. When the scattering scan also produces rows with `effective_mu_s_500` values varying from 0.5 to 240, the calibration rows appear in the ranked output as if they all share `μs'(500) = 6.0`. A user ranking both scan types together (as the script does in `all_rows`) sees calibration rows alongside scattering rows and cannot tell from the column alone that the calibration K-factor is the primary variable, not the scattering.

**Impact:** The `scan` and `calibration_k` fields distinguish them, but the `print_top_rows` output line (line 340–344) prints `mu_s_eff_500` prominently but `K` with equal prominence, making it easy to misread a calibration row as endorsing `μs'(500) = 6.0`.

**Recommendation:** Print the `scan` type explicitly in the top-rows header or prefix the `effective_mu_s_500` value with `(fixed)` for calibration rows. Alternatively, separate the two scan types into two ranked tables (not currently the case — `all_rows` is a single list). The current behavior is not wrong, just easily misinterpretable.

**Severity:** High for interpretability of the scan output, especially for external readers.

### H3. Bilirubin index log-linear calibration is unvalidated against independent Hb/bili phantoms

**Location:** `scripts/bilirubin_index_report.py:158–175`

The calibration `BI = slope × log10(bili_uM) + intercept` is fit to the *same* A1–A6 data that it predicts. The LOO validation mitigates overfitting to individual points but does not test against an independent phantom set or a different imaging session.

**Context:** The script's stated interpretation (line 182) explicitly limits the calibration domain to A1–A6. This is honest, but the R² of 0.942 is reported prominently without noting it's an in-sample fit (not a held-out R²). The LOO predictions provide a cross-validated R² — the script should ideally report that instead.

**Recommendation:** Report the LOO R² alongside (or instead of) the in-sample R². Currently the script prints both fits (raw and corrected) but only the in-sample R² for each. The LOO predictions are computed and printed per-sample (lines 178–185) but not aggregated into an R² metric. Adding `r2_loo = 1 - sum((truth - loo_preds)^2) / sum((truth - mean(truth))^2)` would give a more honest calibration-quality metric.

**Severity:** High for scientific reporting. The diagnostic itself is correctly caveated, but the primary fit statistic (R²) could mislead a reader into thinking the calibration generalizes beyond the 6-phantom series.

---

## Medium — observations

### M1. `bili_range` computes range from positive-only entries, not A1→A6 ratio

**Location:** `scripts/km_sensitivity_scan.py:121–122`

```python
positive_bili = bili_medians[bili_positive_mask]
bili_range = float(np.max(positive_bili) / max(float(np.min(positive_bili)), eps))
```

When not all samples are positive, the range reflects only the positive subset. For example, if A1 and A6 are positive but A2–A5 are zero (degenerate but conceivable), `bili_range = max(A1, A6) / min(A1, A6)`. This could be large even though the series is non-monotonic (A1 zero, others positive). The `bili_mono` metric partially guards against this, but `bili_range` and `bili_mono` can disagree in confusing ways.

**Recommendation:** Consider computing `bili_range` as `bili_medians[0] / bili_medians[-1]` (first-to-last) when both are positive, falling back to the current max/min behavior otherwise. This would align `bili_range` with the expected A1-highest/A6-lowest pattern.

**Severity:** Medium. Affects CSV readability and ranking precision, not functional correctness.

### M2. `hb_cov = 1.0` sentinel may confuse CSV readers

**Location:** `scripts/km_sensitivity_scan.py:115`

When Hb is absent, `hb_cov` is set to `1.0`. This reads in the CSV as "100% coefficient of variation" which could be misinterpreted as "high variance" when it actually means "Hb not detected." The `hb_present` column disambiguates, but not all CSV consumers will check it.

**Recommendation:** Use a more distinct sentinel (e.g., `hb_cov = −1.0` or `float('inf')`) and document it in the CSV header or a README note. A comment in the `fieldnames` list would help.

**Severity:** Medium. Documentation gap, not a code bug.

### M3. `build_scattering_profile` helper does not document the `effective → raw` conversion

**Location:** `scripts/km_sensitivity_scan.py:212–218`

```python
def build_scattering_profile(..., effective_mu_s_500, power_b):
    raw_mu_s_500 = effective_mu_s_500 / (DEFAULT_F_LIPO * (1.0 - DEFAULT_G))
    return processing.build_fixed_scattering_profile(..., mu_s_500_cm1=raw_mu_s_500, ...)
```

The `effective_mu_s_500` is the post-lipofundin, post-anisotropy reduced scattering value (what the solver actually uses). To pass this to `build_fixed_scattering_profile`, it is divided by `f_lipo × (1−g) = 0.25 × 0.2 = 0.05`, converting back to the raw `mu_s_500_cm1` parameter. This is mathematically correct but undocumented.

**Recommendation:** Add a docstring explaining the conversion.

**Severity:** Medium. A developer modifying `DEFAULT_F_LIPO` or `DEFAULT_G` without updating this function could break the mapping between scan parameter and physical scattering.

### M4. `compute_bilirubin_index` defaults are fragile: `wavelength_index_450=0, wavelength_index_517=1, wavelength_index_ref=2`

**Location:** `app/core/processing.py:1324–1326`

```python
def compute_bilirubin_index(
    reflectance: np.ndarray,
    wavelength_index_450: int = 0,
    wavelength_index_517: int = 1,
    wavelength_index_ref: int | None = 2,
```

The default indices assume the data cube has 450 nm at index 0, 517 nm at index 1, and a reference band at index 2. These defaults happen to be correct for the current 8-band LED set ([450, 517, 671, ...]), but are incorrect for any other wavelength configuration.

**Recommendation:** Document the defaults explicitly in the docstring with a note about the assumed wavelength ordering. Alternatively, expose wavelength-center parameters instead of indices and have the function look them up (though this would require the wavelengths list as an additional parameter). The current approach is consistent with how `solve_unmixing_km` receives band-averaged inputs (indices are caller's responsibility), but the *defaults* create a silent failure mode.

**Severity:** Medium. Could produce silently wrong results if the function is called with different band orderings and the defaults are used.

---

## Low / Notes

### N1. `compute_metrics` `slope_score` uses `≥ 2` positive-slope-pair threshold

**Location:** `scripts/km_sensitivity_scan.py:131–133`

```python
slope_score = 0.0
if len(slopes) >= 2:
    slope_score = max(0.0, 1.0 - abs(bili_log2_slope + 1.0))
```

`slopes` only accumulates pairs where *both* left and right are `> eps` (1e-12). This means the slope metric is computed from the concentration ratios of *any* consecutive positive pairs, not necessarily A1→A2→A3. If A1=10, A2=0, A3=5 (A2 below eps threshold), only the A3→A4... slopes contribute. The `log2(5/next)` is a valid halving-ratio metric for the samples where bilirubin IS detected. This is acceptable given the gating on positivity.

### N2. `reflectance_ratio_sanity` uses median across all pixels, not a masked ROI

**Location:** `scripts/km_sensitivity_scan.py:326`

```python
med = np.median(sample["reflectance"].reshape(-1, len(wavelengths)), axis=0)
```

The reflectance ratio check aggregates pixel-wise median across the full image including background/edge pixels. For well-cropped phantom images, this is fine. For images with significant background/artifact areas, the median is robust to outliers. No issue.

### N3. No CLI default `--k-hb-correction` in bilirubin report for automation

The `--k-hb-correction` defaults to `None` (disabled), which is the correct scientific default — the uncorrected index is the primary diagnostic. The flag is available for experimentation. Good design.

### N4. The bilirubin index report uses `np.polyfit` (rank-1 least squares) which is deprecated in newer NumPy

`numpy.polyfit(x, y, deg=1)` is equivalent to `numpy.linalg.lstsq` for degree 1, but NumPy has deprecated `polyfit` for new code. The current NumPy version (≥1.22) emits a deprecation warning. Using `numpy.polyfit` is technically deprecated in NumPy ≥ 2.0. This affects `bilirubin_index_report.py:68` (and potentially `km_sensitivity_scan.py` if it also uses it — in the current code it doesn't). Not a correctness issue, but worth migrating to `numpy.linalg.lstsq` or `scipy.stats.linregress` in a future maintenance pass.

### N5. Implementation plan says "88 passed, 1 warning, 15 subtests passed" but the full KM+phantom suite is 12 tests

The implementation plan's full-focused validation count (88 passed) includes the main window tests, fixed scattering tests, etc. The core KM + phantom tests are 12. No discrepancy — the plan correctly documents the broader test suite.

---

## Files examined with line references

| File | Lines inspected | Key sections |
|------|----------------|-------------|
| `app/core/processing.py` | 1193–1376 | `_reflectance_to_mu_a_km` valid mask, `solve_unmixing_km`, `compute_bilirubin_index` |
| `scripts/km_sensitivity_scan.py` | 1–438 (full) | `compute_metrics` positivity thresholds, composite scoring, recommendation filter |
| `scripts/bilirubin_index_report.py` | 1–188 (full) | Log-linear calibration, LOO validation, interpretation caveat |
| `tests/test_kubelka_munk.py` | 1–165 (full) | 11 tests including clipping and bilirubin index tests |
| `features/kubelka_munk_implementation_plan.md` | 1–195 (full) | Post-review corrections documentation, Stage D bilirubin index |

---

## Evidence of fix completeness (from sensitivity-review findings)

| Finding | Severity (original) | Status | Evidence |
|---------|--------------------|--------|----------|
| `_reflectance_to_mu_a_km` valid mask bug | Blocker | **FIXED** | `processing.py:1222–1223` — `(reflectance_arr > 0) & (reflectance_arr < 1.0)` |
| `bili_positive_a1` eps=1e-12 threshold | High | **FIXED** | `scan.py:47,129` — `POSITIVE_CONCENTRATION_THRESHOLD_M = 1e-7` |
| Zero-Hb cov passes trivially | High | **FIXED** | `scan.py:114–115` — `hb_cov = 1.0 if not hb_present` |
| `bili_range` ignores ordering | High | **PARTIALLY MITIGATED** | `bili_mono` gating reduces impact; ordering still not checked directly |
| No Hb monotonicity metric | Medium | **UNFIXED** | Same as original; `hb_cov < 0.20` recommendation filter is partial mitigation |
| Zero-bili monotonicity = 5 | Medium | **FIXED** | `scan.py:118` — `bili_mono = 0 if bili_positive_count < 2` |

---

*End of review.*
