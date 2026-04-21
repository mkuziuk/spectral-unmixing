"""
Processing module for spectral unmixing.

Pipeline:
    raw cube → reflectance → optical density → spectral basis → solver → maps
"""

import numpy as np
from scipy.interpolate import interp1d
from scipy.optimize import nnls


SUPPORTED_UNMIXING_METHODS: tuple[str, ...] = ("ls", "nnls", "mu_a")

# Fixed scattering prior used by the mu_a inversion solver.
SCATTERING_REFERENCE_WAVELENGTH_NM: float = 500.0
SCATTERING_MU_S_500_CM1: float = 120.0
SCATTERING_POWER_B: float = 1.0
SCATTERING_LIPOFUNDIN_FRACTION: float = 0.25
SCATTERING_ANISOTROPY_G: float = 0.8


def get_default_scattering_parameters() -> dict[str, float]:
    """Return the default fixed-scattering parameter set for the mu_a solver."""
    return {
        "lambda0_nm": SCATTERING_REFERENCE_WAVELENGTH_NM,
        "mu_s_500_cm1": SCATTERING_MU_S_500_CM1,
        "power_b": SCATTERING_POWER_B,
        "lipofundin_fraction": SCATTERING_LIPOFUNDIN_FRACTION,
        "anisotropy_g": SCATTERING_ANISOTROPY_G,
    }


def validate_scattering_parameters(params: dict) -> dict[str, float]:
    """Coerce and validate fixed-scattering parameters from UI input."""
    required_keys = (
        "lambda0_nm",
        "mu_s_500_cm1",
        "power_b",
        "lipofundin_fraction",
        "anisotropy_g",
    )

    missing = [key for key in required_keys if key not in params]
    if missing:
        raise ValueError(f"Missing scattering parameters: {', '.join(missing)}")

    validated = {key: float(params[key]) for key in required_keys}

    if validated["lambda0_nm"] <= 0:
        raise ValueError("lambda0_nm must be > 0.")
    if validated["mu_s_500_cm1"] <= 0:
        raise ValueError("mu_s_500_cm1 must be > 0.")
    if validated["lipofundin_fraction"] < 0:
        raise ValueError("lipofundin_fraction must be >= 0.")
    if not (0 <= validated["anisotropy_g"] < 1):
        raise ValueError("anisotropy_g must satisfy 0 <= g < 1.")

    return validated


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
# Spectral basis helpers
# ---------------------------------------------------------------------------


