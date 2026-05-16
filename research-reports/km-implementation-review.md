# Kubelka-Munk Solver Implementation Review

**Date:** 2026-05-16
**Branch:** `feature/kubelka-munk-solver`
**Review scope:** Stage A (core solver + GUI hook), Stage B (phantom validation scaffold)

---

## Summary

The KM implementation is **correct, minimal, and well-integrated**. All 7 core KM unit tests and all 44 main-window tests pass. The KM math (remission function, forward/inverse conversion, round-trip) is accurate. The GUI integration follows the existing `mu_a` pattern cleanly. No regressions to existing solvers (`ls`, `nnls`, `mu_a`, `iterative`) were introduced. Two concerns are flagged: one **high-severity data limitation** (bili_agat extrapolation beyond 550 nm) that undermines the phantom validation, and one **medium note** about the `SUPPORTED_UNMIXING_METHODS` tuple missing `"iterative"`.

---

## Correct — what is already good (with evidence)

### 1. KM remission math (critical path)
- **`_reflectance_to_mu_a_km`** (`app/core/processing.py:1193–1214`)
  - Uses the standard semi-infinite Kubelka-Munk remission function: `F(R) = (1−R)²/(2R) = K/S`
  - Converts to absorption via the classical approximation: `μa = F(R)·μs' / 2` (`K≈2μa`, `S≈μs'`)
  - Verified manually: R=0.5, μs′=10 → μa=1.25 ✓ (matches test at `tests/test_kubelka_munk.py:9–16`)
- **`_mu_a_to_reflectance_km`** (`app/core/processing.py:1214–1231`)
  - Correct inverse: `R = 1 + K/S − √((K/S)² + 2(K/S))` where `K/S = 2μa/μs'`
  - Round-trip verified: μa→R→μa recovers original values to machine precision ✓ (test at `tests/test_kubelka_munk.py:28–36`)
- **Non-physical reflectance handling**: Values outside [eps, 1−eps] are clipped; all outputs remain finite ✓ (test at `tests/test_kubelka_munk.py:18–26`)

### 2. Solver algorithm (`solve_unmixing_km`, `app/core/processing.py:1234–1305`)
- Converts per-pixel reflectance → μa using KM remission
- Fits chromophore concentrations via NNLS per pixel (enforces non-negativity)
- Reconstructs fitted reflectance and converts to OD for panel compatibility
- Returns `(concentrations, rmse_map, fitted_od)` — same shape/type contract as every other solver
- Synthetic recovery test passes: known concentrations recovered to `atol=1e-10` ✓ (`tests/test_kubelka_munk.py:38–63`)
- Non-negativity enforcement tested ✓ (`tests/test_kubelka_munk.py:65–84`)
- Missing `mus_prime` raises `ValueError` ✓ (`tests/test_kubelka_munk.py:87–92`)
- All-zero/negative `mus_prime` raises `ValueError` ✓ (guard at `app/core/processing.py:1275–1279`)
- Partial band invalidity handled: `valid` mask excludes bad bands from NNLS; concentrations from valid bands propagate to full reconstruction ✓

### 3. Dispatcher integration (`solve_unmixing`, `app/core/processing.py:1012–1039`)
- `method="km"` requires `mus_prime` and `reflectance`, raises clear `ValueError` if missing
- Tested via `test_solve_unmixing_dispatches_km_when_reflectance_is_provided` ✓ (`tests/test_kubelka_munk.py:94–113`)
- `method="ls"`, `"nnls"`, `"mu_a"` dispatch unchanged (no regression)

### 4. GUI integration (`app/gui_qt/main_window.py`)
- **Solver combo** includes `"km"` at correct position (last) ✓ (line 383)
- **Control visibility**: `km` shows scattering toolbars, hides background and iterative toolbars — exactly mirrors `mu_a` behavior ✓ (lines 1702, 1877, 1427)
- **Snapshot**: captures scattering parameters, forces `include_background=False`, enforces at least one chromophore ✓ (test at `tests/test_main_window.py:696–740`)
- **Pipeline adapter**: builds absorption matrix (not overlap matrix) for `km`, uses `build_fixed_scattering_profile` for band-averaged `mus_prime`, calls `processing.solve_unmixing_km` ✓ (lines 1498–1508, 1584–1594)
- **Result payload**: includes `reflectance`, `od_cube`, `fitted_od`, `concentrations`, `rmse_map`, `diagnostics` — same structure as other solvers ✓

