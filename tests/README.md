# Tests for Spectral Unmixing

## Overview

This directory contains test suites for verifying the correctness of the spectral unmixing pipeline, particularly focusing on edge cases and consistency checks.

## Test Files

### test_data_folder_selection.py

Tests for data directory validation and penetration depth file selection.

**Covers:**
- `validate_data_directory` success case
- Missing `leds_emission.csv`
- Missing `chromophores/` directory
- Empty `chromophores/` directory
- Penetration depth file selection priority:
  - Prefer `penetration_depth_digitized.csv`
  - Otherwise choose lexicographically first `penetration_depth*.csv`

**Tests included:**

1. `test_valid_data_directory`: Validates a properly structured data directory
2. `test_missing_leds_emission_csv`: Verifies error when `leds_emission.csv` is missing
3. `test_missing_chromophores_directory`: Verifies error when `chromophores/` is missing
4. `test_empty_chromophores_directory`: Verifies error when `chromophores/` has no CSV files
5. `test_prefer_digitized_when_present`: Confirms `penetration_depth_digitized.csv` is selected
6. `test_fallback_to_lexicographically_first`: Confirms fallback logic when digitized absent
7. `test_single_penetration_file`: Works with a single penetration depth file
8. `test_digitized_only`: Selects digitized when it's the only option

### test_background_consistency.py

Tests for background value consistency in spectral unmixing. This test suite was specifically designed to investigate the reported issue where changing the background value and then reverting it might cause inconsistent results.

**Tests included:**

1. `test_background_value_affects_unmixing`: Verifies that different background values produce different results (with appropriate tolerance)
2. `test_reverting_background_value_preserves_results`: Key test - verifies that reverting to a previous background value produces identical results
3. `test_maps_means_medians_consistency`: Verifies consistency of all output types (maps, means, medians)
4. `test_background_column_behavior`: Tests the behavior of the background column in the overlap matrix
5. `test_different_solver_methods_with_background`: Tests both LS and NNLS solvers

## Running Tests

### Run all tests
```bash
cd /Users/mikhail/Projects/Biophotonics-lab/spectral-unmixing
.venv/bin/python -m unittest discover tests
```

### Run specific test file
```bash
.venv/bin/python tests/test_data_folder_selection.py
.venv/bin/python tests/test_background_consistency.py
```

## Test Report

Run `tests/test_background_consistency.py` to generate a detailed report. The key findings are:

- Results ARE consistent when reverting background values
- Maps, means, and medians remain identical (max diff: 0.0)
- The core processing code correctly rebuilds the overlap matrix each time

## Notes

The tests use the sample data in `liquid_phantoms_for_unmixing_cropped/` which contains a single sample (A1) with 8 wavelength bands (450, 517, 671, 775, 803, 851, 888, 939 nm).
