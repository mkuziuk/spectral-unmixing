# KM Calibration / Scattering Sensitivity Analysis — Implementation Plan

> **Purpose:** Design a sensitivity-analysis script or test that scans the scattering
> prior (`μs'(500)`, power-law exponent `b`) and/or a global calibration scale factor,
> evaluates Hb constancy and bilirubin monotonicity across the DNG A1–A6 phantoms,
> and identifies parameter regimes that avoid overfitting.
>
> **Target output:** `scripts/km_sensitivity_scan.py` (standalone diagnostic script,
> not a unit test — results are reported, not asserted).
>
> **Status:** Research complete. All evidence from live code, test runs, and research reports.

---

## 1. What the Current KM Baseline Shows

The existing `tests/test_km_phantom_validation.py` smoke test with default scattering
(`μs′(500) = 120 cm⁻¹ × 0.25 f_lipo × 0.2 (1−g) = 6 cm⁻¹`), `power_b = 1.0`,
and `clip_negative_extinction=True` produces:

| Sample | Hb median (µM) | Hb truth | Bili median (µM) | Bili truth |
|--------|---------------|----------|-----------------|------------|
| A1     | 50.0          | 100      | 0.0              | 270        |
| A2     | 43.8          | 100      | 0.0              | 135        |
| A3     | 41.4          | 100      | 0.0              | 67.5       |
| A4     | 40.3          | 100      | 0.0              | 33.75      |
| A5     | 40.6          | 100      | 0.0              | 16.875     |
| A6     | 40.3          | 100      | 0.0              | 8.4375     |

Observations:
- Hb is recovered at ~40–50 µM (roughly half of the 100 µM truth) but shows reasonable constancy across A1–A6 (CV ≈ 8%).
- Bilirubin is **zeroed out by NNLS** in all 6 phantoms. The negative-NIR and huge-scale extinction entries make the NNLS solver unable to attribute any absorption to bilirubin.
- The RMSE is ~0.07 OD units, which is acceptably low → the KM remission function is fitting the data just fine with Hb-only (one chromophore), so there's no residual "room" for bilirubin.

### Root cause: extinction scale mismatch

| Band | ε_Hb × 100 µM | ε_Bili × 270 µM | Predicted μa | Measured μa_KM (A1) | Ratio |
|------|--------------|-----------------|-------------|---------------------|-------|
| 450 nm | 4.67 cm⁻¹ | 11.79 cm⁻¹ | 16.46 cm⁻¹ | 2.18 cm⁻¹ | 7.6× |
| 517 nm | 2.71 cm⁻¹ | 2.45 cm⁻¹ | 5.16 cm⁻¹ | 1.58 cm⁻¹ | 3.3× |

The predicted absorption from Agati extinction + ground-truth concentrations is **3–8× too high**
compared to what the KM remission function infers from the measured reflectance.
The band-wise ratio mismatch (7.6× at 450 nm vs 3.3× at 517 nm) means a single global
scale factor won't fully resolve the discrepancy — the spectral shape is also wrong.

### Why bilirubin is zero despite `clip_negative_extinction=True`

Even though the NIR bands now have zero bilirubin extinction (via clipping), the 450 nm
and 517 nm bilirubin extinction values (43,657 and 9,073 cm⁻¹/M) are so large that the
NNLS solver sees them as "expensive" — any bilirubin concentration produces large μa
contributions that overshoot the measured μa. Hb alone can already fit the measured μa
with moderate concentration, so NNLS assigns zero to bilirubin.

---

## 2. Design: What to Scan

### 2.1 Scattering parameters (2-D grid)

| Parameter | Symbol | Default | Range to scan | Step count | Description |
|-----------|--------|---------|---------------|------------|-------------|
| μs′(500) effective | `mu_s_500 × f_lipo × (1−g)` | 6 cm⁻¹ | 0.5 – 240 cm⁻¹ | 20 log-spaced | Controls the overall scattering level; directly scales μa_KM |
| Power-law exponent | `b` | 1.0 | 0.1 – 3.0 | 15 linear | Controls spectral slope of μs′(λ) |

The **effective μs′(500)** = `mu_s_500_cm1 × lipofundin_fraction × (1 − anisotropy_g)`
is what `build_fixed_scattering_profile()` actually computes.  Varying `mu_s_500_cm1`
alone (keeping `f_lipo=0.25`, `g=0.8`) would sweep the effective μs′(500) from
~1.0 to ~168 cm⁻¹ for the 20-step log-spaced grid.

