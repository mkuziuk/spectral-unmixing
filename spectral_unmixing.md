# Spectral Unmixing App (Hyperspectral Imaging)

Build a **spectral unmixing app** for biomedical hyperspectral data.

The app should take as input a **root folder** containing hyperspectral image cubes and automatically compute:

1. reflectance from raw image data using reference and dark-current folders  
2. optical density  
3. chromophore concentration maps using simple least-squares spectral unmixing  

The first version should be clean, robust, and minimal.

---

## Input Data Structure

The user provides a **single root directory**:
root/
- cube_1/
- cube_2/
- cube_3/
- ref/
- dark_ref/

Use photos_26-03-2026 as an example.


Rules:
- `ref/` → reflectance reference images (I₀)
- `dark_ref/` → dark-current images (I_dark)

---

## Data Folder (Chromophore & System Spectra)

The `data/` folder contains:
data/
- bilirubin_data.csv
- deoxyhemoglobin_data.csv
- leds_emission.csv
- melanin_data.csv
- oxyhemoglobin_data.csv
- penetration_depth_digitized.csv
- water_data.csv


### Description:
- `*_data.csv` → extinction / absorption spectra of chromophores
- `leds_emission.csv` → LED spectral emission profiles
- `penetration_depth_digitized.csv` → wavelength-dependent pathlength / penetration depth

These must be:
- loaded at runtime
- interpolated to the working wavelength grid

---

## Chromophores

Use these 5 chromophores:
- oxyhemoglobin (HbO₂)
- deoxyhemoglobin (Hb)
- melanin
- bilirubin
- water

---

## Reflectance Calculation

\[
R(\lambda) = \frac{I(\lambda) - I_{\text{dark}}(\lambda)}{I_0(\lambda) - I_{\text{dark}}(\lambda)}
\]

Pixelwise:

\[
R(i,j,\lambda) = \frac{I(i,j,\lambda) - I_{\text{dark}}(i,j,\lambda)}{I_0(i,j,\lambda) - I_{\text{dark}}(i,j,\lambda)}
\]

---

## Optical Density

\[
OD(\lambda) = -\log_{10}(R(\lambda) + \varepsilon)
\]

\[
OD(i,j,\lambda) = -\log_{10}(R(i,j,\lambda) + \varepsilon)
\]

---

## Overlap Matrix (CRITICAL PART)

Since illumination is not monochromatic (LEDs have bandwidth), the model must use **spectral overlap integration**.

### Step 1: Definitions

- \( \phi_n(\lambda) \) → emission spectrum of LED \(n\) (from `leds_emission.csv`)
- \( \varepsilon_k(\lambda) \) → chromophore spectrum (from data files)
- \( l(\lambda) \) → penetration depth / pathlength (from `penetration_depth_digitized.csv`)

---

### Step 2: Compute overlap extinction coefficients

For each LED \(n\) and chromophore \(k\):

\[
\varepsilon_{k}^{(n)} = \int \phi_n(\lambda)\,\varepsilon_k(\lambda)\,d\lambda
\]

---

### Step 3: Compute overlap pathlength

\[
l^{(n)} = \int \phi_n(\lambda)\,l(\lambda)\,d\lambda
\]

---

### Step 4: Build overlap matrix

For each LED \(n\):

\[
A_{n,k} = l^{(n)} \cdot \varepsilon_{k}^{(n)}
\]

Final matrix:

\[
A \in \mathbb{R}^{N_{LED} \times 5}
\]

Columns:
- HbO₂
- Hb
- melanin
- bilirubin
- water

Rows:
- LEDs

Add Background = 100.0 to the overlap matrix as the last column.

---

## Linear Model (Using Overlap Matrix)

Instead of wavelength-based model, use LED-based system:

\[
\mathbf{y} = \mathbf{A}\mathbf{x}
\]

Where:
- \(y \in \mathbb{R}^{N_{LED}}\) → OD at LED bands
- \(A\) → overlap matrix
- \(x\) → chromophore concentrations

---

## Optimization

\[
\hat{x} = \arg\min_x \|Ax - y\|_2^2
\]

Use:
- `numpy.linalg.lstsq`

---

## Pixelwise Pipeline

For each sample:

1. Load sample cube  
2. Load `ref` and `dar_ref`  
3. Compute reflectance  
4. Compute OD  
5. Reduce spectrum to LED bands (or already LED-based)  
6. Compute overlap matrix \(A\) once  
7. Solve least squares per pixel  
8. Generate maps  

---

## Derived Maps

\[
THb = HbO2 + Hb
\]

\[
sO_2 = \frac{HbO2}{HbO2 + Hb + \varepsilon}
\]


---

## Quality Control

\[
\hat{y} = A\hat{x}
\]

\[
RMSE = \sqrt{\frac{1}{N}\|y - \hat{y}\|^2}
\]

Warn if:
- bad denominator
- negative reflectance
- NaNs
- rank deficiency

---

## Code Structure

load_data_folder()
load_chromophore_data()
load_led_emission()
load_penetration_depth()

compute_reflectance()
compute_optical_density()

compute_overlap_matrix()
solve_least_squares_per_pixel()

compute_maps()
save_outputs()


---

## UI

The UI should be minimal, clean, and focused on the workflow:

### 1. Input
- Folder picker to select the **root directory**
- Automatically detect:
  - sample folders
  - `ref` and `dar_ref`
- Display detected wavelengths and number of LEDs / bands

---

### 2. Processing Control
- Button: **"Run Unmixing"**
- Progress indicator:
  - current sample being processed
  - percentage / progress bar

---

### 3. Visualization

#### Sample selection
- Dropdown or list to choose processed sample

#### Image display
- Show:
  - raw image (grayscale or RGB preview)
  - reflectance image
  - optical density image

#### Chromophore maps
- Display maps for:
  - HbO₂
  - Hb
  - melanin
  - bilirubin
  - water
- Include:
  - colorbars
  - consistent scaling option

#### Derived maps
- THb
- StO₂
- residual map

---

### 4. Pixel Inspector (important)
- Click on image → show:
  - measured OD spectrum
  - fitted OD spectrum
  - residual
  - estimated concentrations

---

### 5. Diagnostics Panel
- Display:
  - RMSE (global or per pixel)
  - warnings (bad pixels, NaNs, etc.)
- Option to visualize:
  - residual histogram
  - mask of low-quality fits

---

### 6. Export
- Button: **"Save Results"**
- Save:
  - maps (PNG)
  - arrays (NPY / CSV)
  - metadata

---

### 7. Optional (nice-to-have)
- Toggle:
  - log scale / linear scale
- Normalize maps toggle
- Ability to inspect wavelength / LED contributions

## Important Notes

- Interpolate ALL spectra to common wavelength grid
- Normalize LED spectra before integration
- Use numerical integration (trapezoidal rule)
- Precompute overlap matrix once
- Vectorize pixel solving

---

## Version 1 Limitations

No:
- NNLS
- regularization
- scattering models
- nonlinear fitting

---

## Final Goal

**Folder → Reflectance → Optical Density → Overlap Matrix → Least Squares → Chromophore Maps**