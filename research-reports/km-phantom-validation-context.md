# KM Phantom Validation — Context & Implementation-Ready Plan

> **Purpose**: Design the next validation task for the DNG-derived A1–A6 phantom dataset.
> **Output target**: `tests/test_km_phantom_validation.py` or a standalone validation script.
> **Status**: Research complete. All findings below are evidence-backed from code inspection and live data runs.

---

## 1. What Already Exists

### 1.1 KM Solver (implemented, in `app/core/processing.py`)

```python
# Line 1234
def solve_unmixing_km(
    reflectance: np.ndarray,   # (H, W, N_bands)
    A: np.ndarray,             # absorption matrix (N_bands, N_chrom)
    mus_prime: np.ndarray,     # band-averaged reduced scattering (N_bands,)
) -> tuple:
```

The solver:
1. Converts reflectance → μa per pixel via `_reflectance_to_mu_a_km()` using `F(R) = (1-R)²/(2R)` and `μa = F · μs' / 2`.
2. Then runs `scipy.optimize.nnls` to fit μa against the absorption matrix `A`.
3. Returns `(concentrations, rmse_map, fitted_od)` — same contract as other solvers.
4. Already wired in the GUI pipeline (`main_window.py:1584–1592`) and dispatched by `solve_unmixing()` when `method="km"`.

### 1.2 Existing Unit Tests

`tests/test_kubelka_munk.py` — 7 synthetic tests covering:
- `_reflectance_to_mu_a_km` known value & clipping
- `_mu_a_to_reflectance_km` round-trip
- Synthetic concentration recovery with known absorption matrix
- Non-negativity enforcement
- Required scattering profile validation
- Dispatcher integration

**No phantom validation test exists yet.**

### 1.3 Key Pipeline Functions (reused by the test)

| Function | File | Lines | Role |
|---|---|---|---|
| `io.detect_folders()` | `app/core/io.py:96` | Returns `{samples, ref_dir, dark_ref_dir, wavelengths, sample_names}` |
| `io.load_image_cube()` | `app/core/io.py:125` | Loads 8-band image cube `(H, W, 8)` float64 |
| `io.load_chromophore_spectra()` | `app/core/io.py:159` | Returns `{name: (wl_array, coeff_array)}` |
| `io.load_led_emission()` | `app/core/io.py:197` | Returns `(common_wl, {led_nm: emission_array})` |
| `io.load_penetration_depth()` | `app/core/io.py:238` | Returns `(wl_array, depth_array)` |
| `processing.compute_reflectance()` | `app/core/processing.py:239` | `R = (I-Idark)/(I0-Idark+ε)` |
| `processing.compute_optical_density()` | `app/core/processing.py:296` | `OD = -log10(R+ε)` |
| `processing.build_absorption_matrix()` | `app/core/processing.py:471` | Band-averaged extinction `E[n,k]` |
| `processing.build_overlap_matrix()` | `app/core/processing.py:421` | Overlap matrix `A[n,k] = lⁿ·εₖⁿ` |
| `processing.build_fixed_scattering_profile()` | `app/core/processing.py:505` | Band-averaged μs' |
| `processing.solve_unmixing_km()` | `app/core/processing.py:1234` | KM solver |
| `processing.solve_unmixing()` | `app/core/processing.py:1015` | Dispatcher for ls/nnls/mu_a/km |
| `processing.compute_derived_maps()` | `app/core/processing.py:1315` | THb, StO2 maps |

### 1.4 Phantom Data Layout

```
liquid_phantoms_for_unmixing_dng_cropped/
├── A1/  A2/  A3/  A4/  A5/  A6/    # 50×50 px PNG images (8 bands each)
│   ├── 450nm.png  …  939nm.png
├── ref/                              # white reference (50×50 px PNG)
│   ├── 450nm.png  …  939nm.png
└── dark_ref/                         # dark frame (50×50 px JPEG)
    ├── 450nm_2026-03-06-02-38.jpg  …  939nm_2026-03-06-02-38.jpg
```