**Grid size:** 20 × 15 = 300 parameter pairs. Each pair requires one absorption matrix
build + 6 phantom solves → ~300 × 6 pixelwise NNLS fits → ~1800 total solver runs.
At ~0.05 s per 50×50 solve, total runtime ~90 seconds. Acceptable.

### 2.2 Calibration scale factor (1-D scan, optionally nested)

Scan a single global multiplicative factor `K` applied element-wise to the absorption
matrix: `E_calibrated[n,k] = K × E[n,k]`. With a single K, both Hb and bilirubin columns
scale identically — this probes whether the aggregate extinction scale is the problem.

| Parameter | Default | Range | Step count | Description |
|-----------|---------|-------|------------|-------------|
| Calibration factor K | 1.0 | 0.01 – 10.0 | 30 log-spaced | Multiplies the entire absorption matrix |

**Option A (fast):** Scan K at the default scattering → 30 evaluations.
**Option B (thorough):** Grid of (K, μs′(500), b) → 30 × 20 × 15 = 9000 points.
**Recommendation:** Start with Option A for a quick diagnostic. If K alone can't
recover bilirubin trends, proceed to the full 3-D scan.

### 2.3 What should NOT be scanned (avoid overfitting)

| Parameter | Why NOT to scan |
|-----------|----------------|
| Per-chromophore K factors | Would allow arbitrary Hb/bili ratio fitting. A1–A6 is only 6 data points; 2 per-chromophore K's = 2 degrees of freedom already risks overfitting. |
| Per-sample scattering | Hb is constant and bili is monotonic by design; per-sample μs′ would fit away the signal. The phantoms share the same Lipofundin matrix — scattering should be identical across A1–A6. |
| Per-band K factors | With 8 bands and only 2 chromophores, per-band K's would simply absorb spectral shape mismatches with no physical interpretation. |
| Lipofundin fraction or anisotropy g | These are multiplicative with μs′(500) — scanning them is redundant with scanning μs′(500). Keep fixed at defaults. |
| Wavelength subset selection within a scan | Systematically test a few predefined subsets (e.g., [450,517], [450,517,671,775], all 8) as separate experiments, not nested grid dimensions. |

### 2.4 Wavelength band subsets to test

In addition to the main scan, evaluate a few fixed band subsets as separate rows in the
output table. This is a structured experiment, not a grid dimension.

| Subset label | Bands | Rationale |
|---|---|---|
| `2band_blue` | [450, 517] | Only bands where bili_agat has positive extinction; 2 equations for 2 unknowns |
| `4band_vis` | [450, 517, 671, 775] | Adds NIR Hb sensitivity without bili contamination |
| `8band_full` | all 8 | The current default; NIR bands have zero bili extinction |

---

## 3. Metrics: What to Report

### 3.1 Primary diagnostic metrics (per grid point)

| Metric | Description | Target range | Formula |
|--------|-------------|-------------|---------|
| **Hb CoV** | Coefficient of variation of Hb medians across A1–A6 | < 0.15 (15%) | `std(hb_medians) / mean(hb_medians)` |
| **Bili monotonicity** | Number of consecutive decreasing pairs A1≥A2≥…≥A6 | 5 (perfect) | `count(bili[i] ≥ bili[i+1])` for i=1..5 |
| **Bili dynamic range** | Ratio of max bili median to min bili median across A1–A6 | > 2.0 | `max(bili_medians) / (min(bili_medians) + ε)` |
| **Bili log₂ slope** | Mean log₂ ratio per step (A_i / A_{i+1}) | near −1.0 | `mean(log2(bili[i+1] / bili[i]))` |
| **Bili positivity** | Median bili > 0 for A1 (the highest-concentration sample) | `bili_A1 > ε` | Binary |
| **Mean RMSE** | Mean across A1–A6 of per-sample mean RMSE | < 0.2 | `mean(rmse_means)` |

### 3.2 Composite score (for ranking)

```
composite = 0.0
if bili_positive_A1:
    composite += 1.0
composite += bili_monotonicity / 5.0                    # 0..1
composite += max(0, 1.0 - Hb_CoV)                       # 0..1
composite += min(1.0, bili_dynamic_range / 10.0)        # 0..1
composite += max(0, 1.0 - abs(bili_log2_slope + 1.0))  # 0..1
```

