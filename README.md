# Spectral Unmixing Application

A biomedical hyperspectral desktop application that processes raw multidimensional image cubes to automatically compute reflectance, optical density, and finally chromophore concentration maps.

By providing an intuitive, minimal Graphical User Interface (GUI), this application allows analyzing samples without deep coding knowledge.

## Capabilities

* **Automated Data Processing**: Point the application to a root directory containing subfolders for each raw sample alongside reference (`ref/`) and dark-current (`dark_ref/`) folders. 
* **Reflectance and Optical Density Extractor**: Performs pixelwise calculation from raw spectral intensity data directly.
* **Complex Overlap Matrix formulation**: Automatically loads target absorption spectra (`data/`). It creates an inclusive physical model handling LED bandwidth and wavelength-dependent penetration depth.
* **Fast Spectral Unmixing**: Employs an exact simple least-squares mathematical model completely vectorized over pixel dimensions, enabling fast solving per image.
* **Component Tracking**: Extracts five critical chromophores simultaneously (Oxyhemoglobin (HbO₂), Deoxyhemoglobin (Hb), Melanin, Bilirubin, and Water).
* **Derived Quality Metrics**: Computes aggregate metrics such as Total Hemoglobin (THb) and Oxygen Saturation (sO₂).
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

  *(Note: A base background row column is generally appended resulting in $N_{LED} \times 6$ mapping)*

### 4. Least Squares Optimization
Treating the system as an unconstrained inverse linear function over the LED bands, minimizing pixelwise L2 distances:

$$
\mathbf{y} = \mathbf{A}\mathbf{x}
$$

Where $\mathbf{y}$ is the recorded OD on LED bands. Unmixing simply demands resolving:

$$
\hat{x} = \arg\min_x \||Ax - y\||_2^2
$$

---

## Installation Instructions

The application requires **Python 3.8+** and utilizes standard scientific and interface UI libraries (`numpy`, `scipy`, `matplotlib`, `pillow`, `tkinter`).

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

1. Ensure the base python package, environments pack, and Tkinter GUI handlers are installed:
   ```bash
   sudo apt update
   sudo apt install python3 python3-venv python3-tk
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
If UI windows fail to appear, ensure that your OS graphics packages correctly bind Python `tkinter`. Linux machines often decouple UI bindings (`python3-tk` or `python-tkinter` depending upon RPM/Deb distributions). For macOS, native homebrew `python` typically packages tk implementations inherently.