- Wavelengths: `[450, 517, 671, 775, 803, 851, 888, 939]` nm
- Image resolution: 50×50 px (2500 pixels per sample)

### 1.5 Phantom Ground Truth

| Sample | Hb (µM) | Bilirubin (µM) | Bili ratio vs A1 |
|---|---:|---:|---:|
| A1   | 100  | 270     | 1.000 |
| A2   | 100  | 135     | 0.500 |
| A3   | 100  | 67.5    | 0.250 |
| A4   | 100  | 33.75   | 0.125 |
| A5   | 100  | 16.875  | 0.0625 |
| A6   | 100  | 8.4375  | 0.03125 |

Hb is constant. Bilirubin halves each step (log₂ ratio = −1.0 per step).

### 1.6 Required Chromophore Spectra

| File | Key in dict | λ range | Points | Notes |
|---|---|---|---|---|
| `data/chromophores/hb_agat_extr.csv` | `hb_agat_extr` | 320–1000 nm | 341 | Header: `lambda,extinction_coefficient` |
| `data/chromophores/bili_agat.csv` | `bili_agat` | 300–550 nm | 126 | Header: `wavelength_nm,extinction_coefficient` |

Both are in **(cm⁻¹/M)**. Both load correctly via `io.load_chromophore_spectra()` (different header names are skipped by `_load_two_column_csv`).

---

## 2. Critical Pitfalls Discovered

### 2.1 PITFALL 1: Bilirubin Extrapolation to Negative Values

`bili_agat.csv` **ends at 550 nm**. The function `build_absorption_matrix()` calls `_interpolate_chromophore_spectra()` (processing.py:419) which uses `fill_value="extrapolate"`. This causes **large negative extinction values** at the 6 near-IR bands (671–939 nm):

```
Band-averaged bili_agat extinction:
  450 nm: +43,657  ✓
  517 nm:  +9,073  ✓
  671 nm:  −2,521  ✗ negative!
  775 nm:  −5,170  ✗
  803 nm:  −5,819  ✗
  851 nm:  −7,094  ✗
  888 nm:  −7,942  ✗
  939 nm:  −9,070  ✗
```

**Impact**: The NNLS solver (which enforces `x ≥ 0`) sees the negative bilirubin column entries and **zeros out the bilirubin concentration** everywhere because a positive bilirubin concentration × negative extinction = negative absorption contribution, which can't help fit positive μa values. Confirmed by live run: `bili_agat` median = 0.0 for all A1–A6 with the current KM solver.

**Fix options** (for the validation test):
1. Use `fill_value=0.0` instead of `"extrapolate"` when interpolating `bili_agat` — the function `_interpolate_chromophore_spectra` doesn't support per-chromophore fill strategies, so the test must build the absorption matrix manually.
2. Clip negative values to 0 after building the matrix.
3. Restrict to only the 2 bands where bilirubin data is valid (450, 517 nm).

Even with `fill_value=0.0`, small negative values persist at 775 and 803 nm (−0.11, −10.9) due to LED emission profiles having negative noise values — the product of 0 (bili) × negative noise (LED profile) integrates to ~0 but numerical errors remain.

### 2.2 PITFALL 2: Extinction Coefficient Scale Mismatch

The Agati extinction coefficients predict absorption values that are **~8–24× higher** than what the measured reflectance implies via the KM remission function:

| Band | ε_hb × [Hb=100µM] | ε_bili × [Bili=270µM] | Predicted μa (KM) | Measured μa_KM (A1 median) | Ratio |
|------|-------------------|----------------------|-------------------|---------------------------|-------|
| 450 nm | 4.67 cm⁻¹ | 11.79 cm⁻¹ | 16.46 cm⁻¹ | 2.18 cm⁻¹ | 7.6× |
| 517 nm | 2.71 cm⁻¹ | 2.45 cm⁻¹ | 5.16 cm⁻¹ | 1.58 cm⁻¹ | 3.3× |

