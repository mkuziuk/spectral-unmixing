# Kubelka-Munk Solver Implementation Plan

## Decision

Proceed with a **two-stage, additive implementation**:

1. **Stage A: classic KM remission solver** integrated into the current app.
2. **Stage B: phantom validation on the DNG-derived A1-A6 dataset** using `hb_agat_extr` and `bili_agat`.
3. **Stage C: optional nonlinear/Yudovsky KM-style forward model** only after Stage A produces stable baseline behavior.

Rationale:

- The current app already has a two-stage `mu_a` solver pattern: measured signal → absorption-like spectrum → NNLS chromophore fit.
- Classic KM remission can fit that pattern with minimal API risk.
- The Yudovsky/Monte-Carlo-calibrated model may be physically stronger, but it is a larger nonlinear inverse problem and should be benchmarked after a simple baseline exists.
- The DNG-derived images are small enough for quick validation, but per-pixel nonlinear optimization is still not the right first step.

## User constraints

- Branch: `feature/kubelka-munk-solver`
- Testing folder: `liquid_phantoms_for_unmixing_dng_cropped/`
- Required unmixing spectra:
  - `data/chromophores/hb_agat_extr.csv`
  - `data/chromophores/bili_agat.csv`
- Ground truth:
  - Hb = 100 µM for A1-A6
  - Bilirubin = 270 µM for A1, halving per next sample:
    - A1 270
    - A2 135
    - A3 67.5
    - A4 33.75
    - A5 16.875
    - A6 8.4375

## Stage A — implemented baseline core and GUI hook

### A1. Core solver

Add `km` support in `app/core/processing.py`:

- `SUPPORTED_UNMIXING_METHODS` includes `km`.
- `_reflectance_to_mu_a_km(reflectance, mus_prime)` uses:

\[
F(R)=\frac{(1-R)^2}{2R}
\]

