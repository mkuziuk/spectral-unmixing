# Forward Calibration Plan — Two-Band Bilirubin Index (OD450−OD517)

**Date:** 2026-05-16
**Branch:** `feature/kubelka-munk-solver`
**Context:** The two-band bilirubin index `OD450 − OD517` is implemented as a derived diagnostic map (GUI checkbox), with a 6-point in-sample log-linear calibration yielding R² ≈ 0.942 but negative LOO R². This plan defines how to advance the calibration from an exploratory diagnostic to a defensible quantitative index.

---

## 1. Current State Assessment

### 1.1 What exists

| Component | File | Status |
|-----------|------|--------|
| Core index computation | `app/core/processing.py:1322` — `compute_bilirubin_index()` | ✅ production-ready |
| Calibration report CLI | `scripts/bilirubin_index_report.py` | ✅ working, in-sample + LOO |
| GUI derived-map exposure | `app/gui_qt/main_window.py` — checkbox + derived maps | ✅ implemented |
| Unit tests | `tests/test_kubelka_munk.py:91` — 2 tests | ✅ passing |
| In-sample calibration | `bili_agat.csv` + `hb_agat_extr.csv`, 6 points | ⚠️ negative LOO R² |
| Independent validation | None | ❌ missing |

### 1.2 Known calibration numbers (from `research-reports/bilirubin_index_report.csv`)

| Phantom | [Bili] µM | R450/R517 | BI_raw (OD450−OD517) |
|---------|----------:|----------:|---------------------:|
| A1 | 270.0 | 0.9195 | 0.03648 |
| A2 | 135.0 | 0.9360 | 0.02844 |
| A3 | 67.5 | 0.9452 | 0.02446 |
| A4 | 33.75 | 0.9567 | 0.01882 |
| A5 | 16.88 | 0.9613 | 0.01708 |
| A6 | 8.44 | 0.9630 | 0.01481 |

- **Monotonic:** yes (BI_raw strictly decreasing A1→A6)
- **Log-linear in-sample fit:** `BI = 0.01405 × log₁₀([Bili]) − 0.00024`, R² = 0.942
- **LOO R²:** −4.45 (strongly negative — the model overfits the calibration set)

### 1.3 Why LOO R² is negative

With only 6 calibration points, and A1 as both the highest-concentration and most-unusual point, LOOCV sees each left-out Aᵢ as having a very different relationship to the remaining 5 points. The negative LOO R² means the in-sample calibration curve is dominated by the A1→A2 concentration gap and does not generalize even within the A-series. This is a **fundamental small-N problem**, not a code bug.

---

## 2. Calibration Design

### 2.1 Model Form

The current (and recommended) calibration model is:

```
BI_corrected = OD₄₅₀ − OD₅₁₇ − k · OD₆₇₁

log₁₀([Bili]_est) = (BI_corrected − β) / α
```

Where:
- `α` = slope in OD-difference per decade of bilirubin concentration
- `β` = intercept (baseline OD difference from constant Hb + scattering)
- `k` = optional Hb-correction factor (default 0 = uncorrected)

**Rationale for log-linear:** Bilirubin concentration varies over 1.5 orders of magnitude in the calibration series (8.4→270 µM) and over ~2.5 orders in neonatal clinical ranges (0.5→50 mg/dL = 8.5→855 µM). A log-linear relationship respects the multiplicative nature of Beer-Lambert absorption while keeping the calibration invertible with two parameters.

### 2.2 Calibration Phantom Series Design

To move from 6-point to a defensible calibration, the minimal viable forward calibration phantom series is:

#### Core series: Independent bilirubin halving, fixed Hb = 100 µM (replicate A1–A6)

- **Purpose:** Directly comparable to existing A1–A6; tests reproducibility across preparation sessions and imaging sessions.
- **Samples:** 6 phantoms, identical protocol to existing A1–A6.
- **What it validates:** Session-to-session reproducibility of α and β; whether the calibration coefficients transfer to a new phantom batch.
- **Success criterion:** α and β estimates from the new series within 2× standard error of the original estimates.

