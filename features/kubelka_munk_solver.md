# Feature: Kubelka-Munk Solver for Lipofundin/Hemoglobin/Bilirubin Phantoms

## Goal

Add and validate a physically motivated Kubelka-Munk (KM) spectral unmixing solver for the Lipofundin phantom series.

The solver is intended for testing alternatives to the current Beer-Lambert/overlap-matrix and fixed-scattering `mu_a` models. It should estimate hemoglobin and bilirubin concentrations from diffuse reflectance while accounting for a wavelength-dependent scattering background.

## Branch

Development branch:

```text
feature/kubelka-munk-solver
```

## User-specified phantom ground truth

Use the A1-A6 phantom series as the validation set.

| Sample | Hemoglobin | Bilirubin |
|---|---:|---:|
| A1 | 100 µM | 270 µM |
| A2 | 100 µM | 135 µM |
| A3 | 100 µM | 67.5 µM |
| A4 | 100 µM | 33.75 µM |
| A5 | 100 µM | 16.875 µM |
| A6 | 100 µM | 8.4375 µM |

Assumption to confirm later: hemoglobin remains constant at 100 µM for all samples, and only bilirubin halves from sample to sample.

## Required spectra

For this solver/test path, use these chromophore spectra:

```text
data/chromophores/hb_agat_extr.csv
data/chromophores/bili_agat.csv
```

The implementation should make it easy to select these spectra in the UI and in tests. Validation should not accidentally use `Hb.csv`, `HbO2.csv`, or `bilirubin.csv` unless explicitly requested.

## Required image set for testing

Use the DNG-derived test photo folder:

```text
liquid_phantoms_for_unmixing_dng_cropped/
```

Current files are PNG images organized with the same sample/reference layout:

```text
A1/ ... A6/
ref/
dark_ref/
```

Wavelengths:

```text
450, 517, 671, 775, 803, 851, 888, 939 nm
```

## Physical model

Use a Kubelka-Munk diffuse-reflectance model rather than directly fitting optical density.

For a semi-infinite homogeneous scattering medium:

\[
R_\infty(\lambda)
= 1 + \frac{K(\lambda)}{S(\lambda)}
- \sqrt{\left(\frac{K(\lambda)}{S(\lambda)}\right)^2 + 2\frac{K(\lambda)}{S(\lambda)}}
\]

where:

- \(K(\lambda)\) is the absorption-like KM coefficient
- \(S(\lambda)\) is the scattering/backscattering-like KM coefficient

Absorption model:

\[
K(\lambda) = c_{Hb}\,\epsilon_{Hb,agat}(\lambda) + c_{bili}\,\epsilon_{bili,agat}(\lambda)
\]

Scattering model:

\[
S(\lambda) = s_0 \left(\frac{\lambda}{\lambda_0}\right)^{-b}
\]

Initial recommended defaults:

- \(\lambda_0 = 500\,nm\)
- fit \(s_0\) per pixel or per sample
- keep \(b\) fixed initially, e.g. `b = 1.0`, then optionally expose it as a global/sample-level parameter

## LED-band integration

Do not sample spectra at only the nominal LED center if avoidable. Follow the existing pattern in `build_overlap_matrix()` and `build_absorption_matrix()`:

1. Load LED emission profiles.
2. Area-normalize each LED profile.
3. Interpolate chromophore spectra onto the LED wavelength grid.
4. Integrate band-averaged spectra:

\[
\epsilon_k^{(n)} = \int \phi_n(\lambda)\epsilon_k(\lambda)d\lambda
\]

For KM, also band-average or evaluate scattering consistently per LED:

\[
S^{(n)} = \int \phi_n(\lambda)S(\lambda)d\lambda
\]

Then predict reflectance for each LED band.

## Proposed inverse formulation

For each pixel, fit nonnegative parameters:

```text
x = [c_hb, c_bili, s0]
```

Optional later version:

```text
x = [c_hb, c_bili, s0, b]
```

Minimize reflectance residuals, not OD residuals:

\[
\min_x \sum_n w_n\left(R_{measured}^{(n)} - R_{KM}^{(n)}(x)\right)^2
\]

Constraints:

```text
c_hb >= 0
c_bili >= 0
s0 > 0
0.2 <= b <= 3.0, if b is fitted
```

Potential solver choices:

- `scipy.optimize.least_squares` with bounds for physical constraints
- a faster staged solver if full per-pixel nonlinear optimization is too slow:
  - fit sample-level scattering first from ROI averages
  - then solve concentrations per pixel with fixed scattering

## Expected outputs

Match the existing solver contract as much as possible:

```python
concentrations: (H, W, N_components)
rmse_map: (H, W)
fitted_od or fitted_reflectance: existing panels expect fitted_od
solver_info: optional metadata for KM parameters and validation
```

Because existing panels expect `fitted_od`, convert fitted reflectance back to OD for compatibility:

\[
fitted\_od = -\log_{10}(R_{KM} + \epsilon)
\]

Also consider storing `fitted_reflectance` in the result payload for diagnostics.

## Validation plan

### Core unit tests

Add focused tests for:

