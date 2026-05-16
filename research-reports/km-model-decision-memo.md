# Decision Memo: Classic KM Remission vs. Nonlinear Yudovsky KM-Style Model

**Date:** 2026-05-16  
**Author:** Planning subagent  
**Status:** Recommendation — implement classic KM now, defer Yudovsky.

---

## 1. Summary of Recommendation

**Implement the classic KM remission solver now. Defer the Yudovsky nonlinear model.** The classic KM approach is fit-for-purpose as a first-order diagnostic tool on the current 8-band LED data, can be delivered as a minimal additive change following the existing `mu_a` solver pattern, and produces results that will inform whether the Yudovsky upgrade is warranted. The Yudovsky model is physically superior but introduces per-pixel nonlinear optimization, requires MC-calibrated hyperparameters, and would not overcome the fundamental limitation of only 2 blue/green LED bands for Hb/bilirubin separation.

---

## 2. What the Two Models Are

### 2.1 Classic KM Remission (staged now)

**Forward path per pixel:**
```
R_measured(λ)  →  F(R) = (1−R)²/(2R)  →  μa_KM(λ) = F(R)·μs′(λ)/2  →  NNLS: μa_KM ≈ Σ c_k·ε_k
```

- Two-stage: reflectance → absorption → chromophore fit (linear NNLS per pixel).
- Structurally identical to the existing `mu_a` solver — only the conversion formula differs.
- Reuses `build_absorption_matrix()`, `build_fixed_scattering_profile()`, `scipy.optimize.nnls`.
- Code footprint: ~80 new lines in `processing.py`, ~30 lines in `main_window.py`.

### 2.2 Yudovsky (2009, erratum 2015) — deferred

**Forward path per pixel:**
```
w₀ = μs′/(μa + μs′)
R_model = M₁ + M₂·exp(M₃·w₀^M₄) + M₅/(1.02 − M₆)

Inverse: min_{c_Hb, c_Bil, s₀} Σ_λ [R_measured − R_model(λ; c_Hb, c_Bil, s₀)]²
```

- Single-stage nonlinear optimization per pixel (`scipy.optimize.least_squares`).
- 6 MC-fitted hyperparameters (M₁–M₆) that depend on refractive index.
- Physically validated: NRMSE ~0.01 against MC simulations (Bahl et al. 2024).
- Requires fitting 3–4 parameters per pixel via iterative optimization — significantly heavier compute and more code.

---

## 3. Evidence Assessment

### 3.1 Arguments for classic KM now

| Factor | Evidence |
|--------|----------|
| **Validated for these chromophores** | Seroul et al. (2016) and Doi et al. (2004) directly used KM to extract Hb, HbO₂, and bilirubin from skin reflectance. Reported 90–95% chromophore concentration accuracy (blb-alternatives.md §1). |
| **Minimal risk to codebase** | The KM solver is additive — follows the `mu_a` solver pattern exactly (two-stage: convert → NNLS). No existing solver signatures change. The implementation plan in `km-staged-implementation-plan.md` already maps this out. |
| **Diagnostic value even if approximate** | Even if absolute accuracy is poor, classic KM answers critical questions: (a) is the bilirubin trend directional, (b) what scale factor relates fitted values to µM, (c) how sensitive are results to the scattering prior? These answers guide whether a more complex model is justified. |
| **KM→RTE conversion is reasonably accurate** | blb-alternatives.md §1: KM-to-RTE coefficient conversion validated with ~10% reflectance accuracy. The corrected KM formula (using 4R denominator) avoids the factor-of-2 overestimation noted in km-equations-implementation.md §1. |
| **8-band data limits any model** | The DNG phantom data has only 450 and 517 nm in the blue/green region. With only 2 bands where both Hb and bilirubin absorb, no model — however physically accurate — can fully separate the two chromophores. The Yudovsky model improves the forward reflectance mapping but cannot create information that isn't in the data. |

### 3.2 Arguments for deferring Yudovsky