#### Series 2: Intermediate Hb levels

| Phantom | [Bili] µM | [Hb] µM | Purpose |
|---------|----------:|--------:|---------|
| H1 | 270 | 100 | High-bili, baseline Hb (= replicates A1) |
| H2 | 135 | 100 | Mid-bili, baseline Hb |
| H3 | 67.5 | 100 | Low-bili, baseline Hb |
| H4 | 270 | 50 | High-bili, half Hb |
| H5 | 135 | 50 | Mid-bili, half Hb |
| H6 | 67.5 | 50 | Low-bili, half Hb |
| H7 | 135 | 200 | Mid-bili, double Hb |
| H8 | 67.5 | 200 | Low-bili, double Hb |

- **Purpose:** Tests whether Hb correction factor `k` is stable across Hb levels.
- **What it validates:** The correction `BI_corrected = BI_raw − k·OD₆₇₁` removes Hb-dependent bias at the 50–200 µM range.
- **Success criterion:** Corrected BI values for equal [Bili] agree within ±20% across Hb levels.

#### Series 3: Variable scattering

| Phantom | [Bili] µM | [Hb] µM | Lipofundin fraction |
|---------|----------:|--------:|--------------------:|
| L1–L3 | 270, 67.5, 16.9 | 100 | 0.25× (baseline) |
| L4–L6 | 270, 67.5, 16.9 | 100 | 0.50× |
| L7–L9 | 270, 67.5, 16.9 | 100 | 0.125× |

- **Purpose:** Tests whether the 2-band ratio is robust to scattering changes.
- **What it validates:** Since both OD450 and OD517 are affected by scattering path length, their *difference* should partially cancel scattering effects. A scattering-invariant index would show consistent BI at equal [Bili] across Lipofundin levels.
- **Success criterion:** BI at equal [Bili] varies by <30% across Lipofundin levels.

### 2.3 Total Calibration Sample Budget

| Series | N | Cumulative |
|--------|---|-----------|
| Core replicate A1–A6 | 6 | 6 |
| Variable Hb (H1–H8) | 8 | 14 |
| Variable scattering (L1–L9) | 9 | 23 |

The 23-sample dataset provides:
- **6 training points** for the basic α, β fit (A1–A6 original for backward compatibility, or any 6-point subset)
- **6 hold-out points** (core replicate) for reproducibility assessment
- **8 points** for Hb correction validation
- **9 points** for scattering robustness

This gives a **17-point independent validation set** against a 6-point calibration, which is sufficient for meaningful LOOCV.

---

## 3. Validation Strategy

### 3.1 Metrics

#### Primary metrics (calibration quality)

| Metric | Symbol | Target | Interpretation |
|--------|--------|--------|----------------|
| In-sample R² | R²_in | — | Diagnostic only; should be reported alongside LOO |
| Leave-one-out R² | R²_LOO | > 0.5 | Must be positive — confirms calibration generalizes within the domain |
| Hold-out RMSE | RMSE_hold | < 30% of [Bili] range | On the core replicate series |
| Hold-out MAE at low [Bili] | MAE_low | < 50% of true | At A5–A6, where Hb dominates |

#### Secondary metrics (Hb correction)

| Metric | Symbol | Target |
|--------|--------|--------|
| Hb-corrected BI consistency | CV(BI_corrected at equal [Bili]) | < 20% across Hb levels |
| k stability | |k_empirical| from 100 µM Hb data | within ±30% of k from 50/200 µM Hb data |

#### Tertiary metrics (scattering robustness)

| Metric | Symbol | Target |
|--------|--------|--------|
| Scattering sensitivity | CV(BI at equal [Bili] across Lipofundin levels) | < 30% |

### 3.2 Validation Procedure