### 5. Tests
- All **7 KM core tests** pass (`tests/test_kubelka_munk.py`)
- All **44 main-window tests** pass (`tests/test_main_window.py`), including 2 KM-specific GUI tests
- Test coverage includes: known-value math, input clipping, round-trip consistency, synthetic recovery, non-negativity enforcement, error handling, dispatcher support

### 6. No regression risk
- `SUPPORTED_UNMIXING_METHODS` added `"km"` — only used in `solve_unmixing` error message, which is triggered only for unknown methods
- All new functions are additive (three private helpers + one public solver)
- `solve_unmixing` only enters the `km` branch when `method="km"` is explicitly passed
- GUI additions are conditional on solver selection, behind existing visibility-toggle infrastructure

---

## Blocker — critical issue that must be resolved

*None.* No correctness bugs, crashes, or regressions found. All tests pass.

---

## High — severe functional concern (data/model limitation)

### H1. bili_agat.csv extrapolation beyond 550 nm produces negative extinction coefficients

**Location:** `data/chromophores/bili_agat.csv` used via `build_absorption_matrix` → `_interpolate_chromophore_spectra` (`app/core/processing.py:315–331`)

**Evidence:**
```
bili_agat wl range: 300 – 550 nm
bili_agat extrap at 671 nm: −2738.50
bili_agat extrap at 939 nm: −9461.48
```
The integrated absorption matrix for the A1-A6 phantom wavelengths:
```
 WL (nm)     Hb_agat     Bili_agat
   450    46711.0862   43657.4296   ← OK
   517    27057.3121    9073.1149   ← OK
   671     2374.6986   −2520.6184   ← NEGATIVE
   775      882.5929   −5169.9346   ← NEGATIVE
   803     1026.9092   −5819.3316   ← NEGATIVE
   851     1612.2061   −7093.7971   ← NEGATIVE
   888     2068.5340   −7942.3084   ← NEGATIVE
   939     2403.6828   −9070.1406   ← NEGATIVE
```

**Impact:** The bilirubin column in the absorption matrix has strongly negative entries at all NIR bands (671–939 nm). This means:
- Only the 450 nm and 517 nm bands carry usable bilirubin signal
- The NNLS solver receives unphysical negative basis entries at NIR
- Bilirubin concentration identifiability is compromised — Hb and bilirubin separation relies on only two blue/green bands
- The ground-truth phantom validation (`tests/test_km_phantom_validation.py`) will produce unreliable bilirubin estimates regardless of KM math correctness