def _normalized_led_profiles(
    led_emission_wl: np.ndarray,
    led_emission: dict,
    led_wavelengths: list,
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Return the common wavelength grid and area-normalized LED spectra."""
    common_wl = np.asarray(led_emission_wl, dtype=float)
    profiles: list[np.ndarray] = []

    for led_nm in led_wavelengths:
        phi = np.asarray(led_emission[led_nm], dtype=float).copy()
        area = np.trapezoid(phi, common_wl)
        if area > 0:
            phi /= area
        profiles.append(phi)

    return common_wl, profiles


def _interpolate_chromophore_spectra(
    common_wl: np.ndarray,
    chromophore_spectra: dict,
    chromophore_names: list | None = None,
) -> tuple[list[str], dict[str, np.ndarray]]:
    """Interpolate chromophore spectra onto the common wavelength grid."""
    if chromophore_names is None:
        chromophore_names = list(chromophore_spectra.keys())

    chrom_interp = {}
    for name in chromophore_names:
        wl, coeff = chromophore_spectra[name]
        f = interp1d(
            wl,
            coeff,
            kind="linear",
            fill_value="extrapolate",
            bounds_error=False,
        )
        chrom_interp[name] = f(common_wl)

    return chromophore_names, chrom_interp


# ---------------------------------------------------------------------------
# Model matrices
# ---------------------------------------------------------------------------

def build_overlap_matrix(
    led_emission_wl: np.ndarray,
    led_emission: dict,
    chromophore_spectra: dict,
    penetration_wl: np.ndarray,
    penetration_depth: np.ndarray,
    led_wavelengths: list,
    chromophore_names: list = None,
    include_background: bool = True,
    background_value: float = 2500.0,
) -> tuple:
    """
    Build the overlap matrix A ∈ R^{N_LED × N_components}.

    Steps:
        1. Define a common wavelength grid from the LED emission data.
        2. Interpolate all spectra onto this grid.
        3. Normalize each LED spectrum (area = 1).
        4. Compute overlap extinction: eps_k^n = ∫ phi_n(λ) * eps_k(λ) dλ
        5. Compute overlap pathlength: l^n = ∫ phi_n(λ) * l(λ) dλ
        6. A[n,k] = l^n * eps_k^n
        7. Append background column (configurable, default 2500.0).

    Parameters
    ----------
    led_emission_wl : (N,) wavelength axis of LED data
    led_emission : dict {led_nm: (N,) emission array}
    chromophore_spectra : dict {name: (wl_array, coeff_array)}
    penetration_wl, penetration_depth : arrays
    led_wavelengths : list[int], ordered LED centre wavelengths
    include_background : bool, optional
        Whether to append a background column (default True)
    background_value : float, optional
        Value for the background column (default 2500.0)

    Returns
    -------
    A : np.ndarray, shape (N_LED, N_components)
        Columns: [chromophores, optional background with value `background_value`]
    chromophore_names : list[str]
        Column labels (without background)
    """
    common_wl, led_profiles = _normalized_led_profiles(
        led_emission_wl,
        led_emission,
        led_wavelengths,
    )

    # Interpolate penetration depth onto common grid
    f_depth = interp1d(
        penetration_wl, penetration_depth,
        kind="linear", fill_value="extrapolate", bounds_error=False,
    )
    depth_interp = f_depth(common_wl)

    chromophore_names, chrom_interp = _interpolate_chromophore_spectra(
        common_wl,
        chromophore_spectra,
        chromophore_names=chromophore_names,
    )

    n_leds = len(led_wavelengths)
    n_chrom = len(chromophore_names)
    A = np.zeros((n_leds, n_chrom + (1 if include_background else 0)))

    for i, phi in enumerate(led_profiles):
        # Overlap pathlength: l^n = ∫ phi_n(λ) * l(λ) dλ
        l_n = np.trapezoid(phi * depth_interp, common_wl)

        # Overlap extinction for each chromophore
        for j, name in enumerate(chromophore_names):
            eps_k_n = np.trapezoid(phi * chrom_interp[name], common_wl)
            A[i, j] = l_n * eps_k_n

        # Background column
        if include_background:
            A[i, -1] = background_value

    return A, chromophore_names


def build_absorption_matrix(
    led_emission_wl: np.ndarray,
    led_emission: dict,
    chromophore_spectra: dict,
    led_wavelengths: list,
    chromophore_names: list = None,
) -> tuple:
    """
    Build the band-averaged absorption basis E ∈ R^{N_LED × N_chromophores}.

    Each row is the LED-weighted extinction overlap for one band:

        E[n, k] = ∫ phi_n(λ) * ε_k(λ) dλ
    """
    common_wl, led_profiles = _normalized_led_profiles(
        led_emission_wl,
        led_emission,
        led_wavelengths,
    )
    chromophore_names, chrom_interp = _interpolate_chromophore_spectra(
        common_wl,
        chromophore_spectra,
        chromophore_names=chromophore_names,
    )

    E = np.zeros((len(led_wavelengths), len(chromophore_names)))
    for i, phi in enumerate(led_profiles):
        for j, name in enumerate(chromophore_names):
            E[i, j] = np.trapezoid(phi * chrom_interp[name], common_wl)

    return E, chromophore_names


def build_fixed_scattering_profile(
    led_emission_wl: np.ndarray,
    led_emission: dict,
    led_wavelengths: list,
    lambda0_nm: float = SCATTERING_REFERENCE_WAVELENGTH_NM,
    mu_s_500_cm1: float = SCATTERING_MU_S_500_CM1,
    power_b: float = SCATTERING_POWER_B,
    lipofundin_fraction: float = SCATTERING_LIPOFUNDIN_FRACTION,
    anisotropy_g: float = SCATTERING_ANISOTROPY_G,
) -> np.ndarray:
    """
    Build the LED-band reduced scattering prior μs'(λ) for the fixed-scattering solver.
    """
    params = validate_scattering_parameters({
        "lambda0_nm": lambda0_nm,
        "mu_s_500_cm1": mu_s_500_cm1,
        "power_b": power_b,
        "lipofundin_fraction": lipofundin_fraction,
        "anisotropy_g": anisotropy_g,
    })

    common_wl, led_profiles = _normalized_led_profiles(
        led_emission_wl,
        led_emission,
        led_wavelengths,
    )

    mu_s = params["mu_s_500_cm1"] * (common_wl / params["lambda0_nm"]) ** (-params["power_b"])
    mu_s *= params["lipofundin_fraction"]
    mu_s_prime_wl = mu_s * (1.0 - params["anisotropy_g"])

    mu_s_prime = np.zeros(len(led_wavelengths))
    for i, phi in enumerate(led_profiles):
        mu_s_prime[i] = np.trapezoid(phi * mu_s_prime_wl, common_wl)

    return mu_s_prime


# ---------------------------------------------------------------------------
# Least-squares unmixing
# ---------------------------------------------------------------------------

def solve_unmixing(
    od_cube: np.ndarray,
    A: np.ndarray,
    method: str = "ls",
    mus_prime: np.ndarray | None = None,
) -> tuple:
    """
    Pixelwise spectral unmixing.

    Parameters
    ----------
    od_cube : (H, W, N_bands) optical density
    A : np.ndarray
        Solver matrix. For ``ls``/``nnls`` this is the overlap matrix.
        For ``mu_a`` this is the band-averaged absorption basis.
    method : str, optional
        "ls" for unconstrained least-squares (numpy.linalg.lstsq)
        "nnls" for non-negative least-squares (scipy.optimize.nnls)
        "mu_a" for fixed-scattering OD→μa inversion followed by least-squares
    mus_prime : np.ndarray, optional
        Required for ``method="mu_a"``. Band-averaged reduced scattering prior
        with one value per LED band.

    Returns
    -------
    concentrations : (H, W, N_components)
    residual_map : (H, W) RMSE per pixel
    fitted_od : (H, W, N_bands) reconstructed OD
    """
    if method == "nnls":
        return _solve_unmixing_nnls(od_cube, A)
    if method == "mu_a":
        if mus_prime is None:
            raise ValueError("mus_prime is required for method='mu_a'.")
        return _solve_unmixing_mu_a(od_cube, A, mus_prime)
    if method == "ls":
        return _solve_unmixing_ls(od_cube, A)
    raise ValueError(
        f"Unsupported solver method: {method!r}. "
        f"Expected one of {SUPPORTED_UNMIXING_METHODS}."
    )


def _solve_unmixing_ls(
    od_cube: np.ndarray,
    A: np.ndarray,
) -> tuple:
    """
    Pixelwise least-squares spectral unmixing (unconstrained).

    For each pixel: min_x ||Ax - y||^2  via numpy.linalg.lstsq
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


def _solve_unmixing_nnls(
    od_cube: np.ndarray,
    A: np.ndarray,
) -> tuple:
    """
    Pixelwise non-negative least-squares spectral unmixing.

    For each pixel: min_x ||Ax - y||^2  subject to x >= 0
    via scipy.optimize.nnls
    """
    H, W, N = od_cube.shape
    n_components = A.shape[1]

    # Reshape to (N_pixels, N_bands)
    Y = od_cube.reshape(-1, N)  # (H*W, N)

    # Solve NNLS for each pixel
    X = np.zeros((n_components, Y.shape[0]))
    for i in range(Y.shape[0]):
        X[:, i], _ = nnls(A, Y[i])

    concentrations = X.T.reshape(H, W, n_components)

    # Compute fitted OD and residuals
    fitted = (A @ X).T.reshape(H, W, N)  # (H, W, N)
    residual_per_pixel = od_cube - fitted
    rmse_map = np.sqrt(np.mean(residual_per_pixel ** 2, axis=2))

    return concentrations, rmse_map, fitted


def _od_to_mu_a(
    od: np.ndarray,
    mus_prime: np.ndarray,
    eps: float = 1e-10,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert optical density to absorption using the fixed-scattering relation.

    Negative OD values are clipped to zero before inversion because the model
    is only defined for non-negative absorption.
    """
    od_nonnegative = np.clip(np.asarray(od, dtype=float), 0.0, None)
    mus_prime = np.asarray(mus_prime, dtype=float)
    denom = 1.0 - 3.0 * od_nonnegative ** 2

    valid = (
        np.isfinite(od_nonnegative)
        & np.isfinite(mus_prime)
        & (mus_prime > 0)
        & (denom > eps)
    )

    mu_a = np.zeros_like(od_nonnegative, dtype=float)
    mu_a[valid] = (
        3.0
        * mus_prime[valid]
        * od_nonnegative[valid] ** 2
        / denom[valid]
    )
    return mu_a, valid


def _mu_a_to_od(
    mu_a: np.ndarray,
    mus_prime: np.ndarray,
    eps: float = 1e-10,
) -> np.ndarray:
    """Map absorption back to optical density using the same fixed-scattering model."""
    mu_a_clipped = np.clip(np.asarray(mu_a, dtype=float), 0.0, None)
    mus_prime = np.asarray(mus_prime, dtype=float)
    denom = 3.0 * (mu_a_clipped + mus_prime)

    od = np.zeros_like(mu_a_clipped, dtype=float)
    valid = np.isfinite(mu_a_clipped) & np.isfinite(denom) & (denom > eps)
    od[valid] = np.sqrt(np.clip(mu_a_clipped[valid] / denom[valid], 0.0, None))
    return od


def _solve_unmixing_mu_a(
    od_cube: np.ndarray,
    A: np.ndarray,
    mus_prime: np.ndarray,
) -> tuple:
    """
    Fixed-scattering OD→μa inversion followed by NNLS chromophore fit.
    """
    H, W, N = od_cube.shape
    n_components = A.shape[1]
    mus_prime = np.asarray(mus_prime, dtype=float).reshape(-1)

    if A.shape[0] != N:
        raise ValueError(
            "For method='mu_a', the absorption basis must have one row per OD band."
        )
    if mus_prime.shape[0] != N:
        raise ValueError(
            "For method='mu_a', mus_prime must have one entry per OD band."
        )

    Y = od_cube.reshape(-1, N)
    X = np.zeros((n_components, Y.shape[0]))
    fitted_mu_a = np.zeros((Y.shape[0], N))

    for i, od_vec in enumerate(Y):
        mu_a_vec, valid = _od_to_mu_a(od_vec, mus_prime)
        if np.any(valid):
            X[:, i], _ = nnls(A[valid, :], mu_a_vec[valid])
        fitted_mu_a[i, :] = A @ X[:, i]

    fitted = _mu_a_to_od(fitted_mu_a, mus_prime[np.newaxis, :]).reshape(H, W, N)
    concentrations = X.T.reshape(H, W, n_components)
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
    Compute THb and StO2 maps.

    Parameters
    ----------
    concentrations : (H, W, N_components)
    chromophore_names : list[str] – column names (first entries)

    Returns
    -------
    dict with 'THb' and 'StO2' arrays (H, W)
    """
    if "HbO2" in chromophore_names and "Hb" in chromophore_names:
        idx_hbo2 = chromophore_names.index("HbO2")
        idx_hb = chromophore_names.index("Hb")

        hbo2 = concentrations[:, :, idx_hbo2]
        hb = concentrations[:, :, idx_hb]

        thb = hbo2 + hb
        sto2 = hbo2 / (thb + eps)
    else:
        H, W = concentrations.shape[:2]
        thb = np.zeros((H, W))
        sto2 = np.zeros((H, W))

    return {"THb": thb, "StO2": sto2}


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
    Compute quality diagnostics and warnings for the active solver matrix.

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
        warnings.append(f"⚠ Solver matrix condition number is high: {cond:.1f}")

    return {
        "global_rmse": global_rmse,
        "n_nan_pixels": n_nan,
        "n_negative_reflectance": n_neg_refl,
        "condition_number": cond,
        "warnings": warnings,
    }
