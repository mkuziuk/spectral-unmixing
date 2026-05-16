# KM Next-Step Decision Plan

**Date:** 2026-05-16
**Status:** Decision framework — the sensitivity scan has completed; this document maps the three possible outcomes to concrete next actions, validation gates, and implementation priorities.

---

## Scan Outcome Summary

The full sensitivity scan (`scripts/km_sensitivity_scan.py`) tested:

| Dimension | Range | Points |
|-----------|-------|--------|
| Effective μs′(500) | 0.5 – 240 cm⁻¹ (log-spaced) | 20 |
| Power-law exponent b | 0.1 – 3.0 (linear) | 15 |
| Calibration factor K | 0.01 – 10.0 (log-spaced) | 30 |
| Band subsets | 2band_blue, 4band_vis, 8band_full | 3 |
| **Total parameter combinations** | | **990** |

The scan produced `research-reports/km_sensitivity_quick.csv` (quick 225-row version) and the full `km_sensitivity_results.csv`.

### Actual outcome: Branch A — NO bilirubin recovered

**Evidence:** In every one of the 990 parameter combinations, `bili_positive_a1 = False` — bilirubin median is identically zero for A1 (and all other phantoms). The composite score never exceeds ~1.92, which is the Hb-constancy contribution alone (CoV ≈ 8%, monotonicity trivially 5/5 with all zeros). The calibration factor scan (K from 0.01 to 10, spanning three orders of magnitude) fails identically to the scattering scan.

**Model-free sanity check:** The R₄₅₀/R₅₁₇ reflectance ratio is monotonic across A1–A6, confirming that bilirubin IS present in the raw data — the reflectance changes as bilirubin concentration decreases. This means the problem is **spectral identifiability within the solver**, not an absence of bilirubin signal.

---

## Branch A: Full Scan Recovers No Bilirubin (ACTUAL OUTCOME)

### Root-Cause Assessment

The NNLS solver fits `A @ x ≈ μa_KM`. With only two chromophore columns (`hb_agat_extr`, `bili_agat`), the solver must decide how to allocate the measured μa between them. Zero bilirubin occurs when:

1. **Hb alone explains μa_KM adequately.** The Hb spectrum (available at all 8 bands) can approximate the combined Hb+bilirubin signal with low residual, leaving no "room" for bilirubin to reduce the residual further.
2. **The bilirubin column adds correlated, not orthogonal, information.** At 450 and 517 nm (the only two bands with positive bili extinction), the Hb:bili extinction ratios are different (1.73 vs 4.81), so the two columns are not perfectly collinear. But with only 2 discriminating bands out of 8, and Hb having signal at all 8, NNLS sees Hb as the "cheaper" way to fit the NIR bands.
3. **Extinction-scale mismatch compounds the problem.** The measured μa_KM is ~3–8× smaller than predicted from Agati ε × ground-truth concentrations (§2.2 of km-phantom-validation-context.md). Even with K scanning 0.01–10, the relative Hb:bili ratio within each band is fixed by the Agati spectra — scaling both equally can't change the attribution.

### Decision Gates

Before committing to any next step, verify:

| Gate | Check | Pass If |
|------|-------|---------|
| G1 | Bilirubin signal exists in raw data | R₄₅₀/R₅₁₇ ratio trend is monotonic A1→A6 | **PASSED** (confirmed by scan script) |
| G2 | NNLS is converging normally | Hb concentrations are sane (not NaN, not negative) | **PASSED** (Hb ~40–50 µM, finite, coherent) |
| G3 | Absorption matrix is well-formed | Condition number < 200, no all-zero columns | Should verify |
| G4 | The bilirubin column isn't accidentally all-zero | `np.any(A[:, bili_idx] > 0)` | Should verify (clip_negative_extinction=True should leave 450/517 nm positive) |
| G5 | Reflectance values are in valid range | No saturation at R=0 or R=1 for any A1 pixel at 450/517 nm | Should verify |

If any gate G3–G5 fails, the problem is a **pipeline bug**, not a model limitation — fix the bug first.

### Implementation Options (ordered by priority / effort ratio)

#### A1. VERIFY: Model-Free Bilirubin Trend Quantification (effort: low, value: high)