Max composite = 5.0. Higher = better. This penalises solutions that:
- Zero out bilirubin entirely (score ≤ 1.0 from Hb constancy alone)
- Produce non-monotonic bilirubin
- Produce wildly wrong log₂ slopes (overfitting signal)

### 3.3 Per-parameter-pair output

For each (μs′(500)_eff, b) pair, print a CSV/table row with:
```
mu_s_500_eff, power_b, Hb_CoV, bili_monotonicity, bili_dynamic_range, bili_log2_slope, bili_positive_A1, mean_rmse, composite
```

### 3.4 Top-N summary

Print the top 5 parameter combinations by composite score, with full per-sample
Hb and bilirubin median tables.

---

## 4. Avoiding Overfitting

### 4.1 Principles

1. **Global parameters only.** A single μs′(500) and b apply to ALL A1–A6 samples. No per-sample tuning.
2. **Few degrees of freedom.** Scanning 2 scattering parameters against 6 phantom data points leaves 4 residual degrees of freedom — the fit is evaluated, not optimized per phantom.
3. **Trend metrics, not absolute accuracy.** The metrics measure monotonicity and constancy, not µM-scale agreement with ground truth. This prevents driving toward a specific concentration value by over-tuning parameters.
4. **Cross-validation by design.** The same scattering parameters are applied to 6 chemically distinct phantoms. A parameter combination that works for Hb constancy AND bilirubin monotonicity simultaneously is less likely to be coincidental.
5. **No extinction editing.** The absorption matrix is used as-is (with clipping) — no per-band weight adjustment, no spectral warping. If bilirubin trends emerge, they're real, not engineered.

### 4.2 What constitutes a "real" signal vs. overfitting

| Behaviour | Interpretation |
|-----------|---------------|
| Bilirubin monotonically decreasing AND Hb nearly constant AND composite > 4.0 | **Likely real** — the KM model is directionally recovering both chromophores |
| Bilirubin monotonically decreasing BUT Hb wildly varying (CoV > 30%) | **Suspect** — parameters may be trading Hb variance for bili structure |
| Bilirubin monotonic but log₂ slope far from −1.0 (e.g., −0.3 or −3.0) | **Partial signal** — trend direction is right but scale is compressed/expanded |
| Bilirubin zero for all parameter combinations | **Structural limitation** — spectral overlap or wavelength coverage prevents bilirubin identification |
| Composite peaks at extreme parameter values (very low μs′ or very high b) | **Overfitting regime** — the model is exploiting a degenerate corner of parameter space |

### 4.3 Sanity checks

After the scan, verify:
1. The top-parameter μs′(500) values are physically plausible for Lipofundin phantoms (roughly 2–30 cm⁻¹ effective). Values <1 or >100 indicate the solution found a non-physical optimum.
2. The top-parameter b values are in the 0.5–2.0 range typical for biological tissues. b < 0.1 or > 3.0 is suspect.
3. The per-sample Hb medians at the top parameters are all within ±30% of their mean. A single outlier indicates a data issue with that phantom.
4. The reflectance ratio R₄₅₀/R₅₁₇ increases monotonically A1→A6 (model-free check). If it doesn't, the raw data contradicts the expected trend → no parameter tuning can fix it.

---

## 5. Implementation Design for `scripts/km_sensitivity_scan.py`

### 5.1 Script structure

```python
#!/usr/bin/env python3
"""KM sensitivity scan: scattering prior × calibration factor on DNG A1–A6.

Grid-scans μs'(500) and power-law exponent b (and optionally a global
calibration factor K) across the phantom series, reports Hb constancy and
bilirubin monotonicity metrics. Produces a ranked CSV summary.

Usage:
    python scripts/km_sensitivity_scan.py
    python scripts/km_sensitivity_scan.py --skip-calibration  # scattering-only
    python scripts/km_sensitivity_scan.py --output results.csv
"""

import sys
from pathlib import Path
import numpy as np
from scipy.interpolate import interp1d

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core import io, processing
from app.core.processing import _normalized_led_profiles, _prepare_interp_axis
```

### 5.2 Core function: build absorption matrix with bilirubin zero-fill

