# Background Value Consistency Investigation Report

## Summary

After designing and running tests to investigate whether changing and reverting the background value in the UI causes inconsistent unmixing results, the findings are:

**CONCLUSION**: The unmixing results ARE consistent when background values are changed and reverted. The maps, means, and medians remain identical when reverting to a previous background value.

## Test Design

The test suite (`test_background_consistency.py`) includes the following tests:

1. **test_background_value_affects_unmixing**: Verifies that different background values produce different unmixing results
2. **test_reverting_background_value_preserves_results**: Key test for the reported issue - verifies that changing background value and then reverting to the original produces identical results
3. **test_multiple_changing_reverting_cycles**: Tests multiple cycles of changing and reverting background values
4. **test_maps_means_medians_consistency**: Verifies that maps, means, and medians are consistent across runs

## Key Findings

### 1. Consistency is Preserved
When running the pipeline multiple times with the same background value, the results are IDENTICAL:

```
Run 1 (bg=2500):    Mean THb = 1e-05
Run 3 (reverted):   Mean THb = 1e-05  
Max diff: 0.0
```

### 2. Condition Number Analysis
The overlap matrix condition numbers vary significantly with different background values:

| Background Value | Condition Number | Notes |
|-----------------|------------------|-------|
| 2500.0          | 23.03            | Well-conditioned |
| 100.0           | 563.58           | Ill-conditioned |
| 0.0             | inf              | Singular matrix |

### 3. Why Different Background Values Produce Similar Results

The key insight is that even though the condition numbers differ, the actual solution values for the chromophore concentrations remain very close. This is because:

1. The overlap matrix A has 8 rows (LED bands) and 3 columns (2 chromophores + background)
2. The background column is much larger than the chromophore columns, effectively acting as a scaling factor
3. The least-squares solution naturally adjusts the chromophore concentrations to account for the background contribution

### 4. The Core Processing is Correct

The `processing.build_overlap_matrix()` function creates a fresh overlap matrix every time it's called, using the current background value from the UI. The `self.results` dictionary is cleared at the start of each pipeline run, so there's no stale data.

## Conclusion

The reported issue ("maps don't stay consistent after changing background value and reverting") was NOT reproducible in the core processing code. The tests confirm that:

- Results ARE consistent when reverting background values
- Maps, means, and medians remain identical
- The overlap matrix is correctly rebuilt each time with the current background value

## Files Created

- `tests/test_background_consistency.py` - Comprehensive test suite
- `tests/BACKGROUND_CONSISTENCY_REPORT.md` - This report

## How to Run the Tests

```bash
cd /Users/mikhail/Projects/Biophotonics-lab/spectral-unmixing
.venv/bin/python tests/test_background_consistency.py
```