**What:** Quantify the bilirubin signal that is already visible in the reflectance data without any solver.

**How:**
- Compute R₄₅₀/R₅₁₇ median per phantom A1–A6.
- Compute OD₄₅₀ − OD₅₁₇ (differential OD, cancels scattering to first order).
- Fit a simple log-linear model: `log₂(bili_truth) ~ α × (OD₄₅₀ − OD₅₁₇) + β`.
- Report the correlation and slope.

**Files:** `scripts/km_model_free_check.py` (new diagnostic script)

**Gate:** If the correlation is strong (r² > 0.8), bilirubin is quantitatively recoverable from the data — the NNLS solver just can't find it. If the correlation is weak (r² < 0.3), the bilirubin signal is at the noise floor.

**Priority:** **Immediate — do this before any implementation work.** This determines whether the path forward is a solver fix or a data-acquisition problem.

#### A2. JOINT FIT: Multi-Phantom Constrained Solver (effort: medium, value: high)

**What:** Instead of fitting each phantom independently with NNLS, jointly fit all 6 phantoms with structural constraints: Hb shared across samples, bilirubin constrained to be monotonic.

**Why:** The independent per-phantom NNLS has no "knowledge" that Hb is constant or that bilirubin should decrease. Joint fitting imposes the known experimental design as a prior, which is legitimate — the phantoms were designed this way.

**Implementation sketch:**
```python
# For A1..A6, minimize:
#   Σᵢ || A @ xᵢ − μaᵢ ||²
# subject to:
#   xᵢ[h] = xⱼ[h]  for all i,j  (Hb constant)
#   x₁[b] ≥ x₂[b] ≥ … ≥ x₆[b] ≥ 0  (bili monotonic)
#   xᵢ ≥ 0
```
This is a linearly constrained least-squares problem solvable with `scipy.optimize.lsq_linear`.

**Files:** New function `solve_unmixing_km_joint()` in `app/core/processing.py` or a standalone script.

**Validation:** If joint fitting recovers a directional bilirubin trend where independent NNLS cannot, it proves the data contains bilirubin information that is only extractable with structural priors. If joint fitting also fails, the identifiability problem is deeper.

**Gate:** Only proceed if A1 confirms bilirubin signal exists.

**Priority:** **High — do after A1 if A1 shows strong signal.**

#### A3. SYNTHETIC-BAND TEST: Would Better Wavelengths Help? (effort: low, value: high)

**What:** Test whether interpolating reflectance at the optimal discriminating wavelengths (470 nm and 530 nm) from the existing 450 and 517 nm bands would enable bilirubin recovery. This answers: "if we had better hardware, would the solver work?"

**How:**
1. Interpolate reflectance at 470 nm and 530 nm from 450 and 517 nm (linear in wavelength, or spline if justified).
2. Build absorption matrix at [470, 530] nm.
3. Run NNLS on the 2-band interpolated data.
4. Check bilirubin monotonicity.

**Files:** `scripts/km_synthetic_band_test.py` (new diagnostic script)

**Gate:** If synthetic-band NNLS shows bilirubin monotonicity, the problem is the LED wavelength set, and acquiring data at 470/530 nm is the path forward. If not, the problem is deeper (extinction spectra, phantom medium effects).

**Priority:** **High — very quick to implement, answers the "new hardware?" question.**

#### A4. LIPOFUNDIN ABSORPTION: Add Third Chromophore (effort: medium, value: medium)

**What:** Add a Lipofundin absorption spectrum as a third chromophore column to the absorption matrix.