```
For each validation approach:
  1. Fit calibration (α, β, optionally k) on TRAINING set only.
  2. Apply to HELD-OUT set → predicted log₁₀([Bili]).
  3. Compute RMSE, MAE, R² vs ground truth.
  4. Bland-Altman plot (predicted − true vs. mean) for bias assessment.
  5. Report both relative error (%) and absolute error (µM).
```

### 3.3 Statistical Treatment for Small N

With 23 total samples (6 training, 17 hold-out):

- **Bootstrapped confidence intervals:** 1000 bootstrap resamples of the training set, refit α/β each time → 95% CI for predicted [Bili] at each validation point.
- **Prediction intervals:** Report `[Bili]_predicted ± 2×σ_prediction` where σ_prediction includes both calibration uncertainty and hold-out residual variance.
- **Bayesian approach (optional):** Weak priors on α (half-normal, σ=0.05), β (normal, σ=0.01) → posterior predictive intervals. This naturally handles the small-N uncertainty.

---

## 4. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Calibration does not transfer** to replicate A1–A6 session (α, β shift significantly) | Medium | High — index is session-dependent, not generalizable | Investigate root cause: illumination stability, Lipofundin batch variation, camera drift. Add per-session reference phantom for normalization. |
| **Hb correction factor `k` is unstable** across Hb levels | High | Medium — corrected index still has Hb bias | Cap `k` to empirically bounded range [0, 0.1]. If k varies >50% across Hb levels, report uncorrected index as primary. |
| **Scattering dependence is large** (>50% variation across Lipofundin levels) | Medium | Medium — index is not scattering-invariant | Report the index as valid only within a scattering range (±50% of baseline). Add a scattering normalization step using NIR bands. |
| **LOO R² remains negative** even with 23 samples | Low | High — calibration is fundamentally unreliable | Re-evaluate whether the 2-band index should be used at all for concentration estimation. Fall back to ordinal/rank claims only. |
| **Camera non-linearity at low R450** compresses dynamic range | Medium | Medium — [Bili] overestimated at high concentrations | Characterize camera response with neutral density filters; apply gamma correction before OD computation. |
| **Bilirubin oxidation in phantoms** shifts absorption peak over time | Medium | Medium — calibration drifts during imaging session | Add antioxidant (ascorbic acid 1 mg/mL), prepare fresh for each session, measure absorbance before/after imaging. |

---

## 5. What Claims Are Scientifically Defensible

### 5.1 After 6-point in-sample calibration (current state)

✅ **Defensible claims:**
- "The bilirubin index OD450−OD517 is monotonically related to bilirubin concentration in the A1–A6 Lipofundin + Hb phantom series."
- "Higher index values indicate higher bilirubin within the 8–270 µM range when Hb is constant at 100 µM."
- "The index directionally tracks the known bilirubin halving trend."
- "The index is a dimensionless diagnostic, not an absolute bilirubin concentration."

❌ **NOT defensible:**
- "The index measures bilirubin concentration in µM."
- "The index is calibrated and accurate to within X µM."
- "The index works for variable Hb."
- "The index generalizes beyond the A1–A6 phantom series."
- "The calibration R² of 0.942 means the model explains 94% of variance" (this is in-sample, not cross-validated).

### 5.2 After 23-point calibration with Hb and scattering variation

✅ **Additionally defensible:**
- "The Hb-corrected bilirubin index OD450−OD517−k·OD671 estimates bilirubin concentration with ±X µM RMSE in the 8–270 µM range for Hb levels of 50–200 µM in Lipofundin-based phantoms."
- "The index is robust to ±2× variation in Lipofundin scattering."
- "The calibration transfers across phantom preparation sessions with ±Y% reproducibility."
- "Leave-one-out cross-validation on N=23 samples gives R² = Z."

❌ **Still NOT defensible (without further work):**
- "The index is valid for in vivo measurements."
- "The index works for Hb outside the 50–200 µM range."
- "The index is a replacement for spectral unmixing."
- "The index is a medical device or diagnostic."