Crucially, we build the absorption matrix with **zero-fill beyond 550 nm** for bilirubin,
not the default `"extrapolate"` behaviour of `_interpolate_chromophore_spectra`. We use
`_normalized_led_profiles` and a custom interpolator factory.

```python
def build_absorption_matrix_zero_fill_bili(
    led_wl, led_emission, chrom_spectra, led_wavelengths, chromophore_names,
) -> np.ndarray:
    """Band-averaged absorption matrix E with bili_agat zero-filled at λ > 550 nm."""
    common_wl, led_profiles = _normalized_led_profiles(
        led_wl, led_emission, led_wavelengths)

    E = np.zeros((len(led_wavelengths), len(chromophore_names)))
    for i, phi in enumerate(led_profiles):
        for j, name in enumerate(chromophore_names):
            wl, coeff = chrom_spectra[name]
            wl_p, coeff_p = _prepare_interp_axis(wl, coeff)
            fill = 0.0 if name == "bili_agat" else "extrapolate"
            f = interp1d(wl_p, coeff_p, kind="linear",
                         fill_value=fill, bounds_error=False)
            coeff_interp = f(common_wl)
            coeff_interp = np.clip(coeff_interp, 0.0, None)  # safety clip
            E[i, j] = np.trapezoid(phi * coeff_interp, common_wl)

    return np.clip(E, 0.0, None)
```

### 5.3 Scattering profile builder (parametrized)

```python
def build_scattering_profile_for_params(
    led_wl, led_emission, led_wavelengths,
    mu_s_500_cm1, power_b,
    lambda0=500.0, f_lipo=0.25, g=0.8,
) -> np.ndarray:
    """Band-averaged μs' for given scattering parameters."""
    return processing.build_fixed_scattering_profile(
        led_wl, led_emission, led_wavelengths,
        lambda0_nm=lambda0,
        mu_s_500_cm1=mu_s_500_cm1,
        power_b=power_b,
        lipofundin_fraction=f_lipo,
        anisotropy_g=g,
    )
```

### 5.4 Per-sample solver

```python
def run_km_for_sample(
    sample_cube, ref_cube, dark_cube,
    absorption_matrix, mus_prime,
) -> tuple[np.ndarray, float]:
    """Run KM solver on one phantom. Returns (concentration_map, mean_rmse)."""
    reflectance = processing.compute_reflectance(sample_cube, ref_cube, dark_cube)
    concentrations, rmse_map, _ = processing.solve_unmixing_km(
        reflectance, absorption_matrix, mus_prime)
    return concentrations, float(np.nanmean(rmse_map))
```

### 5.5 Metric computation

```python
def compute_metrics(hb_medians: np.ndarray, bili_medians: np.ndarray,
                    rmse_means: list[float]) -> dict:
    """Compute Hb constancy and bilirubin monotonicity metrics.

    Parameters
    ----------
    hb_medians : (6,)  — Hb median concentration per A1..A6
    bili_medians : (6,) — Bili median concentration per A1..A6
    rmse_means : list[float]

    Returns
    -------
    dict with keys: Hb_CoV, bili_mono, bili_range, bili_log2_slope,
                    bili_positive_A1, mean_rmse, composite
    """
    eps = 1e-12
    Hb_CoV = float(np.std(hb_medians) / (np.mean(hb_medians) + eps))

    bili_mono = int(np.sum(np.diff(bili_medians) <= 0))  # 0..5

    bili_range = float(
        max(bili_medians, initial=0.0) / (max(min(bili_medians, initial=0.0), eps)))

    slopes = []
    for i in range(len(bili_medians) - 1):
        if bili_medians[i] > eps and bili_medians[i+1] > eps:
            slopes.append(np.log2(bili_medians[i+1] / bili_medians[i]))
    bili_log2_slope = float(np.mean(slopes)) if slopes else 0.0

    bili_pos = 1 if bili_medians[0] > eps else 0

    mean_rmse = float(np.mean(rmse_means))

    composite = (
        bili_pos
        + bili_mono / 5.0
        + max(0.0, 1.0 - Hb_CoV)
        + min(1.0, bili_range / 10.0)
        + max(0.0, 1.0 - abs(bili_log2_slope + 1.0))
    )

    return {
        "Hb_CoV": Hb_CoV,
        "bili_mono": bili_mono,
        "bili_range": bili_range,
        "bili_log2_slope": bili_log2_slope,
        "bili_positive_A1": bool(bili_pos),
        "mean_rmse": mean_rmse,
        "composite": composite,
    }
```