**Expected per spec:** This risk is explicitly documented in both the feature spec (`features/kubelka_munk_solver.md`, Risks #1 and #2) and the implementation plan (`features/kubelka_munk_implementation_plan.md`, Risks #1 and #2). However, no mitigation is in place.

**Recommended actions:**
1. **Short-term**: Clip the extrapolated spectrum to `max(extrapolated, 0)` or use a zero-fill beyond 550 nm instead of `fill_value="extrapolate"`. This would at least prevent negative extinction entries, though it would disable bilirubin sensitivity at NIR entirely (which is physically correct — bilirubin doesn't absorb at NIR).
2. **Medium-term**: Obtain bilirubin spectra measured beyond 550 nm, or use a literature spectrum (e.g., from Prahl, Jacques) that covers the full LED range.
3. **Documentation**: Add a warning log message when `build_absorption_matrix` detects a chromophore spectrum that extrapolates to negative values at integration wavelengths.

---

## Medium — observations and design notes

### M1. `SUPPORTED_UNMIXING_METHODS` excludes `"iterative"`
**Location:** `app/core/processing.py:16`
```python
SUPPORTED_UNMIXING_METHODS: tuple[str, ...] = ("ls", "nnls", "mu_a", "km")
```
The `"iterative"` solver is available in the GUI combo but is not listed in this tuple. It works because the iterative path bypasses the `solve_unmixing` dispatcher entirely (the pipeline adapter calls `solve_unmixing_iterative` directly). This is functionally correct but semantically inconsistent — a developer reading `SUPPORTED_UNMIXING_METHODS` might incorrectly conclude the iterative solver is not supported. Consider either adding `"iterative"` to the tuple (and handling it in `solve_unmixing` with a redirect or a clear error) or adding a separate `SUPPORTED_ITERATIVE_METHODS` constant.

### M2. Validation script asserts only finite execution, not monotonicity trends
**Location:** `tests/test_km_phantom_validation.py:79–112`

The phantom validation test intentionally asserts only payload sanity (finite values, shape correctness) and prints a comparison table. It does not enforce:
- Bilirubin monotonicity A1 > A2 > … > A6
- Bilirubin halving ratios near 2× per step
- Hb constancy ± some tolerance across A1–A6

**Status:** Per the implementation plan, this is deliberate for Stage B:
> "This intentionally asserts only finite execution and payload sanity. Absolute concentration/trend assertions are deferred until the KM scale and scattering calibration are settled."

However, be aware that without trend assertions, CI would pass a KM solver that produces random or flat outputs. When the scale/calibration is determined, trend assertions should be added.

### M3. RMSE is reported in optical-density space, not reflectance space
**Location:** `app/core/processing.py:1294–1299`
```python
measured_od = compute_optical_density(reflectance)
residual_per_pixel = measured_od - fitted_od
rmse_map = np.sqrt(np.mean(residual_per_pixel ** 2, axis=2))
```

This is by design (per the feature spec) for GUI panel compatibility. However, the KM model is a reflectance model — the physical residuals are in reflectance space. A user comparing KM RMSE against `mu_a` or `ls` RMSE should understand they're in OD space (log₁₀-transformed), not native reflectance space. The `_mu_a` solver similarly computes RMSE in OD space, so the comparison is internally consistent.

### M4. No test for mixed valid/invalid bands or all-invalid edge case
The per-pixel loop in `solve_unmixing_km` handles partial validity via the `valid` mask, but there are no unit tests covering:
- Some bands invalid, some valid → NNLS on submatrix
- All bands invalid → `nnls` skipped, concentrations remain zero, fitted reflectance defaults to 1.0

These edge cases are unlikely with realistic data but would benefit from explicit tests, especially the all-invalid path (no-op with zero concentrations).

### M5. Reflectance > 1 is silently clipped without warning
**Location:** `app/core/processing.py:1206`
```python
R = np.clip(reflectance_arr, eps, 1.0 - eps)
```

If reflectance exceeds 1.0 (possible with imperfect dark/ref calibration), the KM remission function silently clips it to `1.0 − ε`, producing F≈0 and μa≈0. The `_mu_a` solver has a similar pattern but warns via `compute_diagnostics` (`n_negative_reflectance` count). The KM solver's `compute_diagnostics` call will catch negative reflectance values, but reflectance > 1.0 is not flagged. Consider adding a similar diagnostics check or log warning for pixels with reflectance > 1.0.

---

## Notes — low-severity observations

### N1. `_mu_a_to_reflectance_km` valid-mask fallthrough
When `mus_prime_arr ≤ eps` (invalid scattering), `ratio` stays at 0 and reflectance is computed as 1.0 (then clipped). This is reasonable for internal reconstruction but could produce subtly misleading fitted reflectance values at bands where scattering is numerically degenerate.

### N2. No performance benchmarks
The per-pixel `nnls` loop will scale linearly with pixel count. For the A1-A6 phantom images (small DNG-derived crops), runtime is negligible. The implementation plan acknowledges this as a future concern (Stage C/4).

### N3. Feature spec mentions `validate_km_parameters` — not implemented
The feature spec (`features/kubelka_munk_solver.md`) suggests an optional `validate_km_parameters(...)` function. This is not implemented and not needed for the current classic-KM approach (which reuses the existing `validate_scattering_parameters`). The mention appears to be forward-looking for a potential nonlinear/KM-fit-scattering variant. No action needed now.

---

## Files examined

| File | Lines | Purpose |
|------|-------|---------|
| `app/core/processing.py` | 1–1305 | Core processing: KM math, solver, dispatch |
| `app/gui_qt/main_window.py` | 1–2382 | GUI: solver combo, pipeline adapter, control visibility |
| `tests/test_kubelka_munk.py` | 1–115 | 7 unit tests for KM core |
| `tests/test_main_window.py` | 1–860 | 44 tests including 2 KM-specific GUI tests |
| `tests/test_km_phantom_validation.py` | 1–112 | Phantom validation smoke test (Stage B) |
| `features/kubelka_munk_solver.md` | 1–200 | Feature specification |
| `features/kubelka_munk_implementation_plan.md` | 1–135 | Implementation plan with staged approach |

---

## Test results

```
tests/test_kubelka_munk.py .......                                  [7 passed]
tests/test_main_window.py ........................................  [44 passed]
```

No failures, no warnings.

---

*End of review.*