### 5.3 After independent validation on separate phantom dataset

✅ **Additionally defensible:**
- "The bilirubin index calibration generalizes to independently prepared phantoms from a different batch/session with RMSE < X µM."
- "The calibration is session-independent within specified uncertainty bounds."

---

## 6. Implementation Sequence

### Phase 1: Strengthen existing calibration infrastructure (no new data needed)

**Files:** `scripts/bilirubin_index_report.py`, `research-reports/`

1. **Add bootstrapped confidence intervals** to the calibration report.
   - Bootstrap resample the 6 A1–A6 median BI values 1000×, refit α/β each time.
   - Report 95% CI for α, β, and for predicted [Bili] at each phantom concentration.
   - Output: `research-reports/bilirubin_calibration_bootstrap.json`

2. **Add prediction intervals** (not just LOO point predictions).
   - Compute σ_prediction = sqrt(σ²_residual + σ²_calibration).
   - Report ±2σ for each predicted point.

3. **Add a Bland-Altman-style diagnostic** plot.
   - Difference (predicted − true) vs. mean for the LOO predictions.

4. **Add log-linear calibration function to `app/core/processing.py`**:
   ```python
   def calibrate_bilirubin_index(
       bi_values: np.ndarray,       # (N,) median or pixel-wise BI values
       bili_truth_uM: np.ndarray,   # (N,) known bilirubin concentrations
       method: str = "log_linear",
   ) -> dict:
       """Fit BI = α·log₁₀([Bili]) + β and return (α, β, R², residuals)."""
   ```
   This makes the calibration reusable from GUI, CLI, and tests.

**Effort:** ~2 hours. **Done when:** bootstrap report exists, calibration function is tested.

### Phase 2: Design and prepare the forward calibration phantom protocol

**New file:** `docs/calibration_phantom_protocol.md`

1. Document the existing A1–A6 preparation protocol exactly (if available).
2. Define the 23-sample phantom matrix (3 series × variable Hb/scattering).
3. Specify materials, concentrations, mixing order, stabilization requirements.
4. Define imaging protocol: dark/ref acquisition, exposure times, ambient light control.
5. Define quality checks: absorbance verification before/after imaging, oxidation monitoring.

**Effort:** ~2 hours (physical phantom preparation time NOT included). **Done when:** protocol document is reviewed and approved.

### Phase 3: Calibration analysis on expanded dataset

**Files:** `scripts/bilirubin_index_report.py` (extend)

1. Extend the script to accept a calibration/training mask so α/β are fit on training data only.
2. Add Hb-correction factor `k` fitting:
   - Fit `k` by minimizing CV of corrected BI across Hb levels at each fixed [Bili].
   - Report `k_empirical` with bootstrap CI.
3. Add scattering sensitivity analysis:
   - Compute CV of BI at each [Bili] across Lipofundin levels.
4. Generate a calibration summary report with all metrics above.

**Effort:** ~3 hours. **Done when:** calibration report on expanded dataset passes all primary metric targets.

### Phase 4: GUI calibration feedback

**Files:** `app/gui_qt/main_window.py`, `app/gui_qt/panels/inspector_panel.py`

Only after Phase 3 produces a positive-LOO-R² calibration:

1. Add calibration coefficients (α, β, k) as configurable parameters in the GUI toolbar (or load from a calibration file).
2. In the Pixel Inspector, show approximate µM alongside the raw index:
   ```
   Bilirubin Index (OD450−OD517): 0.0245
   est. [Bili]: ~68 µM (calibrated on A1–A6, Hb=100 µM)
   ```
3. The "est." prefix and calibration source annotation prevent overclaiming.

**Effort:** ~2 hours. **Done when:** pixel inspector shows "est. [Bili]" with calibration caveat.

### Phase 5: External validation report

**New file:** `research-reports/bilirubin-index-validation.md`