### 5.6 Scan loops

```python
def scan_scattering_grid(info, ref_cube, dark_cube, absorption_matrix,
                         led_wl, led_emission):
    """Grid scan over μs'(500) and power-law exponent b."""
    mu_s_eff_values = np.logspace(np.log10(0.5), np.log10(240), 20)
    b_values = np.linspace(0.1, 3.0, 15)

    results = []
    for mu_s_500_raw in mu_s_eff_values:
        for b in b_values:
            # Convert effective μs'(500) back to mu_s_500_cm1 parameter
            # effective = mu_s_500_cm1 * f_lipo * (1 - g)
            # → mu_s_500_cm1 = effective / (f_lipo * (1 - g))
            mu_s_500_cm1 = mu_s_500_raw / (0.25 * 0.2)  # = / 0.05

            mus_prime = build_scattering_profile_for_params(
                led_wl, led_emission, info["wavelengths"],
                mu_s_500_cm1=mu_s_500_cm1, power_b=b)

            hb_meds, bili_meds, rmses = [], [], []
            for sample_dir, name in zip(info["samples"], info["sample_names"]):
                cube = io.load_image_cube(sample_dir, info["wavelengths"])
                conc, rmse = run_km_for_sample(
                    cube, ref_cube, dark_cube, absorption_matrix, mus_prime)
                stats = spatial_medians(conc)
                hb_meds.append(stats[0])
                bili_meds.append(stats[1])
                rmses.append(rmse)

            metrics = compute_metrics(
                np.array(hb_meds), np.array(bili_meds), rmses)
            metrics["mu_s_500_eff"] = mu_s_500_raw
            metrics["power_b"] = b
            results.append(metrics)

    return results


def scan_calibration_grid(info, ref_cube, dark_cube, absorption_matrix,
                          led_wl, led_emission):
    """Scan global calibration factor K at default scattering."""
    mus_prime = build_scattering_profile_for_params(
        led_wl, led_emission, info["wavelengths"],
        mu_s_500_cm1=120.0, power_b=1.0)

    K_values = np.logspace(np.log10(0.01), np.log10(10.0), 30)
    results = []
    for K in K_values:
        E_cal = absorption_matrix * K
        hb_meds, bili_meds, rmses = [], [], []
        for sample_dir, name in zip(info["samples"], info["sample_names"]):
            cube = io.load_image_cube(sample_dir, info["wavelengths"])
            conc, rmse = run_km_for_sample(
                cube, ref_cube, dark_cube, E_cal, mus_prime)
            stats = spatial_medians(conc)
            hb_meds.append(stats[0])
            bili_meds.append(stats[1])
            rmses.append(rmse)

        metrics = compute_metrics(
            np.array(hb_meds), np.array(bili_meds), rmses)
        metrics["K"] = K
        results.append(metrics)

    return results
```

### 5.7 Output formatting

The script should:
1. Print a header describing the phantom ground truth and default-parameter results.
2. Print the top 5 parameter combinations ranked by composite score, with full
   per-sample Hb/bili tables.
3. Save a full CSV of all grid points for plotting.
4. Print a model-free sanity check: reflectance ratio R₄₅₀/R₅₁₇ trend across A1–A6.
5. Print a recommendation: which parameter regime (if any) produces directionally
   correct bilirubin and Hb trends.

Example output format:

```
KM Sensitivity Scan — DNG A1–A6 Phantom Series
===============================================
Ground truth: Hb = 100 µM (constant), Bili = 270→8.44 µM (halving)

Sanity check — R₄₅₀/R₅₁₇ reflectance ratio:
  A1: 0.XXX  A2: 0.XXX  ... → monotonic: YES/NO

--- Scattering grid scan (300 points) ---

Top 5 parameter combinations by composite score:
Rank  μs'(500) b     Hb_CoV  BiliMono  BiliRange  Log2Slope  BiliPos  RMSE   Score
1     12.6     1.30  0.082   5/5       6.23       −0.94      YES      0.071  4.89
2      7.9     1.50  0.091   5/5       5.18       −0.87      YES      0.073  4.82
...

Per-sample detail for Rank 1:
Sample  Hb_median  Hb_truth  Bili_median  Bili_truth
A1      52.3       100       12.4         270.0
A2      49.1       100        5.8         135.0
A3      48.7       100        3.1          67.5
A4      47.2       100        1.6          33.75
A5      45.8       100        0.9          16.875
A6      44.9       100        0.4           8.4375

Note: Bili concentrations are in solver-native units (not µM).
      A calibration factor of ~22× (270/12.4) would map A1 to truth.

--- Calibration factor scan (30 points) ---
... (same format)

Full grid saved to: sensitivity_scan_results.csv
```

