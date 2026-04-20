"""
I/O module for spectral unmixing.

Handles:
- Folder structure detection (samples, ref, dark_ref)
- Image cube loading (JPEG/DNG → grayscale float64 arrays)
- Chromophore spectra loading from CSV
- LED emission spectra loading
- Penetration depth loading
"""

import os
import re
import numpy as np
from PIL import Image
import csv
try:
    import rawpy
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    rawpy = None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_data_directory(data_dir: str) -> None:
    """
    Validate that the data directory contains required files and folders.

    Required items:
        - leds_emission.csv
        - penetration_depth*.csv (at least one, including penetration_depth_digitized.csv)
        - chromophores/ directory with at least one .csv file

    Parameters
    ----------
    data_dir : str
        Path to the data directory to validate.

    Raises
    ------
    FileNotFoundError
        If required files or directories are missing.
    ValueError
        If the chromophores directory exists but contains no CSV files.
    """
    # Check leds_emission.csv
    leds_path = os.path.join(data_dir, "leds_emission.csv")
    if not os.path.isfile(leds_path):
        raise FileNotFoundError(
            f"Required file 'leds_emission.csv' not found in {data_dir}"
        )

    # Check penetration_depth*.csv (wildcard support)
    penetration_files = [
        f for f in os.listdir(data_dir)
        if f.startswith("penetration_depth") and f.endswith(".csv") and os.path.isfile(os.path.join(data_dir, f))
    ]
    if not penetration_files:
        raise FileNotFoundError(
            f"Required file 'penetration_depth*.csv' not found in {data_dir}"
        )

    # Check chromophores directory
    chrom_dir = os.path.join(data_dir, "chromophores")
    if not os.path.isdir(chrom_dir):
        raise FileNotFoundError(
            f"Required directory 'chromophores/' not found in {data_dir}"
        )
    chrom_files = [f for f in os.listdir(chrom_dir) if f.endswith(".csv") and not f.startswith(".")]
    if not chrom_files:
        raise ValueError(
            f"Directory 'chromophores/' in {data_dir} contains no .csv files"
        )


def _find_penetration_depth_file(data_dir: str) -> str:
    """
    Find penetration depth file with deterministic selection.

    Priority:
        1. penetration_depth_digitized.csv (exact match)
        2. Lexicographically first penetration_depth*.csv

    Parameters
    ----------
    data_dir : str
        Path to the data directory.

    Returns
    -------
    str
        Absolute path to the selected penetration depth file.
    """
    all_files = [
        f for f in os.listdir(data_dir)
        if f.startswith("penetration_depth") and f.endswith(".csv") and os.path.isfile(os.path.join(data_dir, f))
    ]
    
    # Prefer exact match
    exact = os.path.join(data_dir, "penetration_depth_digitized.csv")
    if exact in [os.path.join(data_dir, f) for f in all_files]:
        return exact
    
    # Otherwise lexicographically first
    return os.path.join(data_dir, sorted(all_files)[0])


# ---------------------------------------------------------------------------
# Folder detection
# ---------------------------------------------------------------------------

def detect_folders(root_dir: str) -> dict:
    """
    Scan root directory and return structure info.

    Returns
    -------
    dict with keys:
        samples   : list[str]  – absolute paths of sample folders
        ref_dir   : str        – absolute path to reference folder
        dark_ref_dir : str     – absolute path to dark-reference folder
        wavelengths : list[int] – sorted LED wavelengths (nm) parsed from filenames
        sample_names : list[str] – just the folder basenames
    """
    entries = sorted(os.listdir(root_dir))
    ref_dir = None
    dark_ref_dir = None
    samples = []
    sample_names = []

    for entry in entries:
        full = os.path.join(root_dir, entry)
        if not os.path.isdir(full):
            continue
        low = entry.lower()
        if low == "ref":
            ref_dir = full
        elif low == "dark_ref":
            dark_ref_dir = full
        else:
            samples.append(full)
            sample_names.append(entry)

    if ref_dir is None:
        raise FileNotFoundError(f"No 'ref/' folder found in {root_dir}")
    if dark_ref_dir is None:
        raise FileNotFoundError(f"No 'dark_ref/' folder found in {root_dir}")

    # Parse wavelengths from the first sample (or ref) folder
    source = samples[0] if samples else ref_dir
    wavelengths = _parse_wavelengths_from_folder(source)

    return {
        "samples": samples,
        "sample_names": sample_names,
        "ref_dir": ref_dir,
        "dark_ref_dir": dark_ref_dir,
        "wavelengths": wavelengths,
    }


def _parse_wavelengths_from_folder(folder: str) -> list:
    """Extract wavelength integers from filenames like '450nm_...' """
    pattern = re.compile(r"^(\d+)nm[_.]")
    wls = set()
    for fname in os.listdir(folder):
        m = pattern.match(fname)
        if m:
            wls.add(int(m.group(1)))
    return sorted(wls)


# ---------------------------------------------------------------------------
# Image cube loading
# ---------------------------------------------------------------------------

def load_image_cube(folder: str, wavelengths: list) -> np.ndarray:
    """
    Load images from *folder* and stack into a cube.

    Parameters
    ----------
    folder : str
        Directory containing ``<wavelength>nm_*.jpg`` or ``<wavelength>nm_*.dng`` files.
    wavelengths : list[int]
        Sorted wavelengths to load.

    Returns
    -------
    cube : np.ndarray, shape (H, W, N_bands), dtype float64
        Grayscale intensity values in [0, 255].
    """
    slices = []
    for wl in wavelengths:
        path = _find_image_for_wavelength(folder, wl)
        gray = _load_image_as_grayscale(path)
        slices.append(gray)
    return np.stack(slices, axis=-1)  # (H, W, N_bands)