**Impact**: The solver cannot recover concentrations in µM directly. The NNLS fit assigns a ~5× smaller Hb concentration (≈5e-5 M = 50 µM instead of 100 µM) and zeros out bilirubin.

**Explanation**: The KM remission function uses phenomenological K and S coefficients. The relationship K ≈ 2μa is approximate. The Agati extinction coefficients may be for a different solvent environment. A calibration factor is needed.

### 2.3 PITFALL 3: Spectral Ratio Mismatch

The measured μa ratio at 450/517 nm does not match either chromophore's extinction ratio:

- Hb extinction ratio: ε₄₅₀/ε₅₁₇ = 46711/27057 = **1.726**
- Bilirubin extinction ratio: ε₄₅₀/ε₅₁₇ = 43578/9064 = **4.808**
- Measured μa ratio: A1 = **1.38**, A6 = **1.26**

For any non-negative mixture of Hb and bilirubin, the ratio must be between 1.726 and 4.808. The measured ratio (1.26–1.38) is **below** the Hb-only ratio, which is physically impossible if these are the only two absorbers.

**Likely cause**: Lipofundin (the scattering medium) has non-negligible absorption at 450 nm, acting as a third "chromophore" with an even lower 450/517 ratio, pulling the mixture ratio down. Or the Agati spectra are for a different solvent condition than the phantom.

### 2.4 PITFALL 4: mu_a Solver Outperforms KM on This Data

With the zero-filled bilirubin matrix, the `mu_a` solver (OD→μa inversion) detects non-zero bilirubin for A1 (1.15e-5) and zero for A2–A6, matching the expected decreasing trend. The KM solver zeros out bilirubin entirely. This is counterintuitive — the KM solver was expected to be better for reflectance-based data.

**Reason**: Both solvers use the same absorption matrix and scattering prior. The KM remission function `(1-R)²/(2R)` amplifies noise at low reflectance (R≈0.3). The mu_a solver's OD-based inversion is more stable for these reflectance values.

---

## 3. Implementation Plan for `tests/test_km_phantom_validation.py`

### 3.1 Test File Structure