### 5.8 Spatial statistics helper

```python
def spatial_medians(conc_map: np.ndarray) -> list[float]:
    """Return per-chromophore spatial median for a (H,W,N) array."""
    H, W, N = conc_map.shape
    medians = []
    for j in range(N):
        c = conc_map[:, :, j]
        finite = c[np.isfinite(c)]
        medians.append(float(np.median(finite)) if len(finite) > 0 else 0.0)
    return medians
```

---

## 6. Parameter Ranges — Physical Justification

### 6.1 μs′(500) effective range: 0.5 – 240 cm⁻¹

For Intralipid/Lipofundin phantoms at typical dilutions (1–20% v/v):
- Flock et al. (1992): μs'(630) ≈ 6–30 cm⁻¹ for Intralipid-10% at 1–4%.
- Michels et al. (2008): μs'(500) ≈ 28 cm⁻¹ for Intralipid-20% (pure).
- Di Ninni et al. (2012): Lipofundin S-20% ≈ Intralipid-20% within 5%.

The effective range 0.5–240 cm⁻¹ covers:
- Very dilute scatterer (0.5 → ~0.08% v/v Lipofundin-20%)
- Pure Lipofundin-20% × safety margin (240 → ~pure × 8.6×)

This wide range ensures we don't miss the optimum by an a priori restriction.

### 6.2 Power-law exponent b: 0.1 – 3.0

- Jacques (2013): biological tissues b = 0.1–3.3, typical 0.5–2.5.
- Bahl et al. (2024): Intralipid phantoms b ≈ 0.98, stable across concentrations.
- For Mie scattering from lipid droplets, b is related to particle size distribution.

Range covers Rayleigh (b ≈ 4) to large-Mie (b ≈ 0.4) regimes. A wider range
would explore non-physical regimes and invite overfitting.

### 6.3 Calibration factor K: 0.01 – 10.0

The factor-of-7.6 scale mismatch at 450 nm suggests the optimum K may be near
1/7.6 ≈ 0.13. The range 0.01–10 spans two orders of magnitude around 1.0,
comfortably covering the plausible optimum.

---

## 7. Wavelength Subset Experiment (supplementary)

Not part of the main grid, but the script should test 3 predefined subsets with
default scattering to compare band configurations:

```python
BAND_SUBSETS = {
    "2band_blue": [0, 1],                       # 450, 517 nm
    "4band_vis":  [0, 1, 2, 3],                 # 450, 517, 671, 775 nm
    "8band_full": list(range(8)),                # all
}
```

For each subset, run the same metrics computation. This isolates whether the
NIR bands (with zero bilirubin extinction) help by constraining Hb or hurt by
adding noise / redundant equations.

---

## 8. Dependencies and Imports

The script uses only already-available imports:

| Import | Source | Why |
|--------|--------|-----|
| `numpy` | requirements.txt | Array ops, stats |
| `scipy.interpolate.interp1d` | requirements.txt | Custom spectrum interpolation |
| `app.core.io` | project | `detect_folders`, `load_image_cube`, `load_chromophore_spectra`, `load_led_emission` |
| `app.core.processing` | project | `compute_reflectance`, `solve_unmixing_km`, `build_fixed_scattering_profile`, `_normalized_led_profiles`, `_prepare_interp_axis` |

No new dependencies.

---

## 9. Commands to Run

```bash
cd /Users/mikhail/Projects/Biophotonics-lab/spectral-unmixing

# Main scan (scattering grid + calibration scan):
.venv/bin/python scripts/km_sensitivity_scan.py

# Scattering-only (skip calibration scan):
.venv/bin/python scripts/km_sensitivity_scan.py --skip-calibration

# Save full CSV:
.venv/bin/python scripts/km_sensitivity_scan.py --output sensitivity_results.csv

# Quick smoke test (reduced grid for development):
.venv/bin/python scripts/km_sensitivity_scan.py --quick  # uses 5×3 grid
```