| Factor | Evidence |
|--------|----------|
| **No improvement for spectral overlap** | Murphy (2022) found significant Hb/bilirubin cross-talk even with a LUT-based model (more sophisticated than either KM variant). The root cause is spectral overlap in the 400–500 nm region, not forward-model inaccuracy. Yudovsky uses the same linear absorption additivity assumption (μa = Σ c_i·ε_i); it only upgrades the reflectance mapping. |
| **The 8-band data lacks the discriminating wavelengths** | The literature identifies 470 nm (BR/Hb extinction ratio maximum) and 525–530 nm (Hb isosbestic, BR ≈ 0) as the optimal pair for Hb/bilirubin separation (lipofundin-hb-bilirubin-phantoms.md §6). Neither band is present in the DNG LED set. The Yudovsky model cannot compensate for missing spectral information. |
| **Per-pixel nonlinear optimization cost** | Yudovsky requires `least_squares` per pixel. On a 50×50 image = 2500 optimizations × 8 bands × 3 parameters. The staged plan already identifies this as a risk and proposes fitting s₀ per-sample first. But even with 2 parameters per pixel, it's substantially more code and testing surface. |
| **Hyperparameter portability not validated for Lipofundin** | The M₁–M₆ values for n=1.33 (water) were fitted to MC simulations (km-equations-implementation.md §1). Bahl et al. (2024) validated them on gelatin + Intralipid phantoms but not on Lipofundin specifically. While Lipofundin ≈ Intralipid within 5% (lipofundin-hb-bilirubin-phantoms.md §1), this uncertainty cascades. |
| **Extinction coefficient medium dependence** | Bahl et al. (2024) found that dye extinction coefficients shifted by 5–10 nm when measured in gelatin vs. solution. The Agati extinction spectra in the repo may already be shifted relative to the DNG phantom medium. This is a calibration problem that affects both models equally; upgrading the forward model won't fix it. |
| **Classic KM provides the baseline to justify the upgrade** | If classic KM shows reasonable bilirubin monotonicity but poor absolute accuracy, that justifies spending the effort on Yudovsky. If classic KM shows no bilirubin trend at all, the problem is likely in the data (wavelength coverage, extinction spectra, scattering prior), not in the forward model choice. |

### 3.3 What the literature says about when to upgrade

- **Palmer & Ramanujam (2006):** MC-based inverse model achieved 3% error on single-chromophore Hb phantoms but 12% on Nigrosin. Multi-chromophore cross-talk dominated the error budget.
- **Bahl et al. (2024):** Yudovsky model achieved median APE ~1.4% for 2-dye configurations but degraded severely with 3 dyes. Their key lesson: "extinction coefficients measured in the actual phantom medium are essential."
- **Murphy (2022):** "Future work should shift wavelength bounds to better discriminate bilirubin, possibly by including the bilirubin-specific 460–490 nm region with higher weight."

**The consistent pattern across studies:** forward-model sophistication is not the binding constraint for multi-chromophore liquid phantoms in the visible range. Spectral coverage, extinction coefficient accuracy, and scattering prior calibration dominate.

---

## 4. Decision

### What to implement now

1. **Classic KM remission solver** as specified in `features/kubelka_munk_solver.md` and detailed in `research-reports/km-staged-implementation-plan.md`:
   - `_reflectance_to_mu_a_km()` — the corrected remission formula using 4R denominator.
   - `solve_unmixing_km()` — two-stage (reflectance → μa → NNLS chromophore fit).
   - GUI integration: add `"km"` to solver combo, wire scattering toolbar, disable background.
   - Unit tests: synthetic recovery, clipping behavior, round-trip consistency.

2. **Validation on DNG phantom series A1–A6** using `hb_agat_extr` and `bili_agat`:
   - Soft acceptance: bilirubin monotonically decreasing, Hb flatter than bilirubin, no NaN/inf.
   - Do not gate on absolute µM accuracy — calibration scale is not yet established.

### What to defer

1. **Yudovsky (2009/2015) nonlinear forward model** as a full solver.
2. **Per-pixel `scipy.optimize.least_squares`** optimization.
3. **Fitting scattering amplitude s₀ per-pixel** (sample-level fitting is acceptable for diagnostic exploration).
4. **Fitting scattering power b** (keep fixed at 1.0).

### What the deferred work should look like (for later reference)