```python
#!/usr/bin/env python3
"""Phantom validation for Kubelka-Munk (and other) solvers on A1–A6 DNG dataset.

Ground truth:
  Hb   = 100 µM constant across all samples
  Bili = 270 → 8.44 µM, halving each step (A1 → A2 → A3 → A4 → A5 → A6)

Uses chromophores:
  data/chromophores/hb_agat_extr.csv
  data/chromophores/bili_agat.csv
"""

import sys
import unittest
from pathlib import Path
import numpy as np
from scipy.interpolate import interp1d

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core import io, processing
from app.core.processing import (
    _normalized_led_profiles,
    _prepare_interp_axis,
)


class TestKMPhantomValidation(unittest.TestCase):
    """End-to-end phantom validation across all solvers."""

    ROOT_DIR = "liquid_phantoms_for_unmixing_dng_cropped"
    DATA_DIR = "data"
    CHROM_NAMES = ["hb_agat_extr", "bili_agat"]

    @classmethod
    def setUpClass(cls):
        # --- Load folder structure ---
        cls.info = io.detect_folders(cls.ROOT_DIR)
        cls.wls = cls.info["wavelengths"]  # [450, 517, 671, 775, 803, 851, 888, 939]

        # --- Load reference & dark ---
        cls.ref_cube = io.load_image_cube(cls.info["ref_dir"], cls.wls)
        cls.dark_cube = io.load_image_cube(cls.info["dark_ref_dir"], cls.wls)

        # --- Load spectral data ---
        cls.chrom_spectra = io.load_chromophore_spectra(cls.DATA_DIR)
        cls.led_wl, cls.led_em = io.load_led_emission(cls.DATA_DIR, cls.wls)
        cls.pen_wl, cls.pen_depth = io.load_penetration_depth(cls.DATA_DIR)

        # --- Build absorption matrix with ZERO-FILL for bilirubin ---
        # (critical: bili_agat.csv ends at 550 nm; extrapolation → negative values)
        cls.E_zf = cls._build_absorption_matrix_zero_fill()

        # --- Build overlap matrix with ZERO-FILL for bilirubin ---
        cls.A_zf = cls._build_overlap_matrix_zero_fill()

        # --- Fixed scattering profile ---
        cls.mus_prime = processing.build_fixed_scattering_profile(
            cls.led_wl, cls.led_em, cls.wls
        )

        # --- Load and process all samples ---
        cls.sample_results = {}
        for sample_dir, name in zip(cls.info["samples"], cls.info["sample_names"]):
            cube = io.load_image_cube(sample_dir, cls.wls)
            R = processing.compute_reflectance(cube, cls.ref_cube, cls.dark_cube)
            OD = processing.compute_optical_density(R)
            cls.sample_results[name] = {
                "cube": cube, "reflectance": R, "od": OD,
                "R_median": np.median(R.reshape(-1, 8), axis=0),
                "OD_median": np.median(OD.reshape(-1, 8), axis=0),
            }

    # ------------------------------------------------------------------
    # Matrix builders with zero-fill bilirubin
    # ------------------------------------------------------------------

    @classmethod
    def _build_absorption_matrix_zero_fill(cls):
        """Build band-averaged absorption matrix E with bili_agat zero-filled
        beyond its native wavelength range (300–550 nm)."""
        common_wl, led_profiles = _normalized_led_profiles(
            cls.led_wl, cls.led_em, cls.wls
        )
        f_hb = cls._make_interpolator("hb_agat_extr", fill="extrapolate")
        f_bili = cls._make_interpolator("bili_agat", fill=0.0)

        E = np.zeros((len(cls.wls), len(cls.CHROM_NAMES)))
        for i, phi in enumerate(led_profiles):
            E[i, 0] = np.trapezoid(phi * f_hb(common_wl), common_wl)
            E[i, 1] = np.trapezoid(phi * f_bili(common_wl), common_wl)
        return E

    @classmethod
    def _build_overlap_matrix_zero_fill(cls):
        """Build overlap matrix A with zero-filled bilirubin."""
        common_wl, led_profiles = _normalized_led_profiles(
            cls.led_wl, cls.led_em, cls.wls
        )
        f_depth = interp1d(
            cls.pen_wl, cls.pen_depth,
            kind="linear", fill_value="extrapolate", bounds_error=False,
        )
        depth_interp = f_depth(common_wl)
        f_hb = cls._make_interpolator("hb_agat_extr", fill="extrapolate")
        f_bili = cls._make_interpolator("bili_agat", fill=0.0)
        eps_funcs = [f_hb, f_bili]

        A = np.zeros((len(cls.wls), len(cls.CHROM_NAMES)))
        for i, phi in enumerate(led_profiles):
            l_n = np.trapezoid(phi * depth_interp, common_wl)
            for j in range(len(cls.CHROM_NAMES)):
                A[i, j] = l_n * np.trapezoid(phi * eps_funcs[j](common_wl), common_wl)
        return A

    @classmethod
    def _make_interpolator(cls, chrom_name, fill="extrapolate"):
        """Create an interp1d for a chromophore with sorted unique x-values."""
        wl, coeff = cls.chrom_spectra[chrom_name]
        wl_p, coeff_p = _prepare_interp_axis(wl, coeff)
        return interp1d(
            wl_p, coeff_p, kind="linear",
            fill_value=fill, bounds_error=False,
        )

    # ------------------------------------------------------------------
    # Helper: spatial statistics
    # ------------------------------------------------------------------

    @staticmethod
    def _spatial_stats(conc_map):
        """Return (median, iqr, mean) per chromophore for a (H,W,N) array."""
        H, W, N = conc_map.shape
        stats = []
        for j in range(N):
            c = conc_map[:, :, j]
            finite = c[np.isfinite(c)]
            median = float(np.median(finite))
            q25 = float(np.percentile(finite, 25))
            q75 = float(np.percentile(finite, 75))
            mean = float(finite.mean())
            stats.append({"median": median, "iqr": q75 - q25, "mean": mean})
        return stats

    # ------------------------------------------------------------------
    # Solver runners
    # ------------------------------------------------------------------

    def _run_km(self, reflectance):
        c, rmse, fitted_od = processing.solve_unmixing_km(
            reflectance, self.E_zf, self.mus_prime
        )
        return c, rmse

    def _run_mu_a(self, od_cube):
        c, rmse, fitted_od = processing.solve_unmixing(
            od_cube, self.E_zf, method="mu_a", mus_prime=self.mus_prime
        )
        return c, rmse

    def _run_nnls(self, od_cube):
        c, rmse, fitted_od = processing.solve_unmixing(
            od_cube, self.A_zf, method="nnls"
        )
        return c, rmse

    def _run_ls(self, od_cube):
        c, rmse, fitted_od = processing.solve_unmixing(
            od_cube, self.A_zf, method="ls"
        )
        return c, rmse
```