\[
\mu_a \approx \frac{F(R)\mu_s'}{2}
\]

- `_mu_a_to_reflectance_km(mu_a, mus_prime)` reconstructs KM reflectance:

\[
R = 1 + F - \sqrt{F^2 + 2F}
\]

with:

\[
F = \frac{2\mu_a}{\mu_s'}
\]

- `solve_unmixing_km(reflectance, A, mus_prime)`:
  - converts reflectance to `mu_a`
  - solves `A @ c ≈ mu_a` with NNLS per pixel
  - reconstructs fitted reflectance and fitted OD
  - returns `(concentrations, rmse_map, fitted_od)` compatible with existing panels

### A2. GUI integration

Add `km` to `app/gui_qt/main_window.py`:

- solver combo includes `km`
- KM uses the absorption matrix path, same as `mu_a`
- KM uses fixed scattering controls, same as `mu_a`
- KM disables background, same as `mu_a`
- per-sample pipeline calls `processing.solve_unmixing_km(reflectance, A, mus_prime)`

### A3. Unit tests

Add `tests/test_kubelka_munk.py`:

- known KM conversion value
- clipping/finite behavior for nonphysical reflectance
- KM forward/inverse round trip
- synthetic concentration recovery
- nonnegative concentration check
- missing scattering profile error
- dispatcher support with `method="km"`

Current focused status:

```text
.venv/bin/python -m pytest -q tests/test_kubelka_munk.py
7 passed
```

## Stage B — implemented exploratory DNG smoke validation

Added `tests/test_km_phantom_validation.py` as an exploratory smoke test over the DNG-derived A1-A6 folder.

Current focused status:

```text
.venv/bin/python -m pytest -q tests/test_kubelka_munk.py tests/test_km_phantom_validation.py
10 passed
```

Broader focused status:

```text
.venv/bin/python -m pytest -q tests/test_kubelka_munk.py tests/test_km_phantom_validation.py tests/test_processing_fixed_scattering.py tests/test_main_window.py
86 passed, 1 warning, 15 subtests passed
```

Current baseline observations from the exploratory run:

- Hb median is finite and roughly decreases from about 50 µM in A1 to about 40 µM in A6.
- Bilirubin currently recovers as 0 µM for all A1-A6 with the classic KM + fixed-scattering baseline.
- This means the initial implementation is usable as a code path and test harness, but not yet scientifically validated for bilirubin recovery.

Mitigation already added after review:

- `build_absorption_matrix(..., clip_negative_extinction=True)` can now clip interpolated/extrapolated negative extinction values and final negative band integrals.
- The KM GUI path uses this clipping for the absorption matrix.
- `solve_unmixing_km(...)` defensively clips negative absorption-basis entries to zero.
- The DNG smoke test asserts that the KM validation matrix is nonnegative.

Likely remaining causes to investigate next:

1. The current wavelength set has only 450 and 517 nm in the useful bilirubin/Hb region.
2. Even after nonnegative clipping, `bili_agat` contributes little/no independent information in the NIR bands.
3. The fixed scattering prior may be too restrictive.
4. Hb/bilirubin spectral cross-talk may make NNLS attribute the blue absorption to `hb_agat_extr`.

Next validation task: add a calibration/scattering sensitivity analysis before making hard concentration-trend assertions.

## Stage C — implemented sensitivity scan diagnostic

Added:

```text
scripts/km_sensitivity_scan.py
```

Purpose:

- scan global effective scattering `μs'(500)` and power-law exponent `b`
- optionally scan a global absorption-matrix calibration factor `K`
- compare band subsets: `2band_blue`, `4band_vis`, and `8band_full`
- report Hb constancy, bilirubin monotonicity, bilirubin positivity, RMSE, and a composite score
- save full CSV results for plotting/review

Quick-run command:

```text
.venv/bin/python scripts/km_sensitivity_scan.py --quick --output research-reports/km_sensitivity_quick.csv
```

Quick/full scan result:

- model-free reflectance ratio `R450/R517` increases monotonically from A1 to A6, which is consistent with decreasing bilirubin.
- the quick grid found no nonzero bilirubin regime.
- the full grid found only partial bilirubin positivity in the most favorable corner: `8band_full`, `b=3.0`, low effective scattering, with positive bilirubin only for A1-A3 and zeros for A4-A6.
- after tightening the scan scoring/recommendation criteria to require at least four positive bilirubin samples, the full scan reports no directionally valid regime.
- this supports the current working hypothesis: the data contains a weak bilirubin trend, but the classic KM + current Agati spectra + current LED set cannot robustly separate bilirubin through NNLS.

Full scan artifacts:

```text
research-reports/km_sensitivity_quick.csv
research-reports/km_sensitivity_full.csv
```

Full focused validation still passes:

```text
.venv/bin/python -m py_compile scripts/km_sensitivity_scan.py scripts/bilirubin_index_report.py
.venv/bin/python -m pytest -q tests/test_kubelka_munk.py tests/test_km_phantom_validation.py tests/test_processing_fixed_scattering.py tests/test_main_window.py
88 passed, 1 warning, 15 subtests passed
```

Post-review corrections added to the sensitivity path:

- `_reflectance_to_mu_a_km(...)` now treats reflectance outside `(0, 1)` as invalid rather than valid-after-clipping, preventing dark/edge pixels from creating huge KM absorption values.
- sensitivity scan positivity thresholds now use a meaningful concentration threshold (`0.1 µM`) rather than numerical epsilon.
- all-zero bilirubin no longer receives monotonicity credit.
- Hb constancy now requires nonzero Hb presence.

## Stage D — implemented model-free two-band bilirubin index report

Added:

```text
scripts/bilirubin_index_report.py
```

Added core helper:

```text
processing.compute_bilirubin_index(...)
```

The primary diagnostic index is:

```text
BI_raw = OD450 - OD517
```

Report command:

```text
.venv/bin/python scripts/bilirubin_index_report.py --output research-reports/bilirubin_index_report.csv
```

Result on the DNG-derived A1-A6 set:

- `R450/R517` is monotonic increasing A1→A6.
- `OD450 - OD517` is monotonic decreasing A1→A6.
- log-linear in-sample fit `BI = slope * log10(bilirubin_uM) + intercept` gives `R² ≈ 0.942`.
- leave-one-out `R²` is poor/negative on the six-point calibration set, so the in-sample fit must not be treated as a generalizable concentration model.
- fitted bilirubin values are directionally useful but not reliable as physical concentrations, especially at A1 and low concentrations.

Current interpretation:

- the data contains a measurable bilirubin-related two-band trend.
- classic KM+NNLS cannot robustly separate bilirubin as a chromophore with this LED set.
- the two-band index is currently the most honest bilirubin diagnostic for these images; it should be labeled as an index/calibrated diagnostic, not physical unmixing.

Stage D GUI integration now adds an optional toolbar checkbox for `Bilirubin Index` plus optional `k_corr`. When enabled, each sample payload gains derived maps:

- `Bilirubin Index (OD450-OD517)`
- `Bili Index (raw)` only when Hb correction is enabled

The app validates that 450 nm and 517 nm bands are present, uses 671 nm when a correction is requested, computes dynamic derived-map scales, and export metadata includes a disclaimer that the map is a diagnostic index rather than concentration.

## Stage B follow-up — stricter DNG phantom validation TODO

`tests/test_km_phantom_validation.py` now exists as a non-strict exploratory smoke test. Upgrade it to stricter assertions only after calibration/sensitivity work shows bilirubin recovery is meaningful.

### B1. Load DNG-derived folder

Use:

```text
liquid_phantoms_for_unmixing_dng_cropped/
```

Expected layout:

```text
A1/ ... A6/
ref/
dark_ref/
```

### B2. Use only required chromophores

Force:

```python
chromophore_names = ["hb_agat_extr", "bili_agat"]
```

or `["bili_agat", "hb_agat_extr"]`, but keep ordering explicit in reports.

### B3. Build model inputs

- `load_led_emission(data_dir, wavelengths)`
- `load_chromophore_spectra(data_dir)`
- `build_absorption_matrix(..., chromophore_names=...)`
- `build_fixed_scattering_profile(...)`

### B4. Per-sample metrics

For each A1-A6:

- mean and median Hb coefficient
- mean and median bilirubin coefficient
- finite pixel fraction
- RMSE mean/median
- optional center ROI metrics to avoid edge/background artifacts

### B5. Future validation criteria

Keep these as future acceptance criteria, not current hard assertions:

- all results finite
- bilirubin median is monotonically decreasing from A1 to A6
- bilirubin ratios are directionally near 2, e.g. each ratio in `[1.2, 3.5]`
- Hb median coefficient is flatter than bilirubin coefficient across A1-A6
- report absolute scale vs µM, but do not fail solely on absolute calibration yet

Reason: KM coefficients, Agati spectra, and scattering prior may need a calibration scale before absolute µM accuracy is meaningful.

## Stage C — calibration and model upgrades

After Stage B, decide whether to:

1. Keep classic KM but add a global calibration factor.
2. Fit sample-level scattering amplitude `s0` instead of using fixed `mu_s_500/lipofundin_fraction/g`.
3. Add Yudovsky model as `km_yudovsky` or as an advanced option.
4. Add a downsampled nonlinear per-pixel solver.

## Risks to track

1. **Only 450 and 517 nm constrain bilirubin/Hb separation.** Missing 470 and 525-530 nm limits identifiability.
2. **`bili_agat.csv` ends at 550 nm.** Existing interpolation extrapolates beyond 550; validation should inspect long-wavelength effective extinction.
3. **Absolute units are uncertain.** Fitted values may need a scale factor to match µM.
4. **Fixed scattering may be wrong.** The Lipofundin concentration in A1-A6 may not match defaults.
5. **Reflectance values may be outside [0, 1].** Current implementation clips for KM conversion; validation should count clipped pixels.
6. **Classic KM is approximate.** If trends fail, Yudovsky/MC-calibrated reflectance is the next model, not necessarily a code bug.

## Implemented follow-up stages

### Stage E — Forward calibration backend

Implemented in:

```text
app/core/calibration.py
tests/test_calibration.py
```

Adds:

- `CalibrationModel` dataclass with schema version, fit type, coefficients, fit quality, calibration domain, validation flag, and disclaimer.
- `fit_calibration(...)` for log-linear index calibration.
- `apply_calibration(...)` with domain clipping.
- `calibration_clamp_counts(...)` for export/diagnostic metadata.
- `save_calibration(...)` / `load_calibration(...)` for JSON persistence.
- `get_default_calibration_path()` for `data/calibrations/bilirubin_a1a6_log_linear.json`.

The model is explicitly a domain-calibrated diagnostic estimate, not a physical concentration solver.

### Stage F — CLI save/load calibration

Implemented in:

```text
scripts/bilirubin_index_report.py
tests/test_bilirubin_index_report.py
```

New flags:

```bash
--save-calibration path.json
--load-calibration path.json
```

The script still reports the raw `OD450 - OD517` trend and now can create/apply calibration JSON files. Loaded-calibration outputs are labeled as estimates.

### Stage G — GUI calibration integration

Implemented in:

```text
app/gui_qt/main_window.py
app/core/export.py
tests/test_main_window.py
```

Toolbar additions:

```text
Bilirubin Index
k_corr
Apply Calibration
Load Calibration...
calibration status label
```

Derived maps:

```text
Bilirubin Index (OD450-OD517)
Bili Index (raw)                         # when k_corr is used
Bilirubin est. (calibrated, see disclaimer)
Bilirubin est. clamp mask
```

Export metadata includes bilirubin index notes and calibration metadata: coefficients, fit quality, domain, validation status, disclaimer, and clamp counts.

### Stage H — Bar chart diagnostic integration

Implemented in:

```text
app/gui_qt/panels/chromophore_barcharts_panel.py
tests/test_chromophore_barcharts_panel.py
```

When bilirubin derived maps are present, the Chromophore Bar Charts tab adds separate diagnostic subplots. These are not labeled as concentrations:

- index axis: `OD450 - OD517 (dimensionless)`
- calibrated estimate axis: `domain-calibrated estimate (see disclaimer)`

## Current status

The branch is feature-complete for the first KM/bilirubin-index/calibration implementation. Current full validation result:

```text
340 passed, 1 warning, 24 subtests passed
```

Remaining scientific work is forward validation, not basic implementation:

1. Prepare an expanded phantom calibration/validation set with replicate A1-A6, variable Hb, and variable Lipofundin/scattering.
2. Refit calibration using independent training/hold-out splits.
3. Only relax warnings if independent validation gives acceptable hold-out or cross-validated performance.
4. Keep documentation and UI labels conservative until then: the bilirubin output is a diagnostic estimate, not validated concentration.
