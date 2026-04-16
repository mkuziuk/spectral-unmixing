# Tests for Spectral Unmixing

## Overview

This directory contains test suites for verifying the correctness of the spectral unmixing pipeline, particularly focusing on edge cases and consistency checks.

## Test Files

### test_background_consistency.py

Tests for background value consistency in spectral unmixing. This test suite was specifically designed to investigate the reported issue where changing the background value and then reverting it might cause inconsistent results.

**Tests included:**

1. test_background_value_affects_unmixing: Verifies that different background values produce different results (with appropriate tolerance)
2. test_reverting_background_value_preserves_results: Key test - verifies that reverting to a previous background value produces identical results
3. test_maps_means_medians_consistency: Verifies consistency of all output types (maps, means, medians)
4. test_background_column_behavior: Tests the behavior of the background column in the overlap matrix
5. test_different_solver_methods_with_background: Tests both LS and NNLS solvers

## Running Tests

cd /Users/mikhail/Projects/Biophotonics-lab/spectral-unmixing
.venv/bin/python tests/test_background_consistency.py

## Test Report

Run tests/test_background_consistency.py to generate a detailed report. The key findings are:

- Results ARE consistent when reverting background values
- Maps, means, and medians remain identical (max diff: 0.0)
- The core processing code correctly rebuilds the overlap matrix each time

## Notes

The tests use the sample data in liquid_phantoms_for_unmixing_cropped/ which contains a single sample (A1) with 8 wavelength bands (450, 517, 671, 775, 803, 851, 888, 939 nm).