### 3.2 Test Cases

#### Test 1: `test_bilirubin_monotonicity_nnls`

```python
def test_bilirubin_monotonicity_nnls(self):
    """Bilirubin median concentration decreases monotonically A1→A6 for NNLS."""
    bili_medians = []
    for name in sorted(self.sample_results, key=lambda n: int(n[1:])):  # A1..A6
        od = self.sample_results[name]["od"]
        c, _ = self._run_nnls(od)
        stats = self._spatial_stats(c)
        bili_medians.append(stats[1]["median"])

    # Monotonic decrease
    for i in range(len(bili_medians) - 1):
        self.assertGreaterEqual(
            bili_medians[i], bili_medians[i + 1],
            f"Bili not monotonic: {bili_medians[i]:.3e} → {bili_medians[i+1]:.3e} "
            f"(A{i+1} → A{i+2})"
        )
```

#### Test 2: `test_hb_approximately_constant_nnls`

```python
def test_hb_approximately_constant_nnls(self):
    """Hb varies less than bilirubin across the series (coefficient of variation)."""
    hb_medians = []
    for name in sorted(self.sample_results, key=lambda n: int(n[1:])):
        od = self.sample_results[name]["od"]
        c, _ = self._run_nnls(od)
        stats = self._spatial_stats(c)
        hb_medians.append(stats[0]["median"])

    cv_hb = np.std(hb_medians) / (np.mean(hb_medians) + 1e-12)
    # Expect Hb CV < 0.20 (20%) since Hb is nominally constant
    self.assertLess(cv_hb, 0.20, f"Hb CV too high: {cv_hb:.3f}")
```

#### Test 3: `test_bilirubin_log2_slope_near_minus_one`

```python
def test_bilirubin_log2_slope_near_minus_one(self):
    """The log₂ ratio per step should be near −1.0 for bilirubin."""
    bili_medians = [...]
    slopes = []
    for i in range(len(bili_medians) - 1):
        if bili_medians[i+1] > 0 and bili_medians[i] > 0:
            slope = np.log2(bili_medians[i+1] / bili_medians[i])
            slopes.append(slope)

    mean_slope = np.mean(slopes)
    # Allow generous tolerance: expect −1.0 ± 0.5
    self.assertAlmostEqual(mean_slope, -1.0, delta=0.5)
```

#### Test 4: `test_no_nan_or_inf_in_concentrations`

```python
def test_no_nan_or_inf_in_concentrations(self):
    """No NaN or inf values in any sample's concentration maps."""
    for name, res in self.sample_results.items():
        for solver_name, run_fn in [
            ("KM", lambda r: self._run_km(r)[0]),
            ("mu_a", lambda od: self._run_mu_a(od)[0]),
            ("NNLS", lambda od: self._run_nnls(od)[0]),
            ("LS", lambda od: self._run_ls(od)[0]),
        ]:
            with self.subTest(sample=name, solver=solver_name):
                if solver_name == "KM":
                    c = run_fn(res["reflectance"])
                else:
                    c = run_fn(res["od"])
                self.assertTrue(
                    np.all(np.isfinite(c)),
                    f"{solver_name} {name}: {np.sum(~np.isfinite(c))} non-finite values"
                )
```