1. `build_km_band_basis()` or equivalent band-averaging helper.
2. KM forward reflectance monotonicity:
   - increasing absorption lowers reflectance
   - increasing scattering raises reflectance for fixed absorption
3. Synthetic recovery:
   - generate reflectance from known `c_hb`, `c_bili`, `s0`
   - recover concentrations with bounded least squares
4. Solver output shape and finite values.

### DNG-derived phantom validation

Use:

```text
liquid_phantoms_for_unmixing_dng_cropped/
```

Validation should report, at minimum:

- sample-level median or ROI-mean `c_hb`
- sample-level median or ROI-mean `c_bili`
- bilirubin monotonicity A1 > A2 > A3 > A4 > A5 > A6
- bilirubin log2 slope near `-1` per sample step, if concentrations are comparable
- Hb approximately flat across A1-A6
- RMSE / residual spectra per sample

Acceptance criteria for initial exploratory implementation:

- no NaN/inf results
- bilirubin estimate decreases monotonically from A1 to A6
- Hb coefficient varies less than bilirubin across the series
- report relative trend error against the known halving series

Do not require absolute concentration accuracy in the first implementation unless unit conversions and calibration constants are settled.

## Integration points

### `app/core/processing.py`

Potential additions:

- `build_kubelka_munk_basis(...)`
- `kubelka_munk_reflectance(K, S, eps=...)`
- `solve_unmixing_kubelka_munk(...)`
- optional `validate_km_parameters(...)`

### `app/gui_qt/main_window.py`

Add solver option, likely:

```text
km
```

Add a pipeline branch that passes reflectance, not OD, to the KM solver.

Control visibility:

- background controls: probably disabled
- scattering controls: enabled or replaced with KM scattering controls
- iterative controls: disabled

### Export/panels

Prefer payload compatibility. Existing panels should still work from `concentrations`, `rmse_map`, and `fitted_od`. Add `fitted_reflectance` only as extra metadata/data.

## Risks and open questions

1. **Units:** The Agati spectra may not be scaled directly to µM-compatible KM absorption without a calibration factor.
2. **Only two blue/green bands:** Current wavelengths have limited Hb/bilirubin separation. Missing 470 nm and 530 nm bands are significant.
3. **KM coefficient meaning:** KM `K` and `S` are phenomenological and not exactly equal to physical `mu_a` and `mu_s'`.
4. **Per-pixel nonlinear fitting cost:** `scipy.optimize.least_squares` per pixel may be slow for full images.
5. **Reflectance calibration:** KM expects diffuse reflectance. Current reflectance is sample/ref/dark corrected, but instrument geometry and illumination diffuseness may affect absolute scaling.
6. **Bilirubin stability:** bilirubin spectra depend on solvent/binding/pH and photodegradation.

## Recommended staged implementation

### Stage 1 — offline/core prototype

- Implement KM forward model and bounded fit in `app/core/processing.py`.
- Write synthetic tests.
- Add a small script/test helper to run sample-level ROI or downsampled validation on the DNG-derived folder.

### Stage 2 — app integration

- Add `km` to solver combo.
- Wire the pipeline branch using reflectance input.
- Preserve result payload shape.

### Stage 3 — validation/reporting

- Add a validation report comparing A1-A6 estimates to known series.
- Include plots/tables for bilirubin halving and Hb constancy.

### Stage 4 — performance improvements

- Downsample or ROI-first testing.
- Fit scattering per sample, then concentrations per pixel.
- Consider lookup-table or vectorized approximation if needed.

## Implemented status on `feature/kubelka-munk-solver`

The initial branch implements the classic fixed-scattering KM baseline rather than a full nonlinear per-pixel `[c_hb, c_bili, s0]` fit.

Implemented path:

1. compute reflectance from sample/ref/dark;
2. validate reflectance in the physical KM domain `(0, 1)`;
3. convert to KM remission:

   ```text
   F(R) = (1 - R)^2 / (2R)
   ```

4. estimate absorption-like values using fixed reduced scattering:

   ```text
   mu_a ≈ F(R) * mu_s' / 2
   ```

5. solve nonnegative chromophore coefficients with NNLS against the band-averaged absorption matrix;
6. reconstruct fitted reflectance and convert it to `fitted_od` for GUI compatibility.

GUI integration:

- the solver combo includes `km`;
- KM uses fixed-scattering controls;
- background fitting is disabled for KM;
- `bili_agat.csv` negative extrapolated extinction is clipped in the KM absorption-matrix path.

## Validation outcome and bilirubin caveat

On the A1-A6 DNG-derived phantom series, KM+NNLS runs successfully but does **not** robustly recover bilirubin as a positive `bili_agat` chromophore map. This is consistent with a spectral-identifiability limitation of the current LED set: only the 450 nm and 517 nm bands strongly constrain Hb/bilirubin separation.

The practical bilirubin output for this dataset is therefore the separate two-band derived map:

```text
Bilirubin Index (OD450-OD517)
```

This map is a dimensionless diagnostic, not a physical concentration. Optional log-linear calibration is implemented separately in `app/core/calibration.py` and documented in `features/bilirubin_index_calibration.md`.
