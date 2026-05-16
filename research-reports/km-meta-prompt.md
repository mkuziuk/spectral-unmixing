# Meta-Prompt: Implement Kubelka-Munk Solver

**Goal:** Add a working Kubelka-Munk spectral unmixing solver to this repo on branch `feature/kubelka-munk-solver`, with full GUI integration and validation against the DNG phantom series A1–A6 using chromophores `bili_agat` and `hb_agat_extr`.

**Context/Evidence:** See `/research-reports/km-implementation-context.md` for the complete codebase map, integration points, test patterns, phantom ground truth, and risk analysis. See `features/kubelka_munk_solver.md` for the specification.

## Hard Constraints

- **Branch:** `feature/kubelka-munk-solver`
- **No editing files** at this stage (analysis/handoff only — the next agent does the implementation)
- **Chromophore spectra:** Use `data/chromophores/hb_agat_extr.csv` and `data/chromophores/bili_agat.csv` only for KM validation. Do not use `Hb.csv`, `HbO2.csv`, or `bilirubin.csv` for KM fits unless the user explicitly requests it.
- **Test data:** `liquid_phantoms_for_unmixing_dng_cropped/` (PNG files, 50×50 px, 8 LED bands 450–939 nm)
- **Phantom ground truth:** Hb = 100 µM constant across A1–A6; bilirubin halves each step: A1=270, A2=135, A3=67.5, A4=33.75, A5=16.875, A6=8.4375 µM.
- **Payload compatibility:** Must produce result dicts with all keys expected by existing Qt panels (`concentrations`, `rmse_map`, `fitted_od`, `derived`, `diagnostics`, etc.). See km-implementation-context.md §3.5 for the full key list.
- **No breaking changes** to existing solvers (`ls`, `nnls`, `mu_a`, `iterative`) — KM is additive only.
- **Existing tests must continue to pass.** New KM tests should follow the patterns in `test_processing_fixed_scattering.py` (core math) and `test_main_window_qt013_callbacks.py` (Qt integration).

## Suggested Approach

### Stage 1 — Core Math (processing.py)

1. Add `build_km_band_basis()` — reuses `_normalized_led_profiles()` and `_interpolate_chromophore_spectra()`. Returns band-averaged extinction per chromophore `E_band[n,k]`.
2. Add `build_km_scattering_profile()` — band-averages `S(λ) = s₀·(λ/λ₀)^(-b)` using the same LED profiles.
3. Add `km_reflectance()` — vectorized KM forward model: `R = 1 + K/S − √((K/S)² + 2·K/S)`.
4. Add `solve_unmixing_km()` — per-pixel bounded least-squares fit of `[c_hb, c_bili, s₀]` with `scipy.optimize.least_squares`. Returns `(concentrations, rmse_map, fitted_od, solver_info)` where `fitted_od = -log10(R_KM + eps)`.
5. Add KM parameter validation functions (`get_default_km_parameters()`, `validate_km_parameters()`).
6. Write core tests (synthetic recovery, monotonicity, bounds, bili_agat extrapolation handling).

### Stage 2 — GUI Integration (main_window.py)

1. Add `"km"` to the solver combo in `_build_toolbar()`.
2. Update `_set_solver_dependent_controls()` to show scattering toolbar (not background) for KM.
3. Add KM branch in `_build_config_snapshot()` to capture KM-specific parameters.
4. Add KM branch in `_make_pipeline_adapter()` to call `solve_unmixing_km()` with reflectance input.
5. Ensure result payload has all expected keys.
6. Write Qt integration tests.

### Stage 3 — Phantom Validation

1. Write a validation function/test/script that processes A1–A6 through the KM pipeline.
2. Assert bilirubin monotonically decreases: A1 > A2 > A3 > A4 > A5 > A6.
3. Assert log₂ ratio between consecutive samples is approximately 1 (halving).
4. Assert Hb concentration is approximately constant across samples (or varies less than bilirubin).
5. Report RMSE and residual spectra per sample.

## Success Criteria

1. `"km"` appears in the solver dropdown and can be selected.
2. Running KM on A1–A6 produces result payloads compatible with all existing panels (no crashes, maps render, stats compute).
3. Bilirubin estimate decreases monotonically from A1 to A6 (trend qualitative, not absolute concentration accuracy).
4. No NaN/inf values in concentration maps, RMSE maps, or fitted OD.
5. All existing tests pass (especially `test_processing_fixed_scattering.py`, `test_main_window_qt013_callbacks.py`, `test_gui_qt_smoke.py`).
6. New KM-specific core tests pass.

## Validation Commands

```bash
# Core math tests
.venv/bin/python -m pytest -q tests/test_processing_fixed_scattering.py

# Qt integration tests (headless)
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_main_window_qt013_callbacks.py tests/test_gui_qt_smoke.py

# Full test suite
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/

# KM-specific tests (to be created)
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_kubelka_munk.py
```

## Stop/Escalation Rules

- **If the bili_agat spectrum range (300–550 nm) causes extrapolation instability at 671+ nm bands:** Consider using `fill_value=0.0` (explicit zero) instead of `fill_value="extrapolate"` for bilirubin beyond 550 nm.
- **If per-pixel `least_squares` is prohibitively slow (2500+ pixels):** Fall back to fitting `s₀` from the sample ROI average first, then solve concentrations per-pixel with fixed scattering.
- **If fitted_od panels break:** Verify `fitted_od = -log10(R_KM + eps)` uses the same `eps=1e-10` as `compute_optical_density()`.
- **If the phantom validation shows no bilirubin trend:** Check whether the Agati extinction coefficients need a calibration scale factor. The CSV values are in cm⁻¹/M; phantom concentrations in µM need unit conversion.
- **For any decision that affects the public API or existing solver behavior:** escalate via intercom before proceeding.

## Resolved Questions

- Solver name: `"km"` (per feature doc)
- Spectra: `hb_agat_extr` + `bili_agat` only for KM
- Test folder: `liquid_phantoms_for_unmixing_dng_cropped/`
- Scattering: fit `s₀` per-pixel initially, consider per-sample optimization for performance
- b is fixed at 1.0 initially, optionally exposed later
- Background controls: OFF for KM (no OD nuisance basis)
- KM entry point: standalone `solve_unmixing_km()` (not via `solve_unmixing()` dispatcher), following the iterative solver pattern

## Assumptions to Verify

1. Agati extinction coefficients in the CSVs are directly usable for µM-scale concentration fitting without additional calibration.
2. The PNG files in `liquid_phantoms_for_unmixing_dng_cropped/` are correctly handled by `load_image_cube()` (they are; PIL works for PNG).
3. `_interpolate_chromophore_spectra()` with `fill_value="extrapolate"` produces physically reasonable near-zero values for bilirubin beyond 550 nm.
4. The existing `compute_reflectance()` output needs clipping to [0, 1] before KM fitting to avoid domain errors.