#### Test 5: `test_reflectance_ratio_trend`

```python
def test_reflectance_ratio_trend(self):
    """R_450 / R_517 increases as bilirubin decreases (bili absorbs more at 450)."""
    ratios = []
    for name in sorted(self.sample_results, key=lambda n: int(n[1:])):
        R_med = self.sample_results[name]["R_median"]
        ratios.append(float(R_med[0] / R_med[1]))  # R_450 / R_517

    # Ratios should increase from A1 (most bili → lowest R_450 → lowest ratio)
    # Wait — bili absorbs at 450nm, reducing R_450. Less bili → higher R_450.
    # R_450/R_517: A1 has lowest R_450 (most bili) → lowest ratio at A1
    # A6 has highest R_450 (least bili) → highest ratio
    # So ratio should INCREASE from A1→A6
    for i in range(len(ratios) - 1):
        self.assertLess(
            ratios[i], ratios[i + 1],
            f"R450/R517 not increasing: A{i+1}={ratios[i]:.4f} → A{i+2}={ratios[i+1]:.4f}"
        )
```

#### Test 6: `test_km_vs_mu_a_correlation`

```python
def test_km_vs_mu_a_correlation(self):
    """KM and mu_a solvers should produce correlated Hb estimates."""
    km_hb = []
    mua_hb = []
    for name in sorted(self.sample_results, key=lambda n: int(n[1:])):
        c_km, _ = self._run_km(self.sample_results[name]["reflectance"])
        c_mua, _ = self._run_mu_a(self.sample_results[name]["od"])
        km_hb.append(np.median(c_km[:,:,0]))
        mua_hb.append(np.median(c_mua[:,:,0]))

    r = np.corrcoef(km_hb, mua_hb)[0, 1]
    self.assertGreater(r, 0.5, f"KM vs mu_a Hb correlation too low: r={r:.3f}")
```

#### Test 7: `test_all_three_solvers_finite_rmse`

```python
def test_all_three_solvers_finite_rmse(self):
    """RMSE maps are finite and reasonable for all solvers on all samples."""
    for name in sorted(self.sample_results, key=lambda n: int(n[1:])):
        res = self.sample_results[name]
        for solver_name, run_fn in [
            ("KM", lambda: self._run_km(res["reflectance"])),
            ("mu_a", lambda: self._run_mu_a(res["od"])),
            ("NNLS", lambda: self._run_nnls(res["od"])),
        ]:
            with self.subTest(sample=name, solver=solver_name):
                _, rmse = run_fn()
                self.assertTrue(np.all(np.isfinite(rmse)))
                self.assertLess(np.nanmean(rmse), 1.0,
                    f"{solver_name} {name}: mean RMSE={np.nanmean(rmse):.4f} > 1.0")
```

### 3.3 Standalone Validation Script (optional alternative)

If a script is preferred over `unittest`, create `scripts/validate_km_phantom.py`:

```python
#!/usr/bin/env python3
"""Standalone phantom validation script — prints a markdown report table."""
import sys; sys.path.insert(0, ".")
from pathlib import Path
import numpy as np
from scipy.interpolate import interp1d
from app.core import io, processing
from app.core.processing import _normalized_led_profiles, _prepare_interp_axis

def build_matrices(...): ...
def spatial_stats(...): ...

def main():
    # Load, build, run all solvers, print comparison table
    ...

if __name__ == "__main__":
    main()
```

---

## 4. Expected Output & Acceptance Criteria

A passing validation should satisfy (in priority order):

