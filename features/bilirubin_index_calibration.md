# Feature: Bilirubin Index and Forward Calibration

## Overview

The application can compute a model-free bilirubin diagnostic map from DNG-derived phantom reflectance images:

```text
Bilirubin Index = OD450 - OD517
```

This index is useful for the Lipofundin + hemoglobin + bilirubin phantom series where the KM/NNLS chromophore map for `bili_agat` can be zero because the current LED set has limited Hb/bilirubin separability.

⚠️ The bilirubin index is dimensionless. It is not a spectral-unmixing concentration and not a validated physical bilirubin concentration.

## UI Controls

Toolbar controls:

- **Bilirubin Index** — enables the derived index map.
- **k_corr** — optional Hb correction coefficient for `OD450 - OD517 - k_corr * OD671`.
- **Apply Calibration** — applies a loaded log-linear calibration model to the index.
- **Load Calibration...** — loads a calibration JSON file.
- Calibration status label — shows the loaded calibration filename and warns when the calibration is not cross-validated.

Leave `k_corr` empty for the shipped calibration. Only use `k_corr` when the loaded calibration was fitted with the same `k_hb_correction`.

## Derived Maps

When **Bilirubin Index** is checked:

```text
Bilirubin Index (OD450-OD517)
```

When `k_corr` is used, the raw map is also retained:

```text
Bili Index (raw)
```

When **Apply Calibration** is checked and a calibration JSON is loaded:

```text
Bilirubin est. (calibrated, see disclaimer)
Bilirubin est. clamp mask
```

The clamp mask marks whether calibrated pixels stayed within the calibration domain after inversion/clipping. Large clamped regions mean the calibration is being applied outside its useful domain.

## Calibration Model

Calibration JSON files use schema version 1 and a log-linear model:

```text
BI = slope * log10(bilirubin_estimate) + intercept
```

The inverse used for the calibrated estimate is:

```text
bilirubin_estimate = 10 ** ((BI - intercept) / slope)
```

Core implementation:

```text
app/core/calibration.py
```

Important functions/classes:

- `CalibrationModel`
- `fit_calibration(...)`
- `apply_calibration(...)`
- `save_calibration(...)`
- `load_calibration(...)`
- `calibration_clamp_counts(...)`
- `model_summary_for_metadata(...)`

## Default Calibration

The shipped calibration is:

```text
data/calibrations/bilirubin_a1a6_log_linear.json
```

Domain:

- A1-A6 DNG-derived Lipofundin/Hb/bilirubin phantoms
- bilirubin approximately `8.4–270 µM`
- hemoglobin fixed at `100 µM`
- same camera/LED/DNG processing setup
- `k_hb_correction = null`

Fit quality:

- in-sample `R² ≈ 0.94`
- leave-one-out `R² < 0`

Interpret this calibration as a domain diagnostic estimate only.

## CLI

Fit and save a calibration JSON:

```bash
python scripts/bilirubin_index_report.py \
  --root liquid_phantoms_for_unmixing_dng_cropped \
  --save-calibration data/calibrations/bilirubin_a1a6_log_linear.json
```

Load and apply an existing calibration:

```bash
python scripts/bilirubin_index_report.py \
  --root liquid_phantoms_for_unmixing_dng_cropped \
  --load-calibration data/calibrations/bilirubin_a1a6_log_linear.json
```

## Bar Charts and Export

The Chromophore Bar Charts tab adds separate bilirubin diagnostic subplots when bilirubin derived maps exist. These axes are not labeled as concentration:

- raw index axis: `OD450 - OD517 (dimensionless)`
- calibrated estimate axis: `domain-calibrated estimate (see disclaimer)`

Exports include bilirubin notes in `metadata.json`:

- `bilirubin_index_note`
- `bilirubin_calibration` with coefficients, fit quality, domain, validation status, disclaimer, and clamp counts when available.

## Scientific Caveats

- The KM solver may not recover `bili_agat` as a positive chromophore map on the current LED set.
- The bilirubin index tracks relative contrast but is not a physical concentration.
- The shipped calibration is small-N and not independently validated.
- Do not use calibrated estimates outside the declared phantom/camera/LED domain.
- Do not report calibrated estimates as validated clinical or in-vivo bilirubin measurements.
