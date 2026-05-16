# KM Sensitivity Scan — Review

**Date:** 2026-05-16
**Scope:** `scripts/km_sensitivity_scan.py`, `app/core/processing.py`, `tests/test_km_phantom_validation.py`, `tests/test_kubelka_munk.py`, `features/kubelka_munk_implementation_plan.md`

---

## Correct

- **Reflectance-ratio sanity check** (`km_sensitivity_scan.py:208–224`). Computing R450/R517 per sample and verifying monotonic increase from A1→A6 is a model-free, data-quality verification that is well-placed and correctly implemented.

- **Band-subset design** (`km_sensitivity_scan.py:227–232`). The three subsets (2-band blue, 4-band visible, 8-band full) are a reasonable experimental matrix. The 2-band subset isolates the only bands where bilirubin has meaningful extinction, which directly tests the identifiability hypothesis.

- **Sample ordering** (`km_sensitivity_scan.py:55–56` + `load_context`). The `sample_sort_key` extracts the numeric suffix from A1…A6 and `load_context` re-sorts samples by that key. This guarantees the median arrays are in A1→A6 order regardless of OS folder listing order. Verified against `detect_folders` which uses `sorted(os.listdir())`.

- **Unit tests for KM core** (`tests/test_kubelka_munk.py`). The round-trip test (μa→R→μa with atol=1e-12) validates the KM forward/inverse pair. The synthetic concentration recovery test validates the full `solve_unmixing_km` pipeline on noise-free data. Non-negativity enforcement, missing-scattering error, and dispatcher support are all covered. All 7 tests pass.

- **Phantom validation smoke test** (`tests/test_km_phantom_validation.py`). Correctly asserts only finiteness and shape invariants, deferring concentration-trend assertions until the sensitivity scan informs calibration. Aligns with the phased plan in the implementation document.

- **CSV output** (`km_sensitivity_scan.py:240–268`). Produces well-structured CSV with all scan parameters, per-sample concentrations, and metrics. Field ordering is explicit and reproducible.

- **`clip_negative_extinction=True` usage** in the scan's `load_context` (line 130) correctly prevents the Agati bilirubin spectrum (which ends at 550 nm) from producing negative extrapolated absorption in NIR bands during absorption-matrix construction.

---

## Blocker

### 1. `_reflectance_to_mu_a_km` valid mask checks original reflectance, not clipped — negative/zero reflectance treated as valid

**File:** `app/core/processing.py`, lines 1215–1223

```python
R = np.clip(reflectance_arr, eps, 1.0 - eps)          # line 1218
F = (1.0 - R) ** 2 / (2.0 * R)                         # line 1219
mu_a = F * mus_prime_arr / 2.0                          # line 1220
valid = np.isfinite(reflectance_arr) & ...              # line 1221 ← bug
```

`valid` is computed from the *original* `reflectance_arr`, not the clipped `R`. A pixel with `reflectance = 0.0` (or `-0.1`, or `-inf`) gets clipped to `eps = 1e-10`, yielding `F ≈ 5×10⁹` and `μa ≈ 2.5×10¹⁰ cm⁻¹` (for μs′=10). But `np.isfinite(0.0)` is `True`, so this pixel is marked valid and the absurd μa is passed to NNLS, where it swamps the fit.

The `valid` mask must check the domain of the KM remission function: `R` must satisfy `0 < R < 1` (strict, not just finite). The fix should add `(reflectance_arr > 0) & (reflectance_arr < 1.0)` to the valid condition, or check the clipped `R`.

**Impact:** While well-exposed phantom images may not trigger this, any dark/edge/background pixel can inject spurious huge absorption into the NNLS, biasing the spatial-median concentration estimates and corrupting the scan metrics. This is a correctness bug in the core solver, not just the scan script.

**Recommendation:** Replace the `valid` computation with:

```python
valid = (
    (reflectance_arr > 0) & (reflectance_arr < 1.0)
    & np.isfinite(reflectance_arr)
    & np.isfinite(mus_prime_arr)
    & (mus_prime_arr > 0)
    & np.isfinite(mu_a)
    & (mu_a >= 0)
)
```

And update the corresponding unit test `test_reflectance_to_mu_a_km_clips_nonphysical_reflectance` to also assert that reflectance ≤ 0 (and ≥ 1) produce `valid == False`, not just that μa is finite.

---

## High

### 2. `bili_positive_a1` threshold (eps=1e-12) is 12 orders of magnitude below any plausible concentration — numerical noise can trigger a false positive

**File:** `scripts/km_sensitivity_scan.py`, line 87

```python
bili_positive_a1 = bool(bili_medians[0] > eps) if bili_medians.size else False
```

where `eps = 1e-12` (line 72). Expected bilirubin in A1 is 270 µM; solver-internal units appear to be ~µM scale (Hb recovers ~50). Machine-precision noise at 1e-15 or 1e-14 is below this threshold, but any solver regime that produces even a 1e-10 residual (e.g., from a degenerate NNLS) would incorrectly count as "positive bilirubin."

Combined with the recommendation filter (`bili_positive_a1 == True`), a zero-bilirubin model with a 1e-9 noise floor would pass this gate, misleading the recommendation logic.

**Recommendation:** Set the threshold to a meaningful fraction of the expected concentration — e.g., `bili_medians[0] > 1.0` (1 µM in solver units) or a fraction of ground truth like `0.01 * GROUND_TRUTH_UM["A1"][1]`.

### 3. `hb_cov` passes trivially when Hb is recovered as all-zero

**File:** `scripts/km_sensitivity_scan.py`, lines 79–80

```python
hb_mean = float(np.mean(hb_medians))
hb_cov = float(np.std(hb_medians) / (hb_mean + eps))
```

If all six Hb medians are 0.0, then `hb_mean = 0.0`, `hb_std = 0.0`, and `hb_cov = 0.0 / 1e-12 = 0.0`. This passes `hb_cov < 0.20` trivially. A model that completely fails to detect Hb would receive full credit on the Hb-constancy metric.

Combined with Finding 2, a model that recovers zero Hb everywhere and zero bilirubin everywhere (with a 1e-9 noise floor in A1) could: (a) pass `bili_positive_a1`, (b) score `bili_mono = 5`, (c) have `hb_cov = 0.0 < 0.20`, and thus pass the recommendation filter. The `bili_range` and `bili_log2_slope` terms would be low, keeping the overall composite score low, but the recommendation logic would still flag it as "valid."

**Recommendation:** Add an `hb_positive` guard analogous to `bili_positive_a1` — e.g., require `hb_mean > a_meaningful_threshold` before accepting `hb_cov` as meaningful. Or gate `hb_cov` behind `hb_mean > eps_meaningful` by returning a sentinel (e.g., `hb_cov = 1.0`) when Hb is effectively absent.

### 4. `bili_range` computes max/min without checking ordering — scrambled concentrations can yield large dynamic range

**File:** `scripts/km_sensitivity_scan.py`, lines 82–83

```python
bili_max = float(np.max(bili_medians)) if bili_medians.size else 0.0
bili_min = float(np.min(bili_medians)) if bili_medians.size else 0.0
bili_range = 0.0 if bili_max <= eps else float(bili_max / max(bili_min, eps))
```

If the solver returns bilirubin medians `[5, 100, 10, 200, 8, 50]` for A1–A6, `bili_range = 200/5 = 40`, giving `min(1.0, 40/10) = 1.0` — full composite credit for dynamic range despite the series being completely out of order. The `bili_mono` metric would catch most of this (mono=0 in this example), but if 4/5 steps are accidentally non-increasing while the magnitude is scrambled, both metrics could give misleadingly high scores.

**Recommendation:** Either (a) compute the range as `bili_medians[0] / bili_medians[-1]` (first-to-last ratio) which implicitly checks direction, or (b) keep max/min range but weight it down when `bili_mono` is imperfect. The current composite treats these independently.