def _load_image_as_grayscale(path: str) -> np.ndarray:
    """
    Load an image file and convert to grayscale.
    
    Supports both JPEG/PNG (via PIL) and DNG (via rawpy) formats.
    For color images, averages RGB channels to produce grayscale.
    
    Parameters
    ----------
    path : str
        Path to the image file.
        
    Returns
    -------
    gray : np.ndarray, shape (H, W), dtype float64
        Grayscale image array.
    """
    ext = os.path.splitext(path)[1].lower()
    
    if ext == '.dng':
        if rawpy is None:
            raise ImportError(
                "rawpy is required to load .dng images. "
                "Install optional dependency 'rawpy' or use non-DNG inputs."
            )
        # Load DNG using rawpy
        with rawpy.imread(path) as raw:
            # Postprocess to get RGB image
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=False,
                no_auto_bright=True,
                output_bps=16
            )
        arr = np.asarray(rgb, dtype=np.float64)
        # Average RGB channels
        gray = arr.mean(axis=2)
        # Scale from 16-bit range to match 8-bit behavior [0, 255]
        gray = gray / 65535.0 * 255.0
    else:
        # Load JPEG/PNG using PIL
        img = Image.open(path).convert("RGB")
        arr = np.asarray(img, dtype=np.float64)
        gray = arr.mean(axis=2)  # average RGB channels
    
    return gray


def _find_image_for_wavelength(folder: str, wl: int) -> str:
    """Find the file matching a given wavelength in a folder."""
    prefix = f"{wl}nm"
    for fname in os.listdir(folder):
        if fname.startswith(prefix):
            return os.path.join(folder, fname)
    raise FileNotFoundError(
        f"No image found for wavelength {wl} nm in {folder}"
    )


# ---------------------------------------------------------------------------
# Chromophore spectra
# ---------------------------------------------------------------------------




def load_chromophore_spectra(data_dir: str) -> dict:
    """
    Load all chromophore extinction coefficient spectra.

    Returns
    -------
    dict  {name: (wavelengths_array, coefficients_array)}
    """
    spectra = {}
    chrom_dir = os.path.join(data_dir, "chromophores")
    if os.path.isdir(chrom_dir):
        for filename in sorted(os.listdir(chrom_dir)):
            if filename.endswith(".csv") and not filename.startswith("."):
                name = os.path.splitext(filename)[0]
                path = os.path.join(chrom_dir, filename)
                wls, coeffs = _load_two_column_csv(path)
                if wls and coeffs:
                    spectra[name] = (np.asarray(wls), np.asarray(coeffs))
    return spectra


def _load_two_column_csv(path: str):
    """Load a CSV with a header row and two numeric columns."""
    wavelengths = []
    values = []
    with open(path, "r") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header
        for row in reader:
            if len(row) < 2:
                continue
            wavelengths.append(float(row[0]))
            values.append(float(row[1]))
    return wavelengths, values


# ---------------------------------------------------------------------------
# LED emission
# ---------------------------------------------------------------------------

def load_led_emission(data_dir: str, led_wavelengths: list):
    """
    Load LED spectral emission profiles.

    Parameters
    ----------
    data_dir : str
        Path to the ``data/`` folder.
    led_wavelengths : list[int]
        LED centre wavelengths (e.g. [450, 517, ...]).

    Returns
    -------
    common_wl : np.ndarray, shape (N,)
        Wavelength axis from the CSV.
    emission : dict  {led_nm: np.ndarray shape (N,)}
        Emission intensity for each LED.
    """
    path = os.path.join(data_dir, "leds_emission.csv")
    with open(path, "r") as f:
        reader = csv.reader(f)
        header = next(reader)
        # header: wavelength, 450, 517, 671, ...
        led_cols = [str(w) for w in led_wavelengths]
        col_indices = {}
        for lw in led_cols:
            if lw in header:
                col_indices[int(lw)] = header.index(lw)
            else:
                raise ValueError(
                    f"LED {lw} nm not found in {path}. "
                    f"Available: {header[1:]}"
                )

        rows_wl = []
        rows_data = {k: [] for k in col_indices}
        for row in reader:
            if len(row) < 2:
                continue
            rows_wl.append(float(row[0]))
            for led_nm, idx in col_indices.items():
                rows_data[led_nm].append(float(row[idx]))

    common_wl = np.asarray(rows_wl)
    emission = {k: np.asarray(v) for k, v in rows_data.items()}
    return common_wl, emission


# ---------------------------------------------------------------------------
# Penetration depth
# ---------------------------------------------------------------------------

def load_penetration_depth(data_dir: str):
    """
    Load penetration depth / pathlength data.

    Loads from penetration_depth_digitized.csv if present, otherwise
    loads from the lexicographically first penetration_depth*.csv file.

    Parameters
    ----------
    data_dir : str
        Path to the data directory.

    Returns
    -------
    wavelengths : np.ndarray
    depths : np.ndarray
    """
    path = _find_penetration_depth_file(data_dir)
    wls, depths = _load_two_column_csv(path)
    return np.asarray(wls), np.asarray(depths)
