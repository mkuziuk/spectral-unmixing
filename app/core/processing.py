"""
Processing module for spectral unmixing.

Pipeline:
    raw cube → reflectance → optical density → overlap matrix → least-squares → maps
"""

import numpy as np
from scipy.interpolate import interp1d


# ---------------------------------------------------------------------------
# Reflectance
# ---------------------------------------------------------------------------

def compute_reflectance(
    sample_cube: np.ndarray,
    ref_cube: np.ndarray,
    dark_cube: np.ndarray,
    eps: float = 1e-10,
) -> np.ndarray:
    """
    Pixelwise reflectance.

    R(i,j,λ) = (I - I_dark) / (I_0 - I_dark + eps)

    Parameters
    ----------
    sample_cube, ref_cube, dark_cube : (H, W, N_bands)

    Returns
    -------
    reflectance : (H, W, N_bands)
    """
    numerator = sample_cube - dark_cube
    denominator = ref_cube - dark_cube + eps
    reflectance = numerator / denominator
    return reflectance


# ---------------------------------------------------------------------------
# Optical density
# ---------------------------------------------------------------------------

def compute_optical_density(
    reflectance: np.ndarray,
    eps: float = 1e-10,
) -> np.ndarray:
    """
    OD(i,j,λ) = -log10(R + eps)
    """
    return -np.log10(np.clip(reflectance, eps, None))


# ---------------------------------------------------------------------------
# Overlap matrix
# ---------------------------------------------------------------------------

def build_overlap_matrix(
    led_emission_wl: np.ndarray,
    led_emission: dict,
    chromophore_spectra: dict,
    penetration_wl: np.ndarray,
    penetration_depth: np.ndarray,
    led_wavelengths: list,
) -> np.ndarray:
    """
    Build the overlap matrix A ∈ R^{N_LED × 6}.

    Steps:
        1. Define a common wavelength grid from the LED emission data.
        2. Interpolate all spectra onto this grid.
        3. Normalize each LED spectrum (area = 1).
        4. Compute overlap extinction: eps_k^n = ∫ phi_n(λ) * eps_k(λ) dλ
        5. Compute overlap pathlength: l^n = ∫ phi_n(λ) * l(λ) dλ
        6. A[n,k] = l^n * eps_k^n
        7. Append background column (100.0).

    Parameters
    ----------
    led_emission_wl : (N,) wavelength axis of LED data
    led_emission : dict {led_nm: (N,) emission array}
    chromophore_spectra : dict {name: (wl_array, coeff_array)}
    penetration_wl, penetration_depth : arrays
    led_wavelengths : list[int], ordered LED centre wavelengths

    Returns
    -------
    A : np.ndarray, shape (N_LED, 6)
        Columns: HbO2, Hb, melanin, bilirubin, water, background
    chromophore_names : list[str]
        Column labels (without background)
    """
    common_wl = led_emission_wl  # use LED wavelength grid as common grid

    # Interpolate penetration depth onto common grid
    f_depth = interp1d(
        penetration_wl, penetration_depth,
        kind="linear", fill_value="extrapolate", bounds_error=False,
    )
    depth_interp = f_depth(common_wl)

    # Interpolate chromophore spectra onto common grid
    chromophore_names = ["HbO2", "Hb", "melanin", "bilirubin", "water"]
    chrom_interp = {}
    for name in chromophore_names:
        wl, coeff = chromophore_spectra[name]
        f = interp1d(
            wl, coeff,
            kind="linear", fill_value="extrapolate", bounds_error=False,
        )
        chrom_interp[name] = f(common_wl)

    n_leds = len(led_wavelengths)
    n_chrom = len(chromophore_names)
    A = np.zeros((n_leds, n_chrom + 1))  # +1 for background

    for i, led_nm in enumerate(led_wavelengths):
        phi = led_emission[led_nm].copy()

        # Normalize LED spectrum (area = 1)
        area = np.trapezoid(phi, common_wl)
        if area > 0:
            phi /= area

        # Overlap pathlength: l^n = ∫ phi_n(λ) * l(λ) dλ
        l_n = np.trapezoid(phi * depth_interp, common_wl)

        # Overlap extinction for each chromophore
        for j, name in enumerate(chromophore_names):
            eps_k_n = np.trapezoid(phi * chrom_interp[name], common_wl)
            A[i, j] = l_n * eps_k_n

        # Background column
        A[i, -1] = 100.0

    return A, chromophore_names


