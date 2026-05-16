# KM Post-Fix Review

**Date:** 2026-05-16
**Branch:** `feature/kubelka-munk-solver` (uncommitted working tree)
**Review scope:** Post-review fixes applied after `km-implementation-review.md`

---

## Summary

All three mitigations for the negative-bilirubin-extrapolation concern (H1) are in place and correct. No regressions introduced. API compatibility is preserved for all existing callers. The fix is sufficient for the immediate concern, though the fundamental data limitation (only 2 of 8 bands carry bilirubin signal) remains an input-data problem, not a code defect.

---

## Fix-by-fix assessment

### 1. `build_absorption_matrix` — `clip_negative_extinction` parameter

**Location:** `app/core/processing.py:594–629`

**Mechanism:** When `clip_negative_extinction=True`, the interpolated/extrapolated extinction coefficients for each chromophore are clipped to `[0, ∞)` before band integration, and the final matrix `E` is defensively clipped a second time.

**Assessment: Correct.** The two-level clipping is belt-and-suspenders:
- Level 1 (`np.clip(coeff, 0.0, None)` inside the double loop, line 623): catches per-chromophore extrapolation artifacts before the trapezoidal integration. Since the LED profile `phi >= 0`, a non-negative integrand guarantees non-negative band integrals.
- Level 2 (`np.clip(E, 0.0, None)` at line 628): safety net against floating-point underflow that could produce `-0.0` or near-zero negatives.

Verified by the new unit test `test_build_absorption_matrix_can_clip_negative_extrapolated_extinction` (`tests/test_kubelka_munk.py:117–144`), which constructs a deliberately short-range spectrum (400–500 nm, falling to 0), extrapolates to 600 nm, and confirms the unclipped matrix entry is negative while the clipped entry is ≥ 0.

**No regression risk:** `clip_negative_extinction` defaults to `False`, matching all existing callers.

### 2. KM GUI path uses clipping

**Location:** `app/gui_qt/main_window.py:1501–1506`

```python
clip_negative_extinction=snapshot["solver_method"] == "km",
```

**Assessment: Correct.** Clipping is selectively enabled only for `"km"`, not for `"mu_a"`. This is the right scope — the `mu_a` solver was designed for chromophores with full-wavelength-range spectra (HbO₂, Hb) where extrapolation is not an issue. The KM solver targets bilirubin validation, which is the only use case with short-range spectra.

Verified by the GUI test `test_km_snapshot_captures_scattering_parameters_and_disables_background` (`tests/test_main_window.py:693–740`), which exercises the full snapshot path including the absorption-matrix build.

### 3. `solve_unmixing_km` — negative-basis clipping

**Location:** `app/core/processing.py:1266`

```python
A = np.clip(np.asarray(A, dtype=float), 0.0, None)
```

**Assessment: Correct defensive programming.** This is a third safety layer protecting direct API callers that might pass an unclipped absorption matrix. Even though the GUI path already clips, `solve_unmixing_km` is a public function and should protect itself. `scipy.optimize.nnls` technically allows negative entries in `A`, but treating bilirubin's NIR absorption as non-existent (clipped to 0) is physically correct.

Verified by `test_km_solver_clips_negative_absorption_basis_entries` (`tests/test_kubelka_munk.py:101–115`), which constructs an `A` with a negative entry, generates reflectance from the *clipped* matrix, and confirms the solver recovers the true concentrations.

### 4. DNG phantom validation — nonnegative matrix assertion

**Location:** `tests/test_km_phantom_validation.py:89`

```python
assert np.all(absorption_matrix >= 0.0)
```

**Assessment: Correct.** This is the integration-level verification that `clip_negative_extinction=True` produces a fully non-negative absorption matrix for the real bilirubin + Hb dataset across all 8 LED bands. This test would have caught the negative-extrapolation issue if it had existed before the fix.

### 5. Updated implementation plan

**Location:** `features/kubelka_munk_implementation_plan.md`, lines 82–95 ("Mitigation already added after review")

**Assessment: Accurate.** The mitigation section correctly documents all four countermeasures and lists the remaining known causes of poor bilirubin recovery (limited wavelength set, spectral cross-talk, restrictive scattering prior). No factual errors.

---

## Regression analysis

### Modified call signatures

| Function | Change | Risk |
|----------|--------|------|
| `solve_unmixing(..., reflectance=None)` | New keyword argument with default `None` | **None** — all 5 existing call sites pass only `od_cube`, `A`, `method`, and `mus_prime`. The new parameter is unused unless `method="km"`. |
| `build_absorption_matrix(..., clip_negative_extinction=False)` | New keyword argument with default `False` | **None** — all existing callers are unaffected. Only the KM GUI path passes `True`. |
| `SUPPORTED_UNMIXING_METHODS` | Added `"km"` | **None** — used only in `solve_unmixing` error message. Adding an entry only widens the accepted set; it does not alter existing dispatch paths. |