| # | Criterion | Assertion |
|---|---|---|
| 1 | No NaN/inf in any concentration map | `np.all(np.isfinite(c))` |
| 2 | Bilirubin monotonic A1 ≥ A2 ≥ … ≥ A6 (NNLS) | `bili[i] >= bili[i+1]` for 5 consecutive pairs |
| 3 | Hb has lower CoV than bilirubin across A1–A6 | `cv(hb) < cv(bili)` or `cv(hb) < 0.20` |
| 4 | Reflectance ratio R₄₅₀/R₅₁₇ increases A1→A6 | Monotonic increase (5 pairs) |
| 5 | All RMSE maps finite and < 1.0 | `np.nanmean(rmse) < 1.0` |
| 6 | KM and mu_a Hb estimates positively correlated | Pearson r > 0.5 |

**Non-goals for this validation**:
- Absolute concentration accuracy (calibration required — see Pitfall 2)
- Bilirubin log₂ slope exactly −1.0 (extinction scale mismatch + limited bands)
- Perfect identification (only 2 blue/green bands for bili; missing 470/530 nm)

---

## 5. Commands to Run

```bash
# From project root:
cd /Users/mikhail/Projects/Biophotonics-lab/spectral-unmixing

# Run the validation test:
.venv/bin/python -m pytest tests/test_km_phantom_validation.py -v

# Or with unittest:
.venv/bin/python -m unittest tests.test_km_phantom_validation -v

# Or run standalone script:
.venv/bin/python scripts/validate_km_phantom.py

# Quick smoke test — load and check data integrity:
.venv/bin/python -c "
from app.core import io
info = io.detect_folders('liquid_phantoms_for_unmixing_dng_cropped')
assert len(info['samples']) == 6
assert info['wavelengths'] == [450, 517, 671, 775, 803, 851, 888, 939]
print('OK: 6 samples, 8 wavelengths')
"
```

---

## 6. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Bilirubin extrapolation zeros out the channel | **Certain** (happens now) | Build matrices with zero-fill; test LS (unconstrained) alongside NNLS |
| All solvers fail to detect bilirubin trend | Medium | Test reflectance ratio (model-free); report as finding, not failure |
| Test too slow (2500 pixels × 6 samples × 3 solvers) | Low | 50×50 is fast; NNLS per pixel: ~2s total. Skip LS for all-pixel if needed. |
| mu_a solver detects bili but KM doesn't | High (observed) | Include multi-solver comparison; report KM limitation explicitly |
| LED profiles have negative noise → small negative band integrals | Observed | Clip absorption matrix entries <0 to 0.0 after construction |

---

## 7. File Dependencies

The validation test/script imports from:

```
app/core/io.py              — detect_folders, load_image_cube, load_chromophore_spectra,
                              load_led_emission, load_penetration_depth
app/core/processing.py      — compute_reflectance, compute_optical_density,
                              build_fixed_scattering_profile, solve_unmixing_km,
                              solve_unmixing, _normalized_led_profiles,
                              _prepare_interp_axis
scipy.interpolate           — interp1d (already in requirements)
numpy                       — (already in requirements)
```

No new dependencies needed.

---

## 8. Summary of Evidence

1. **KM solver is already implemented** (`solve_unmixing_km` at processing.py:1234), wired in GUI, with unit tests in `test_kubelka_munk.py`.

2. **Bilirubin extrapolation is the #1 blocker** — `fill_value="extrapolate"` in `_interpolate_chromophore_spectra` (processing.py:419) produces large negative values at λ > 550 nm.

3. **The validation test must build absorption/overlap matrices with zero-fill for bilirubin** — this cannot reuse `build_absorption_matrix()` directly.

4. **Extinction coefficient scale is ~8× too high** for direct µM recovery — relative trends are the achievable goal.

5. **Only 2 of 8 bands (450, 517 nm) carry bilirubin information** — missing 470 nm (peak ratio) and 530 nm (isosbestic) limit identifiability.

6. **The `mu_a` solver outperforms KM on this data** — OD-based inversion is more stable than KM remission at R ≈ 0.3–0.4.

7. **No existing phantom validation exists** — `test_kubelka_munk.py` only has synthetic tests.