---

## 10. Acceptance Criteria

The script is successful if:

| # | Criterion | Measurement |
|---|---|---|
| 1 | Runs without errors on the DNG A1–A6 dataset | Exit code 0 |
| 2 | Produces a ranked table of ≥1 parameter combination with bili_pos_A1 = True | Bilirubin is non-zero for A1 at some parameter combination |
| 3 | Reports the reflectance ratio sanity check (model-free) | R₄₅₀/R₅₁₇ trend printed |
| 4 | Reports whether any parameter combination achieves bili_mono ≥ 4 AND Hb_CoV < 0.20 | "Found/Missing directionally valid regime" printed |
| 5 | Saves a CSV of all grid points for plotting | File exists, ≥300 rows (scattering) + ≥30 rows (K) |
| 6 | Identifies the top-parameter μs′(500)_eff and b values | Printed in summary |
| 7 | Includes a recommendation paragraph: "calibration factor K ≈ X would map recovered concentrations to µM" | Printed in recommendation |

**Non-goals:**
- Guaranteeing bilirubin recovery (the spectral overlap and band limitations may make this impossible regardless of parameters — the scan diagnoses this)
- Asserting any pass/fail — this is a diagnostic, not a validation test
- Fitting per-chromophore calibration factors
- Producing publication-ready figures

---

## 11. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Bilirubin stays zero for all parameter combinations | High (observed in current test) | The scan will confirm this and quantify the structural limitation. The recommendation section will state clearly if no scattering/calibration regime recovers bilirubin. |
| The optimum μs′(500) is at an extreme value (e.g., 0.5 or 240) | Medium | Flag as "non-physical optimum — likely overfitting." Extend the range and re-run if the score is still climbing at the boundary. |
| Grid computation takes >5 minutes | Low (estimated ~90s) | Use `--quick` flag for development. Cache absorption matrices where possible (only E depends on K; scattering profiles can be pre-computed). |
| Per-pixel NNLS produces NaN in some parameter corners | Low | NaN-guard the spatial_medians function. Report NaN counts in summary. |
| The 2-band (450, 517 nm) exactly-determined system produces unstable Hb/bili attribution | Medium | This is expected physics — the 470 nm BR/Hb isosbestic ratio point isn't in the LED set. The script reports this as a finding. |

---

## 12. File Summary

| File | Purpose | New/Modified |
|------|---------|-------------|
| `scripts/km_sensitivity_scan.py` | Main scan script | **New** |
| `research-reports/km-sensitivity-analysis-plan.md` | This plan | **New** |

No changes to existing source files. The script is standalone and diagnostic-only.

---

## 13. Evidence Sources

1. **Current KM baseline:** `tests/test_km_phantom_validation.py` run confirms Hb ~50 µM, bili = 0 (see §1 above). Live run evidence: `pytest tests/test_km_phantom_validation.py -v -s`.
2. **Bilirubin extrapolation problem:** `bili_agat.csv` ends at 550 nm (127 rows); `_interpolate_chromophore_spectra` uses `fill_value="extrapolate"` → negative values at λ > 550 nm. Confirmed in `km-implementation-review.md` §H1.
3. **Extinction scale mismatch:** Measured vs predicted μa ratios documented in `km-phantom-validation-context.md` §2.2 and §2.3.
4. **Scattering parameter defaults:** `app/core/processing.py:19–24` — μs(500)=120, b=1.0, f_lipo=0.25, g=0.8 → effective μs′(500)=6 cm⁻¹.
5. **KM solver architecture:** `solve_unmixing_km()` at `app/core/processing.py:1234–1305` with `_reflectance_to_mu_a_km()` at line 1205.
6. **Phantom ground truth:** Hb=100 µM constant, bili halving 270→8.44 µM across A1–A6. Documented in `km-staged-implementation-plan.md` and `km-phantom-validation-context.md` §1.5.
7. **Lipofundin scattering parameters:** Michels et al. (2008) μs' power-law, Di Ninni et al. (2012) Lipofundin≈Intralipid equivalence. Summarised in `lipofundin-hb-bilirubin-phantoms.md` §1–2.
8. **Spectral overlap:** Hb/Bili both absorb 400–500 nm; optimal separation at 470/530 nm pair — neither in current LED set. Documented in `lipofundin-hb-bilirubin-phantoms.md` §6.