When Yudovsky is implemented later, it should be:
- A separate solver method (e.g., `"km_yudovsky"` or `"km_nl"`) — not a replacement for the classic solver.
- Have its own forward model function using the 6-parameter erratum formula with n=1.33.
- Fit per-pixel via `least_squares` with bounds.
- Have its own validation test comparing results against the classic KM baseline.

---

## 5. Criteria for Triggering the Yudovsky Upgrade

Upgrade to Yudovsky **only if all of the following are met:**

| # | Criterion | Rationale |
|---|-----------|-----------|
| C1 | Classic KM produces directionally correct bilirubin trends (monotonically decreasing A1→A6) | Confirms the data and extinction spectra are usable. If KM fails directionally, the problem is not the forward model. |
| C2 | The dominant error source is forward-model mismatch, not spectral overlap or extinction calibration | Diagnose by: if residual spectra show systematic shape errors (e.g., consistently overestimating reflectance at 450 nm), that suggests forward-model error. If residuals are flat or noise-like but bilirubin still fails, the problem is identifiability. |
| C3 | Additional wavelength bands (≥470 nm, ≥525 nm) become available, OR full-spectrometer data replaces the 8-LED set | The Yudovsky model improves reflectance prediction accuracy but cannot create spectral information. New data with better bilirubin/Hb discrimination would make the upgrade worthwhile. |
| C4 | Absolute concentration accuracy (±20% on µM) is a requirement | Classic KM with a calibration factor may achieve trend accuracy. If quantitative accuracy is needed, the Yudovsky + MC calibration path is the right next step. |
| C5 | Extinction coefficients are measured or validated in the actual phantom medium | Per Bahl et al. (2024), using literature ε values without medium-specific validation is a bigger error source than the forward model choice. Measure ε in the phantom solvent system first. |

**Conversely, the following would NOT justify upgrading to Yudovsky:**

- High RMSE alone (could be driven by scattering prior error, which a sample-level s₀ scan can diagnose).
- Poor bilirubin recovery at low concentrations (A5–A6 at <17 µM) — this is a signal-to-noise and spectral overlap problem, likely endemic to the 8-band setup regardless of forward model.
- Hb constancy failure (could be a scattering prior error, fixable by adjusting μs′(500) or the power-law exponent b).

---

## 6. Risks of This Decision

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Classic KM is too approximate and validation fails entirely | Medium | Low — the implementation effort is small (~200 lines), and the diagnostic information from a failed validation is still valuable | If KM fails directionally, pivot to investigating the data/scattering prior before considering Yudovsky |
| Time pressure forces adoption of classic KM results as final, skipping the Yudovsky upgrade that would have been more accurate | Low | Medium — would produce systematically biased concentration estimates | Gate any publication or clinical conclusions on C4 (absolute accuracy requirement) |
| Classic KM works well enough that the Yudovsky upgrade is never prioritized | Medium | Low — if classic KM meets needs, the upgrade wasn't needed | Acceptable outcome; document the known limitations |
| The factor-of-2 KM error (noted in km-equations-implementation.md §1) is mishandled in implementation | Low | Medium — would produce incorrect absorption values | The current implementation plan uses F(R)·S/2 = (1−R)²·S/(4R), which is the corrected form. Verify in code review. |

---

## 7. References

All sources cited are from the existing research reports in `research-reports/`:

- **km-equations-implementation.md** — Yudovsky model details, absorption/scattering models, inverse formulation, Murphy/Bahl validation results.
- **km-staged-implementation-plan.md** — Currently staged classic KM implementation plan (5 stages).
- **km-implementation-context.md** — Codebase map, integration points, solver architecture.
- **blb-alternatives.md** — KM validation history (Seroul, Doi), IAD/MC/PLS alternatives, method comparison table.
- **lipofundin-hb-bilirubin-phantoms.md** — Phantom materials, spectral overlap analysis, wavelength selection strategies.
- **diffusion-models.md** — Diffusion/δ-P1 models, Farrell-Patterson, validity regimes.
- **features/kubelka_munk_solver.md** — Feature specification with physical model and validation plan.
- **features/kubelka_munk_implementation_plan.md** — Decision document staging classic KM first, Yudovsky deferred.