---

## Medium

### 5. No Hb monotonicity metric — Hb drift passes undetected

**File:** `scripts/km_sensitivity_scan.py`, `compute_metrics` (no equivalent of `bili_mono` for Hb)

The composite rewards `1.0 - hb_cov` for low Hb variability, but CoV can be low even with a systematic drift. For example, Hb values `[120, 115, 110, 105, 100, 95]` have mean=107.5, std≈8.5, CoV≈0.079 — excellent composite contribution — despite a clear downward trend. This matters because Hb should be *constant*, not just low-variance.

**Recommendation:** Add an `hb_mono_violations` metric counting how many Hb steps are monotonic in either direction, and penalize any systematic trend.

### 6. All-zero bilirubin produces `bili_mono = 5` (full credit for monotonicity)

**File:** `scripts/km_sensitivity_scan.py`, line 81

```python
bili_mono = int(np.sum(np.diff(bili_medians) <= 0.0))
```

If `bili_medians = [0, 0, 0, 0, 0, 0]`, then `np.diff` gives `[0, 0, 0, 0, 0]`, all `≤ 0.0`, so `bili_mono = 5`. The metric gives full credit for "monotonic" bilirubin when there's no bilirubin at all. `bili_positive_a1` catches this in theory, but with the eps=1e-12 threshold (Finding 2) it may not.

**Recommendation:** Gate `bili_mono` on `bili_positive_a1` being true (i.e., only score monotonicity when bilirubin is actually present). Or return `bili_mono = 0` when `bili_positive_a1` is false.

### 7. Calibration-scan scattering differs from scattering-scan range — cross-comparison misleading

**File:** `scripts/km_sensitivity_scan.py`, lines 184–189

The calibration scan hardcodes:
```python
mus_prime = build_scattering_profile(
    ...,
    processing.SCATTERING_MU_S_500_CM1 * DEFAULT_F_LIPO * (1.0 - DEFAULT_G),
    ...
)
```
which sets `effective_mu_s_500 = 120.0 × 0.25 × 0.2 = 6.0 cm⁻¹`. But the scattering scan sweeps `effective_mu_s_500` from 0.5 to 240 cm⁻¹. When both scan types are ranked together by composite score, a user reading the top rows sees calibration rows with μs'(500)=6.0 and scattering rows with various μs'(500) values, and may not realize the calibration rows use a *different, fixed* scattering value.

The `scan` field in the output distinguishes them, but the print format (`km_sensitivity_scan.py:250–258`) doesn't draw attention to this.

**Recommendation:** Print the `scan` type prominently in the top-rows output, or run calibration scans at *each* scattering grid point so the K-scan is conditioned on the scattering regime. (This would make the grid much larger but avoids the apples-to-oranges ranking.)

---

## Low / Notes

### 8. `bili_log2_slope` is tuned exclusively for exact halving (factor of 2 per step)

**File:** `scripts/km_sensitivity_scan.py`, lines 84–89

```python
for left, right in zip(bili_medians[:-1], bili_medians[1:]):
    if left > eps and right > eps:
        slopes.append(float(np.log2(right / left)))
```

The composite rewards `abs(bili_log2_slope + 1.0)` close to 0. A bilirubin series that decreases by a factor of 3 per step (log2(1/3) ≈ -1.58) gets `abs(-1.58 + 1.0) = 0.58`, contributing only 0.42 to the composite — worse than a flat series (which contributes 0). This is intentional given the known ground-truth halving pattern, but it means the metric is a *pattern-match* rather than a generic "detect decreasing trend" metric. This is defensible for a diagnostic scan targeting known phantom composition, but worth documenting.

### 9. `build_scattering_profile` hardcodes `lipofundin_fraction=0.25` and `anisotropy_g=0.8` without exposing them as scan axes

**File:** `scripts/km_sensitivity_scan.py`, lines 141–150