### New public function

`solve_unmixing_km(reflectance, A, mus_prime)` — purely additive. The GUI pipeline adapter calls it directly (line 1585), and the `solve_unmixing` dispatcher delegates to it when `method="km"`. No existing code calls it.

### Test suite

```
88 passed, 1 warning, 15 subtests passed across:
  test_kubelka_munk.py           —  9 passed (7 original + 2 new for clipping)
  test_km_phantom_validation.py  —  1 passed
  test_processing_fixed_scattering.py — 30 passed
  test_main_window.py            — 46 passed (44 original + 2 new for KM GUI)
  test_background_consistency.py —  2 passed
```

Zero failures. The one warning (`overflow encountered in power` in `_build_mu_s_spectrum` during a nonfinite-input hardening test) is pre-existing and unrelated to KM.

---

## Negative bilirubin extrapolation: is it sufficiently mitigated?

**Yes, for the immediate concern.** The three-layer defense guarantees that:

1. **No negative extinction coefficients enter the absorption matrix** when the KM solver is used via the GUI.
2. **No negative entries reach `scipy.optimize.nnls`** in `solve_unmixing_km`, even if called directly with an unclipped matrix.
3. **The integration test asserts this** for the real phantom dataset.

The bilirubin contribution at NIR bands (671–939 nm) is forced to zero, which is physically correct — bilirubin has negligible absorption beyond ~550 nm. The NNLS solver then attributes all NIR absorption to Hb, as it should.

### Remaining fundamental limitation (not a code bug)

Bilirubin identification still relies on only **2 of 8 LED bands** (450 nm and 517 nm). The clipping fix prevents the NIR bands from *actively harming* bilirubin recovery (negative entries would distort the NNLS solution), but it does not *add* bilirubin information in the NIR. This is a limitation of the input data (the bili_agat spectrum ends at 550 nm and the LED set lacks bands at 470 and 525–530 nm), not a code defect.

---

## Unaddressed review items (from km-implementation-review.md)

| Finding | Severity | Status | Risk of non-fix |
|---------|----------|--------|-----------------|
| M1: `SUPPORTED_UNMIXING_METHODS` excludes `"iterative"` | Medium | Unfixed | Low — the iterative solver bypasses `solve_unmixing` entirely. Only a semantic inconsistency; no functional impact. |
| M4: No tests for mixed valid/invalid bands in `solve_unmixing_km` | Medium | Unfixed | Low — requires pathological input (all bands have invalid μs′ or reflectance). The code handles it correctly (all-invalid → zero concentrations → fitted reflectance = 1.0), but untested. |
| M5: Reflectance > 1 silently clipped without warning | Medium | Unfixed | Low — the `_mu_a` solver has identical behavior. `compute_diagnostics` reports negative reflectance but not >1 reflectance. Adding a count would be trivial but is not blocking. |
| M2: No trend assertions in phantom validation | Medium | Intentional | None — deferred by design in the staged implementation plan. |

None of these are regressions — they were present before the post-review fixes and remain unchanged.

---

## Concrete findings

### Correct (evidence)

- The three-level clipping defense (build-time, solver-entry, integration-assert) is complete and internally consistent.
- All 88 tests pass; zero regressions.
- API signatures are backward-compatible for all existing callers.
- The GUI integration correctly restricts `clip_negative_extinction=True` to the KM solver only.
- The implementation plan accurately documents the mitigations and remaining known causes.

### Blocker

None.

### Notes

1. **The `clip_negative_extinction` clipping inside the `build_absorption_matrix` double loop creates a new array via `np.clip` on each iteration** (lines 621–623). This is safe (no mutation of the cached `chrom_interp` dict) but slightly wasteful — `chrom_interp[name]` is re-clipped once per LED band (8 times for the current dataset) instead of once per chromophore. A micro-optimization would be to clip `chrom_interp` values once before the double loop. Not a correctness concern; negligible performance impact for 8 bands × 2 chromophores.

2. **The `_uses_fixed_scattering_solver` set and inline `solver_method not in {"mu_a", "km"}` checks are duplicated in three locations** (`_build_config_snapshot:1426-1427`, `_set_solver_dependent_controls:1876-1878`, and the static method at line 1701-1703). The inline `not in {"mu_a", "km"}` for background controls could be unified with the static method pattern (`_uses_background_controls = solver_method not in self._solvers_without_background`). This is a maintainability note, not a correctness issue.

3. **`solve_unmixing_km` uses `compute_optical_density` for its RMSE calculation** (line 1302). The RMSE is therefore in OD (log₁₀) space, consistent with the `_mu_a` solver but orthogonal to the native KM reflectance-space residual. This is by design for GUI panel compatibility — the pixel inspector plots measured vs. fitted OD. No correctness issue, but users comparing KM RMSE values against literature should be aware of the log₁₀ transformation.

---

*End of review.*