After all phantom data is collected and analyzed:

1. Comprehensive validation tables and plots.
2. Calibration curve with prediction bands.
3. Bland-Altman analysis.
4. Statement of validated range and limitations.
5. Comparison to full KM unmixing (from `scripts/km_sensitivity_scan.py`).

**Effort:** ~1 hour to write, after data exists. **Done when:** report is peer-reviewed internally.

---

## 7. Non-Goals (explicitly out of scope for this calibration plan)

- **In vivo validation** — requires IRB, clinical partnership, completely different risk profile.
- **Multi-center reproducibility** — requires multiple labs with identical phantoms/imaging.
- **Absolute [Bili] without phantom calibration** — the index is inherently ratiometric, not first-principles.
- **Replacing spectral unmixing** — the index uses 2 of 8 bands; full unmixing provides independent Hb + StO2 information the index discards.
- **KM solver improvement** — separate task; the 2-band index is an orthogonal diagnostic, not a KM fix.
- **Physics-based calibration from extinction coefficients** — effective path length ratio between blue and NIR bands is ~800×, making direct extinction-based calibration impractical.

---

## 8. Decision Gates

| Gate | Condition | Go-forward if | Stop/reconsider if |
|------|-----------|--------------|-------------------|
| G1 | Phase 1 bootstrap CI width | 95% CI for α spans < ±30% of estimate | CI spans > ±50% → 6-point calibration cannot constrain α |
| G2 | Core replicate LOO R² | R²_LOO > 0 | R²_LOO ≤ 0 → calibration fundamentally does not generalize; even directionally |
| G3 | Hb correction CV | CV(BI_corrected) < 20% across Hb levels | CV > 20% → Hb correction is insufficient; index is Hb-dependent |
| G4 | Scattering CV | CV(BI) < 30% across Lipofundin levels | CV > 30% → index requires scattering normalization |
| G5 | Hold-out RMSE | RMSE < 30% of [Bili] range on replicate series | RMSE > 30% → calibration is not session-reproducible |

---

## 9. Files Reference

| File | Change |
|------|--------|
| `app/core/processing.py` | Add `calibrate_bilirubin_index()` |
| `scripts/bilirubin_index_report.py` | Bootstrap CIs, prediction intervals, training/hold-out split, Hb correction fitting, scattering sensitivity |
| `docs/calibration_phantom_protocol.md` | New — phantom preparation and imaging protocol |
| `research-reports/bilirubin_calibration_bootstrap.json` | New — bootstrap results from Phase 1 |
| `research-reports/bilirubin-index-validation.md` | New — comprehensive validation report (Phase 5) |
| `app/gui_qt/main_window.py` | Calibration coefficient entry, pixel inspector "est. [Bili]" (Phase 4) |
| `tests/test_bilirubin_index.py` | Extend with calibration function tests |

**No changes needed:**
- `app/gui_qt/panels/maps_panel.py` — derived map rendering is already generic.
- `app/core/export.py` — already handles all derived keys.
- `data/chromophores/` — existing spectra unchanged.

---

## 10. Summary

The forward calibration plan advances the bilirubin index from a 6-point in-sample diagnostic (R² = 0.942 in-sample, negative LOO R²) to a 23-point calibrated index with cross-validated performance metrics and known Hb/scattering robustness. The key deliverables are:

1. **Bootstrap uncertainty quantification** on existing data (no new phantoms).
2. **Expanded phantom series** (core replicate + variable Hb + variable scattering, 23 samples total).
3. **Hold-out validation** with positive LOO R² as the gating criterion.
4. **Calibration function** in `processing.py` for GUI reuse.
5. **Defensible claims** limited to the validated phantom domain: Lipofundin phantoms, Hb 50–200 µM, [Bili] 8–270 µM.

Until independent validation (Phase 3) is complete, the index should continue to be presented as a dimensionless diagnostic with ordinal interpretation only — never as "bilirubin concentration in µM."