The scan varies `effective_mu_s_500` and `power_b`, but not the scattering composition parameters. Since `effective_mu_s_500` already spans two orders of magnitude, varying f_lipo and g would largely shift the effective range rather than explore new scattering shapes. This is acceptable for a first-pass diagnostic.

### 10. The `reflectance_ratio_sanity` check (`R450/R517`) confirmed monotonic increase from A1→A6

This is a strong, model-free signal that the data contain the expected bilirubin trend (less bilirubin → less blue absorption → higher R450 → higher ratio). The fact that the KM solver cannot recover this trend under *any* scanned parameter regime is evidence of a structural identifiability limitation, not a code bug. The implementation plan (Stage C follow-up) correctly identifies this hypothesis.

### 11. Test `test_km_phantom_validation.py` uses `np.nanmedian`/`np.nanmean` for robustness, but the scan uses an explicit finite-filter-then-median approach

Both are functionally equivalent when `finite_fraction == 1.0` (which the test asserts). No bug here, but the scan's `spatial_medians` silently returns `0.0` when no finite values exist — this edge case is not documented.

### 12. CLI design is clean and well-documented

`--quick`, `--skip-calibration`, `--top`, `--output` are sensible options. Help text includes defaults. No usability issues found.

---

## Overfitting Safeguards

The scan script explicitly avoids per-sample or per-chromophore tuning (noted in docstring line 10). All parameters are global across the entire A1–A6 series. The composite score is a multi-objective aggregate (Hb constancy, bilirubin monotonicity, bilirubin dynamic range, bilirubin halving slope, bilirubin positivity), which discourages overfitting to any single metric.

**Gap:** The composite score is itself a hand-tuned weighted sum with no cross-validation or held-out test. If the user iteratively refines the metric weights or thresholds based on scan results from the *same* dataset, this becomes a form of manual overfitting. The `--top` flag prints the best N rows, which invites such iteration. This is acceptable for a *diagnostic* script but should not be misinterpreted as model selection with statistical guarantees.

The recommendation filter (`bili_positive_a1 && bili_mono >= 4 && hb_cov < 0.20`) is conservative but, as shown in Findings 2–3, has edge-case leaks.

---

## Can Results Be Trusted?

**The scan's negative result (no regime recovers bilirubin) is credible** because:

1. The reflectance-ratio sanity check independently confirms the data quality.
2. The bilirubin spectrum (`bili_agat.csv`) ends at 550 nm — beyond that, clipped extinction is zero, so NIR bands contribute zero bilirubin information.
3. With only 2 informative bands (450, 517) and 2 chromophores (Hb, bilirubin) that have similar blue-absorption shapes, NNLS faces a fundamental identifiability challenge.
4. The parameter grid is broad (μs'(500) from 0.5–240 cm⁻¹, power-law b from 0.1–3.0, calibration K from 0.01–10).
5. The scan tests three band subsets (2, 4, 8), confirming the limitation persists across feature sets.

**However, the positive result (no valid regime found) could be affected by**:

- The `_reflectance_to_mu_a_km` valid-mask bug (Finding 1), which could corrupt μa estimates for dark edge pixels and bias spatial medians.
- The `bili_positive_a1` false-positive risk (Finding 2), which could cause the recommendation logic to *miss* a borderline regime that should have been flagged. (This doesn't affect the negative finding but means the filter's "no valid rows" conclusion might be slightly overstated.)
- The fixed scattering composition parameters (f_lipo=0.25, g=0.8) were not scanned. The effective μs' range covers the same numerical space, but the *spectral shape* of μs'(λ) changes with the power-law exponent `b` only. This is likely adequate.

**Bottom line:** The finding that classic KM + Agati spectra + current LED set cannot recover bilirubin is well-supported and correctly attributed to structural identifiability limitations. The scan is methodologically sound for its diagnostic purpose, with the blocker-level valid-mask bug being the only finding that could materially change results if fixed.