# ---------------------------------------------------------------------------
# Least-squares unmixing
# ---------------------------------------------------------------------------

def solve_unmixing(
    od_cube: np.ndarray,
    A: np.ndarray,
) -> tuple:
    """
    Pixelwise least-squares spectral unmixing.

    For each pixel: min_x ||Ax - y||^2  via numpy.linalg.lstsq

    Parameters
    ----------
    od_cube : (H, W, N_bands) optical density
    A : (N_bands, N_chromophores+1) overlap matrix

    Returns
    -------
    concentrations : (H, W, N_chromophores+1)
    residual_map : (H, W) RMSE per pixel
    fitted_od : (H, W, N_bands) reconstructed OD
    """
    H, W, N = od_cube.shape
    n_components = A.shape[1]

    # Reshape to (N_pixels, N_bands)
    Y = od_cube.reshape(-1, N)  # (H*W, N)

    # Solve: A @ X.T = Y.T  →  X.T = lstsq(A, Y.T)
    # numpy lstsq solves A @ x = b for each column of b
    X, residuals, rank, sv = np.linalg.lstsq(A, Y.T, rcond=None)
    # X shape: (n_components, H*W)

    concentrations = X.T.reshape(H, W, n_components)

    # Compute fitted OD and residuals
    fitted = (A @ X).T.reshape(H, W, N)  # (H, W, N)
    residual_per_pixel = od_cube - fitted
    rmse_map = np.sqrt(np.mean(residual_per_pixel ** 2, axis=2))

    return concentrations, rmse_map, fitted


# ---------------------------------------------------------------------------
# Derived maps
# ---------------------------------------------------------------------------

def compute_derived_maps(
    concentrations: np.ndarray,
    chromophore_names: list,
    eps: float = 1e-10,
) -> dict:
    """
    Compute THb and sO2 maps.

    Parameters
    ----------
    concentrations : (H, W, N_components)
    chromophore_names : list[str] – column names (first entries)

    Returns
    -------
    dict with 'THb' and 'sO2' arrays (H, W)
    """
    idx_hbo2 = chromophore_names.index("HbO2")
    idx_hb = chromophore_names.index("Hb")

    hbo2 = concentrations[:, :, idx_hbo2]
    hb = concentrations[:, :, idx_hb]

    thb = hbo2 + hb
    so2 = hbo2 / (thb + eps)

    return {"THb": thb, "sO2": so2}


# ---------------------------------------------------------------------------
# Quality diagnostics
# ---------------------------------------------------------------------------

def compute_diagnostics(
    reflectance: np.ndarray,
    od_cube: np.ndarray,
    rmse_map: np.ndarray,
    A: np.ndarray,
) -> dict:
    """
    Compute quality diagnostics and warnings.

    Returns
    -------
    dict with:
        global_rmse : float
        n_nan_pixels : int
        n_negative_reflectance : int
        condition_number : float
        warnings : list[str]
    """
    warnings = []

    global_rmse = float(np.nanmean(rmse_map))
    n_nan = int(np.sum(np.isnan(rmse_map)))
    n_neg_refl = int(np.sum(reflectance < 0))
    cond = float(np.linalg.cond(A))

    if n_nan > 0:
        warnings.append(f"⚠ {n_nan} pixels contain NaN values")
    if n_neg_refl > 0:
        pct = 100 * n_neg_refl / reflectance.size
        warnings.append(f"⚠ {n_neg_refl} negative reflectance values ({pct:.1f}%)")
    if cond > 100:
        warnings.append(f"⚠ Overlap matrix condition number is high: {cond:.1f}")

    return {
        "global_rmse": global_rmse,
        "n_nan_pixels": n_nan,
        "n_negative_reflectance": n_neg_refl,
        "condition_number": cond,
        "warnings": warnings,
    }