**Why:** Pitfall 3 in `km-phantom-validation-context.md` notes that the measured μa ratio at 450/517 nm (1.26–1.38) is below the Hb-only ratio (1.73). This is physically impossible with just Hb+bili. Adding a third absorber with a low 450/517 ratio (e.g., Lipofundin's intrinsic absorption, or a generic "background" with flat or blue-weighted absorption) would allow the solver to attribute the ratio discrepancy to the third component, freeing Hb and bili to explain the remaining signal.

**Requirements:**
- Obtain Lipofundin absorption spectrum (literature data or measure).
- Or use a heuristic: add a constant-offset column (1.0 at all bands) representing wavelength-independent loss.

**Files:** `data/chromophores/lipofundin_absorption.csv` (new), modify matrix build in validation.

**Gate:** If adding a reasonable third absorber changes the bilirubin attribution from zero to monotonic, it's strong evidence that unmodeled absorption was biasing the NNLS fit.

**Priority:** **Medium — only if A1 confirms signal and A2/A3 don't resolve.**

#### A5. ALTERNATIVE SOLVER: Ridge / LASSO / Elastic Net (effort: low–medium, value: medium)

**What:** Replace NNLS with regularized least squares. A small L2 penalty (ridge) can break collinearity-induced zeroing.

**Why:** NNLS is an active-set method that tends to produce sparse solutions (components driven exactly to zero). With correlated columns and noise, NNLS may zero out bilirubin even when it should have a small positive value. Ridge regression (`scipy.optimize.lsq_linear` with bounds) or non-negative LASSO would shrink rather than eliminate.

**Implementation:**
```python
from scipy.optimize import lsq_linear
x, _ = lsq_linear(A[valid], mu_a_vec[valid], bounds=(0, np.inf))
```
with no regularization parameter needed for bounds-only non-negative LS. This is essentially NNLS without the active-set sparsity bias — worth testing as a 5-minute change.

**Files:** Modify `solve_unmixing_km` to use `lsq_linear` instead of `nnls` (or add as a `solver="ridge"` option).

**Priority:** **Low — tiny change, but NNLS vs bounds-LS differences are usually subtle.**

#### A6. EXTINCTION SPECTRA RE-EVALUATION (effort: high, value: high if spectra are wrong)

**What:** Verify that the Agati extinction coefficients are correct for the phantom medium. Bilirubin extinction depends on solvent (chloroform vs. albumin-bound vs. alkaline aqueous) and Hb extinction depends on oxygenation state. If the stored spectra don't match what's in the cuvette, no solver will work.

**How:**
- Confirm which Agati publication the CSV data comes from.
- Check if the phantom bilirubin was albumin-solubilized (peak at 460 nm, ε ≈ 48,400) or dissolved in alkaline buffer (peak at 440 nm, ε ≈ 63,500).
- Measure actual phantom absorption in a spectrophotometer if possible.
- Compare with literature spectra from Prahl (OMLC), Gratzer, or Zijlstra.

**Files:** Investigate `data/chromophores/bili_agat.csv` and `data/chromophores/hb_agat_extr.csv` provenance.

**Priority:** **High if A1–A3 all fail — extinction error is the most likely remaining cause.**

#### A7. ACCEPT LIMITATION: Scoped-Down Hb-Only Validation (effort: low, value: medium)

**What:** Accept that bilirubin cannot be recovered with the current setup and pivot to validating Hb quantification only. Hb constancy across A1–A6 is already excellent (CoV ~8%), which is a meaningful result.

**How:**
- Convert `test_km_phantom_validation.py` from exploratory to strict for Hb only.
- Add a calibration factor mapping recovered Hb to µM: `c_Hb_true = scale × c_Hb_fitted`.
- Document bilirubin limitation prominently in README, feature spec, and exports.
- Keep the KM solver in the app as a functional Hb quantification tool.

**Files:** `tests/test_km_phantom_validation.py`, `README.md`, `features/kubelka_munk_solver.md`

**Priority:** **Fallback — do this if A1–A6 all fail to recover bilirubin.**

### Recommended Action Sequence for Branch A

```
A1 (model-free check)
  │
  ├─ r² > 0.8 ──► A3 (synthetic band test)
  │                  │
  │                  ├─ bili recovered ──► new hardware needed; document
  │                  └─ bili still zero ─► A2 (joint fit)
  │                                          │
  │                                          ├─ bili recovered ──► implement joint solver
  │                                          └─ bili still zero ─► A4 (third chromophore)
  │                                                                   │
  │                                                                   ├─ works ──► add Lipofundin absorption
  │                                                                   └─ fails ──► A6 (extinction review)
  │
  └─ r² < 0.3 ──► A7 (Hb-only scoping) + A6 (extinction review in parallel)
```

**Do not proceed to A7 (accept limitation) until A1, A3, and A2 have been tried.** The data contains bilirubin signal (R450/R517 is monotonic) — it would be premature to give up on recovering it before testing whether a different solver structure can extract it.

---

## Branch B: Full Scan Recovers Monotonic but Scaled Bilirubin (HYPOTHETICAL)

If the scan had found parameter combinations where bilirubin is non-zero, monotonically decreasing, and Hb is approximately constant, but the absolute bilirubin values don't match ground-truth µM:

### Validation Gates

| Gate | Check | Pass If |
|------|-------|---------|
| G1 | Bilirubin is non-zero for A1 | `bili_median_A1 > 0` for at least one parameter combination |
| G2 | Bilirubin is monotonic | `bili_mono ≥ 4/5` consecutive decreasing pairs |
| G3 | Hb is approximately constant | `Hb_CoV < 0.20` |
| G4 | Parameters are physically plausible | 2 < μs′(500) < 100 cm⁻¹, 0.4 < b < 2.5 |
| G5 | Calibration factor is reasonable | 0.01 < K < 100 (not extreme) |

### Implementation Path for Branch B

#### B1. CALIBRATE: Global Scale Factor (effort: low, value: high)

**What:** Apply a single multiplicative calibration factor to map solver-native bilirubin concentrations to µM.

**How:**
- Compute `K_bili = bili_truth_A1 / bili_fitted_A1` from the best parameter combination.
- Verify that the same K maps A2–A6 to within ±30% of ground truth.
- If Hb also needs a different K, evaluate whether per-chromophore K factors are justified or whether the spectral shape mismatch is the root cause.

**Files:** New calibration section in `scripts/km_sensitivity_scan.py`, or a new `scripts/km_calibrate.py`.

**Gate:** If a single K maps all 6 bilirubin values to within ±50% of ground truth, the KM solver is directionally valid and needs only a calibration step. **Proceed to B3 (productionize).**

#### B2. REFINE: Per-Chromophore Calibration (effort: medium, value: medium)

**What:** Allow separate calibration factors `K_hb` and `K_bili`.

**Why:** The band-wise ratio mismatch (7.6× at 450 nm vs 3.3× at 517 nm) means Hb and bilirubin likely need different scale factors. This is physically plausible — extinction coefficients in different solvents have different absolute scales.

**Risk:** With only 6 data points (ground-truth pairs) and 2 calibration factors, the risk of overfitting is real. Cross-validate by fitting K on A1–A3 and testing on A4–A6.

**Gate:** Only proceed if B1 fails (single K is insufficient).

#### B3. PRODUCTIONIZE: Integrate Calibration into the Pipeline (effort: medium, value: high)

**What:** Make the KM solver production-ready with built-in calibration.

**How:**
1. Add `calibration_factors: dict[str, float]` to the KM configuration.
2. Apply per-chromophore calibration in `solve_unmixing_km` as a post-processing step (multiply recovered concentrations by calibration factors).
3. Add a calibration tab or configuration file for specifying factors.
4. Update documentation with calibration instructions.
5. Tighten `test_km_phantom_validation.py` assertions to enforce monotonicity, Hb constancy, and approximate halving ratios.

**Files:** `app/core/processing.py`, `app/gui_qt/main_window.py`, `tests/test_km_phantom_validation.py`, `README.md`

#### B4. MEASURE: Cross-Validation on Independent Phantom Set (effort: high, value: high)

**What:** Validate the calibrated KM solver on an independent phantom series (different Hb or bili concentrations, or different Lipofundin dilution).

**Why:** The A1–A6 series was used for calibration — performance on that dataset is optimistic. Independent validation is required before making clinical or publication claims.

**Gate:** Only possible if additional phantom data exists.

### Recommended Sequence for Branch B

```
B1 (single K) ──► B3 (productionize)
  │                  │
  └─ fails ──► B2 (per-chromophore K)
                  │
                  ├─ cross-validates ──► B3 (productionize with caveat)
                  └─ overfits ──► B4 (need independent data) or revisit spectral shape
```

---

## Branch C: Full Scan Finds Nonphysical Optima (HYPOTHETICAL)

If the scan found parameter combinations with high composite scores (bilirubin positive, monotonic, good Hb constancy) but the optimal parameters are physically implausible:

### Examples of Nonphysical Optima

| Symptom | Threshold | Interpretation |
|---------|-----------|----------------|
| μs′(500) at grid boundary | optimum at 0.5 or 240 cm⁻¹ | Solver exploiting degenerate scattering regime |
| Power-law b extreme | b < 0.1 or b > 3.0 | Scattering spectral shape is unphysical for lipid droplets |
| Calibration K extreme | K < 0.001 or K > 1000 | Extinction scale is being used as a free parameter |
| Hb varies wildly | Hb_CoV > 30% at optimum | Parameters trading Hb constancy for bili structure |
| Score still climbing at boundary | composite(max_param) > composite(second-to-max) | Optimum is outside scanned range |

### Decision Gates for Branch C

| Gate | Check | Action if Failed |
|------|-------|-----------------|
| G1 | Is the optimum within physically plausible bounds? | Extend grid to capture peak; re-evaluate |
| G2 | Does the optimum degrade gracefully away from the peak? | If sharp peak, suspect overfitting; if broad plateau, more credible |
| G3 | Do the A1–A6 per-sample Hb values form a flat line at the optimum? | If Hb varies systematically with bili, the parameters are absorbing cross-talk |
| G4 | Is the RMSE at optimum lower than the Hb-only baseline (all bili=0)? | If RMSE is worse but score is higher, the composite score is being gamed |

### Implementation Path for Branch C

#### C1. EXTEND GRID: Capture the True Optimum (effort: low)

**What:** If the optimum is at a boundary, extend the parameter range. If μs′(500) optimal at 240, test up to 1000. If b optimal at 3.0, test up to 5.0.

**Gate:** If the extended grid reveals a plateau (not a boundary spike), the nonphysical parameter may be a calibration proxy, not a degenerate solution.

#### C2. UNCOUPLE: Fit Scattering from Data (effort: high, value: high)

**What:** Instead of scanning a fixed scattering grid, fit μs′(500) and b from the phantom data itself using a model where all A1–A6 share the same scattering parameters but have different absorption.

**Why:** If the scan found bilirubin but at extreme scattering values, the true scattering of the phantoms may simply be outside the default range. Fitting scattering from the data would reveal the actual phantom optical properties.

**How:**
- Use the model: `μa_KM_i(λ) = c_Hb · ε_Hb(λ) + c_bili_i · ε_bili(λ)` for each phantom i, with Hb concentration shared.
- Fit `[c_Hb, c_bili_1..6, μs′(500), b]` jointly to minimize reflectance residual across all 6 phantoms.
- Compare fitted scattering with literature values for the known Lipofundin concentration.

**Files:** New script `scripts/km_fit_scattering.py` or joint optimization in processing.py.

**Gate:** If fitted scattering matches literature within ~30%, the nonphysical optima from the scan were artifacts of the grid search, not the model.

#### C3. DIAGNOSE: Check for Overfitting by Cross-Validation (effort: medium)

**What:** Split A1–A6 into training (A1, A3, A5) and test (A2, A4, A6). Find the best parameters on training and evaluate metrics on test.

**Gate:** If test performance is dramatically worse than training, the scan optimum is overfitting the specific phantom series rather than capturing physics.

#### C4. FALLBACK: Revert to Branch A Reasoning (effort: low)

**What:** If nonphysical optima are confirmed (boundary spike, poor cross-validation, Hb trade-off), treat the outcome as "no credible bilirubin recovery" and follow Branch A.

---

## Cross-Cutting Infrastructure Needs (All Branches)

These are worth implementing regardless of which branch materializes:

### 1. R₄₅₀/R₅₁₇ Trend Dashboard

A small diagnostic that runs before any solver and prints:

```
Model-free reflectance ratio R450/R517:
  A1: 0.XXX  A2: 0.XXX  ...  A6: 0.XXX
  Direction: monotonic INCREASE (consistent with decreasing bili)
  Dynamic range: X% change from A1 to A6
  Implied bilirubin detectability: [STRONG / MODERATE / WEAK / NONE]
```

This should be added to `test_km_phantom_validation.py` as a non-asserting diagnostic print.

### 2. Absorption Matrix Integrity Check

A function `validate_absorption_matrix(A, chromophore_names, wavelengths)` that asserts:
- No NaN/inf entries
- No all-zero columns (would make chromophore unrecoverable)
- Condition number reported
- Per-chromophore "information content" (sum of squared column entries per band group)

Already partially covered by `assert np.all(absorption_matrix >= 0.0)` in the validation test. Extend to cover condition number and column norms.

### 3. Unit-Aware Concentration Reporting

The current validation prints "µM" but the solver-native units are solver-dependent (M for LS/NNLS, µM after ×1e6 in the smoke test). Standardize:
- All internal solver outputs in **M** (consistent with extinction in cm⁻¹/M).
- All reports/prints in **µM** with explicit conversion.
- Add a `_to_uM()` helper that multiplies by 1e6.

### 4. KM Solver Logging

Add `logging` to `solve_unmixing_km` reporting:
- Number of pixels with valid reflectance bands
- Number of pixels with all bands invalid (concentration set to zero)
- Per-band mean μa_KM (for sanity checking against literature)

---

## Files That May Be Created or Modified

| File | Branch | Purpose |
|------|--------|---------|
| `scripts/km_model_free_check.py` | A | Quantify bilirubin signal in reflectance ratios without solver |
| `scripts/km_synthetic_band_test.py` | A | Test whether interpolated 470/530 nm bands enable recovery |
| `scripts/km_joint_fit.py` | A | Joint phantom fitting with Hb constancy + bili monotonicity constraints |
| `scripts/km_calibrate.py` | B | Fit calibration factors from scan results |
| `scripts/km_fit_scattering.py` | C | Fit scattering from phantom data |
| `app/core/processing.py` | A, B | `solve_unmixing_km_joint()` (A2), `lsq_linear` variant (A5), calibration support (B3) |
| `app/gui_qt/main_window.py` | B | Calibration UI if B3 is reached |
| `tests/test_km_phantom_validation.py` | A, B | Upgrade from smoke to strict assertions (if bilirubin recovered) |
| `data/chromophores/lipofundin_absorption.csv` | A | Third chromophore for A4 |
| `README.md` | All | Document KM capabilities and limitations |
| `features/kubelka_munk_implementation_plan.md` | All | Update with actual progress |

---

## Decision Authority

| Decision | Who Decides | When |
|----------|------------|------|
| Proceed with A1 (model-free check)? | **Immediate — no decision needed** | Now |
| Proceed with A2 (joint fit) after A1? | Implementer, if A1 shows r² > 0.5 | After A1 results |
| Proceed with A3 (synthetic bands)? | Implementer | Anytime; very low cost |
| Proceed with A7 (Hb-only scope)? | Project lead / supervisor | Only if A1–A6 all fail |
| Proceed to Branch B or C? | Not applicable — actual outcome is Branch A | — |
| Declare KM solver "done" and move on? | Project lead | After A7 or after successful A2/A4 implementation |

---

## Summary

The sensitivity scan definitively showed that **the classic KM + NNLS per-phantom solver cannot recover bilirubin from the current 8-band LED data with the current Agati extinction spectra, regardless of scattering or calibration parameters.** The reflectance ratio trend confirms bilirubin IS present in the raw data, but the NNLS solver cannot attribute the signal to bilirubin — Hb alone explains the measured μa_KM adequately.

The next step is **A1 (model-free check)** to quantify how much bilirubin signal exists, followed by **A3 (synthetic band test)** and **A2 (joint fit)** to determine whether the problem is the solver architecture or a fundamental data limitation. Only exhaust those diagnostics before considering A7 (accepting Hb-only scope).

The most likely resolution is either (a) the joint-fit approach extracts bilirubin that independent NNLS cannot, or (b) the 8-band LED set simply lacks the discriminating wavelengths (470 and 525–530 nm) needed for Hb/bilirubin separation, and new hardware is required.

---

*References: `km-sensitivity-analysis-plan.md`, `km-phantom-validation-context.md`, `km-model-decision-memo.md`, `km-postfix-review.md`, `lipofundin-hb-bilirubin-phantoms.md`, `km_sensitivity_quick.csv`.*
