## Progress — Forward Calibration, Bar-Chart Integration, and Documentation

### Completed

- Implemented backend calibration module: `app/core/calibration.py`.
- Added calibration tests: `tests/test_calibration.py`.
- Updated bilirubin index CLI: `scripts/bilirubin_index_report.py` with `--save-calibration` and `--load-calibration`.
- Added CLI tests: `tests/test_bilirubin_index_report.py`.
- Added GUI controls for calibration: **Apply Calibration**, **Load Calibration...**, and calibration status label.
- Added calibrated derived maps:
  - `Bilirubin est. (calibrated, see disclaimer)`
  - `Bilirubin est. clamp mask`
- Added export calibration metadata and bilirubin disclaimers.
- Added bilirubin diagnostic subplots to the Chromophore Bar Charts panel with non-concentration y-axis labels.
- Added default A1-A6 calibration artifact:
  - `data/calibrations/bilirubin_a1a6_log_linear.json`
- Updated documentation:
  - `README.md`
  - `AGENT.md`
  - `features/kubelka_munk_solver.md`
  - `features/kubelka_munk_implementation_plan.md`
  - `features/spectral_unmixing.md`
  - `features/bilirubin_index_calibration.md`
- Updated `k_corr` tooltip to warn that calibration must be fitted with the same correction.

### Validation

Focused documentation-adjacent regression run:

```text
99 passed, 10 subtests passed
```

Full suite after calibration/bar-chart implementation:

```text
340 passed, 1 warning, 24 subtests passed
```

The warning is the existing fixed-scattering overflow warning test.

### Scientific caveat

The bilirubin index and calibrated estimate remain diagnostic outputs. The shipped A1-A6 calibration has strong in-sample trend but poor/negative leave-one-out validation and must not be presented as a validated physical bilirubin concentration.
