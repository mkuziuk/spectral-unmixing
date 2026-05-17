# Spectral Unmixing Application

[![Download Latest Release](https://img.shields.io/badge/Download-Latest%20Release-blue?style=for-the-badge&logo=github)](https://github.com/mkuziuk/spectral-unmixing/releases/latest)

<div align="center">
<img src="assets/before_unmixing.png" alt="Before Unmixing" width="45%"/>
<img src="assets/after_unmixing.png" alt="After Unmixing" width="45%"/>
</div>

A biomedical hyperspectral desktop application that processes raw multidimensional image cubes to automatically compute reflectance, optical density, and finally chromophore concentration maps.

By providing an intuitive, minimal Graphical User Interface (GUI), this application allows analyzing samples without deep coding knowledge.

## Release 0.2.5

Release `0.2.5` adds the Kubelka-Munk solver branch features while keeping **PySide6** as the single supported desktop UI.

- `python app/main.py` launches the PySide6 application directly
- solver options now include `km` for a fixed-scattering Kubelka-Munk reflectance workflow
- the toolbar can compute a model-free **Bilirubin Index** derived map (`OD450 - OD517`)
- optional bilirubin calibration JSON files can create domain-calibrated diagnostic estimate maps
- the Chromophore Bar Charts tab can show bilirubin diagnostic summaries when bilirubin derived maps are present
- release packaging and documentation target the Qt application only

## Capabilities

* **Automated Data Processing**: Point the application to a root directory containing subfolders for each raw sample alongside reference (`ref/`) and dark-current (`dark_ref/`) folders. 
* **Reflectance and Optical Density Extractor**: Performs pixelwise calculation from raw spectral intensity data directly.
* **Complex Overlap Matrix formulation**: Automatically loads target absorption spectra (`data/chromophores/`). It creates an inclusive physical model handling LED bandwidth and wavelength-dependent penetration depth.
* **Fast Spectral Unmixing**: Employs vectorized least-squares and NNLS models over pixel dimensions, enabling fast solving per image.
* **Kubelka-Munk Solver**: Provides an optional `km` solver that converts diffuse reflectance through the Kubelka-Munk remission function before NNLS fitting with a fixed reduced-scattering profile.
* **Dynamic Component Tracking**: Automatically identifies and extracts critical chromophores based on the contents of the `data/chromophores/` directory. Users can flexibly add or alter unmixing targets (such as HbO₂, Hb, Melanin, Bilirubin, and Water) simply by dropping custom `.csv` spectra files into this folder without needing to modify the codebase.
* **Custom Data Folder Selection**: Users can select a custom data folder via the UI to support different experimental setups or shared reference data. The application validates the folder structure and provides clear error messages for missing required files.
* **Derived Quality Metrics**: Computes aggregate metrics such as Total Hemoglobin (THb), Oxygen Saturation (StO₂), and optional bilirubin diagnostic maps.
* **Bilirubin Diagnostic Index**: Computes a model-free two-band map `OD450 - OD517`, with optional Hb correction and optional log-linear calibration from JSON. This is a domain diagnostic, not a physical concentration map.
* **Statistical Analysis**: View summary statistics (mean and median reflectance) per hyperspectral cube across all wavelength bands.
* **Interactive Data Inspector Panel**: Includes visual diagnostics and an interactive pixel inspector—allowing you to click on any pixel in the loaded cube to see measured versus fitted optical density spectra, estimated concentrations, residuals, and general pixel RMSE.
* **Exporting**: Save unmixed component maps (.png), raw arrays (.npy or .csv) and metadata back to your file system.

## The Math and Physics Model

At its core, the unmixing engine translates pixel intensities at varied light wavelengths to specific chromophore densities. 

### 1. Reflectance ($R$)
Using specific `ref/` and `dark_ref/` reference images, the pixelwise directional tissue reflectance is computed:

$$
R(i,j,\lambda) = \frac{I(i,j,\lambda) - I_{\text{dark}}(i,j,\lambda)}{I_0(i,j,\lambda) - I_{\text{dark}}(i,j,\lambda)}
$$

### 2. Optical Density ($OD$)
Optical density transitions logarithmic-scaled reflectance representations ensuring linear dependence during subsequent fitting:

$$
OD(i,j,\lambda) = -\log_{10}(R(i,j,\lambda) + \varepsilon)
$$

### 3. Spectral Overlap Integration Formulation
Standard pseudo-inverse models assume pure monochromatic illumination. Since LEDs possess inherent energy distribution bandwidths, the engine evaluates spectral overlap integration dynamically:

* **Overlap Extinction Coefficient**: For a given LED ($n$) and individual chromophore ($k$): 

  $$\varepsilon_k^{(n)} = \int \phi_n(\lambda)\varepsilon_k(\lambda)d\lambda$$

* **Overlap Pathlength**: We modulate theoretical estimations via simulated wavelength-correlated penetration distributions $l(\lambda)$: 

  $$l^{(n)} = \int \phi_n(\lambda)l(\lambda)d\lambda$$

* **Overlap Component Matrix**: Building an inclusive linear target constraint formulation ($N_{LED} \times 5$ parameters): 

  $$A_{n,k} = l^{(n)} \cdot \varepsilon_k^{(n)}$$

  (Note: A base background row column is generally appended resulting in $N_{LED} \times 6$ mapping)

### 4. Least Squares Optimization
Treating the system as an unconstrained inverse linear function over the LED bands, minimizing pixelwise L2 distances:

$$
\mathbf{y} = \mathbf{A}\mathbf{x}
$$

Where $\mathbf{y}$ is the recorded OD on LED bands. Unmixing simply demands resolving:

$$
\hat{x} = \arg\min_x \lvert Ax - y\rvert_2^2
$$

### 5. Kubelka-Munk Reflectance Solver
The optional `km` solver works from reflectance rather than directly fitting optical density. It uses the Kubelka-Munk remission function:

$$
F(R) = \frac{(1 - R)^2}{2R}
$$

With a fixed reduced-scattering profile $\mu_s'(\lambda)$, the solver estimates an absorption-like spectrum:

$$
\mu_a(\lambda) \approx \frac{F(R(\lambda))\,\mu_s'(\lambda)}{2}
$$

It then solves the chromophore coefficients by NNLS against the band-averaged absorption matrix. In the GUI, `km` uses the fixed-scattering controls and disables the background column.

### 6. Bilirubin Index and Forward Calibration
The optional bilirubin diagnostic map is computed from reflectance as:

$$
BI = OD_{450} - OD_{517} = \log_{10}\left(\frac{R_{517}}{R_{450}}\right)
$$

An optional Hb correction can be applied as:

$$
BI_{corrected} = OD_{450} - OD_{517} - k\,OD_{671}
$$

A calibration JSON can convert the index to a domain-calibrated estimate using a log-linear model:

$$
BI = \alpha\log_{10}([bilirubin]) + \beta
$$

⚠️ This bilirubin output is a two-band diagnostic. It is not a spectral-unmixing concentration and should not be treated as a validated physical bilirubin concentration unless independently calibrated and validated for the same imaging setup and phantom domain.

---

## Installation Instructions

The application requires **Python 3.8+** and utilizes standard scientific and interface UI libraries (`numpy`, `scipy`, `matplotlib`, `pillow`, `PySide6`).

### Windows

1. **Install Python** (3.8 or newer) from [python.org](https://www.python.org/). *Ensure you check "Add Python to PATH" during installation.*
2. **Download/Clone** this repository and extract it to a preferred folder.
3. Open **Command Prompt** or **PowerShell** and navigate to the project directory.
4. Create a virtual environment:
   ```cmd
   python -m venv .venv
   ```
5. Activate the virtual environment:
   ```cmd
   .venv\Scripts\activate
   ```
6. Install required dependencies:
   ```cmd
   pip install -r requirements.txt
   ```
   *(Alternatively, install as a package: `pip install .`)*
7. Run the application:
   ```cmd
   python app/main.py
   ```

### macOS

1. **Install Python** (3.8 or newer) via [Homebrew](https://brew.sh/): `brew install python` or using the official installer. 
2. Open **Terminal** and navigate to the downloaded project footprint. 
3. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   ```
4. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```
5. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Alternatively, install as a package: `pip install .`)*
6. Run the application:
   ```bash
   python app/main.py
   ```

### Linux (Ubuntu / Debian)

1. Ensure the base Python and virtual environment packages are installed:
   ```bash
   sudo apt update
   sudo apt install python3 python3-venv
   ```
2. Open your terminal emulator and navigate to the target directory.
3. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   ```
4. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```
5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Alternatively install as a package: `pip install .`)*
6. **Execution**: You can either target the main application runner explicitly, or use the pre-packaged shell hook:
   ```bash
   ./run.sh
   # Or alternatively: python app/main.py
   ```

### Troubleshooting
If the Qt UI fails to launch, confirm that `PySide6` installed successfully in your active environment. On Linux, make sure your machine has the system display libraries needed by Qt and that you are starting the app inside a graphical session.

## Custom Data Folder Support

### Folder Structure Requirements

When selecting a custom data folder via the **🧪 Select Data Folder** button in the UI, the folder must contain the following structure:

```
custom_data_folder/
├── leds_emission.csv              # LED emission spectra (required)
├── penetration_depth*.csv         # Penetration depth data (required, see note below)
├── chromophores/                  # Directory with chromophore spectra (required)
│   ├── HbO2.csv
│   ├── Hb.csv
│   └── ... (more .csv files)
└── calibrations/                  # Optional bilirubin calibration JSON files
    └── bilirubin_a1a6_log_linear.json
```

**Required Files:**

| File | Description |
|------|-------------|
| `leds_emission.csv` | CSV with wavelength column and LED emission intensity columns |
| `penetration_depth*.csv` | Penetration depth vs. wavelength (at least one required) |
| `chromophores/` | Directory containing at least one `.csv` file with extinction coefficients |

**Penetration Depth File Selection:**
- If `penetration_depth_digitized.csv` exists, it will be selected automatically
- Otherwise, the lexicographically first `penetration_depth*.csv` file is chosen
- **Recommendation**: Use `penetration_depth_digitized.csv` for consistency when multiple options exist

### Basic Usage Flow

1. Launch the application: `python app/main.py`
2. Click **📂 Select Root Folder** to choose your sample data directory (containing image cubes, `ref/`, and `dark_ref/`)
3. Click **🧪 Select Data Folder** to choose a custom data folder with required files
4. Verify the data source label shows your custom folder
5. Select desired chromophores from the **Chromophores** menu
6. Adjust solver (`ls`, `nnls`, `mu_a`, `iterative`, or `km`) and background/scattering settings if needed
7. Optionally enable **Bilirubin Index** to compute the `OD450 - OD517` derived map; leave `k_corr` empty unless your calibration was fitted with the same correction
8. Optionally enable **Apply Calibration**, click **Load Calibration...**, and choose a calibration JSON such as `data/calibrations/bilirubin_a1a6_log_linear.json`
9. Click **▶ Run Unmixing** to process all samples
10. Use the tabs (Maps, Pixel Inspector, Diagnostics, Reflectance Stats, Chromophore Bar Charts) to view results. Bilirubin index/calibration maps appear under **Derived Maps**; the Bar Charts tab adds a separate diagnostic subplot when available.
11. Click **💾 Save Results** to export component maps, derived maps, arrays, and metadata

### Common Errors and Solutions

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `Required file 'leds_emission.csv' not found` | Missing LED emission file | Add `leds_emission.csv` to your data folder |
| `Required file 'penetration_depth*.csv' not found` | No penetration depth file | Add at least one `penetration_depth*.csv` file |
| `Required directory 'chromophores/' not found` | Missing chromophores directory | Create `chromophores/` and add `.csv` files |
| `Directory 'chromophores/' contains no .csv files` | Empty chromophores directory | Add at least one `.csv` file with extinction coefficients |
| `LED {wl} nm not found in ...` | Wavelength mismatch | Ensure LED wavelengths in `leds_emission.csv` match your image cube filenames |
| `Bilirubin index requires 450 nm and 517 nm bands` | Required bands missing | Use an image set containing both 450 nm and 517 nm bands |
| `Bilirubin index Hb correction requires a 671 nm reference band` | `k_corr` was entered but 671 nm is unavailable | Leave `k_corr` empty or use a dataset with 671 nm |
| `Enable Bilirubin Index before applying calibration` | Calibration was checked without the index | Check **Bilirubin Index** first |
| `Load a calibration file to apply bilirubin calibration` | Calibration was checked but no JSON was loaded | Click **Load Calibration...** and choose a calibration JSON |
| `Bilirubin index k correction must be a number` | Invalid `k_corr` input | Enter a non-negative number or leave the field empty |

## Kubelka-Munk Solver Notes

The **Solver** dropdown includes `km`, a Kubelka-Munk diffuse-reflectance alternative to the OD overlap-matrix solvers. It is useful for testing physically motivated reflectance-to-absorption behavior in scattering phantoms.

Important behavior:

- `km` uses the absorption matrix, not the OD overlap matrix.
- `km` uses the fixed-scattering toolbar parameters.
- background fitting is disabled for `km`.
- extinction values extrapolated below zero are clipped for the KM path.

Known bilirubin limitation: with the current 8-band LED set (`450, 517, 671, 775, 803, 851, 888, 939 nm`), KM+NNLS does **not** robustly recover `bili_agat` as a chromophore concentration map in the A1-A6 phantoms. Seeing a zero-valued `bili_agat` map can be expected. Use the **Bilirubin Index** derived map for practical bilirubin contrast.

## Bilirubin Diagnostic Index

Enable the toolbar checkbox:

```text
Bilirubin Index
```

to compute a derived map:

```text
Bilirubin Index (OD450-OD517)
```

This map is dimensionless. Higher values indicate stronger bilirubin-like absorption near 450 nm relative to 517 nm within the same imaging/calibration domain.

The optional `k_corr` text input applies:

```text
OD450 - OD517 - k_corr * OD671
```

Leave `k_corr` empty for the default raw index. Only use a non-empty `k_corr` when your calibration was fitted with the same correction. The shipped calibration uses `k_corr = None`.

## Bilirubin Calibration Files

Calibration is optional and uses JSON files. The shipped A1-A6 phantom calibration is located at:

```text
data/calibrations/bilirubin_a1a6_log_linear.json
```

To use it in the UI:

1. check **Bilirubin Index**;
2. check **Apply Calibration**;
3. click **Load Calibration...**;
4. select `data/calibrations/bilirubin_a1a6_log_linear.json`;
5. run the pipeline again.

This adds derived maps:

```text
Bilirubin est. (calibrated, see disclaimer)
Bilirubin est. clamp mask
```

The clamp mask indicates where the calibrated estimate was clipped to the calibration domain boundary. Large clamped regions mean the calibration is being applied outside its useful domain.

To generate a calibration JSON from a phantom series with known bilirubin values, use:

```bash
python scripts/bilirubin_index_report.py \
  --root /path/to/phantom_root \
  --save-calibration my_bilirubin_calibration.json
```

You can also apply an existing calibration in the report script:

```bash
python scripts/bilirubin_index_report.py \
  --root /path/to/phantom_root \
  --load-calibration data/calibrations/bilirubin_a1a6_log_linear.json
```

### Calibration caveats

- The shipped calibration was fitted on the A1-A6 DNG-derived Lipofundin/Hb/bilirubin phantom series.
- Calibration domain: approximately `8.4–270 µM` bilirubin with Hb fixed at `100 µM`, using the same camera/LED processing setup.
- The in-sample fit is strong (`R² ≈ 0.94`), but leave-one-out validation is poor/negative on the six-point set.
- Treat calibrated maps as domain-limited diagnostic estimates, not validated physical concentrations.

## Export Metadata for Bilirubin Maps

When bilirubin index or calibrated estimate maps are exported, each sample's `metadata.json` includes bilirubin-specific notes:

- `bilirubin_index_note` — states that `OD450 - OD517` is a dimensionless diagnostic.
- `bilirubin_calibration` — stores calibration coefficients, fit quality, calibration domain, validation status, disclaimer, and clamp counts when applicable.

Always share `metadata.json` with exported bilirubin maps so downstream users see the calibration domain and disclaimer.
