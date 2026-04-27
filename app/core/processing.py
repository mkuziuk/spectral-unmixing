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

# Background basis defaults used by the LS/NNLS overlap-matrix solvers.
BACKGROUND_MODEL_CONSTANT: str = "constant"
BACKGROUND_MODEL_EXPONENTIAL: str = "exponential"
SUPPORTED_BACKGROUND_MODELS: tuple[str, ...] = (
    BACKGROUND_MODEL_CONSTANT,
    BACKGROUND_MODEL_EXPONENTIAL,
)
BACKGROUND_CONSTANT_VALUE: float = 2500.0
BACKGROUND_EXP_START: float = 1.0
BACKGROUND_EXP_END: float = 0.1
BACKGROUND_EXP_SHAPE: float = 1.0
BACKGROUND_EXP_OFFSET: float = 0.0

# Iterative solver convergence defaults.
ITERATIVE_MAX_ITER: int = 25
ITERATIVE_TOL_REL: float = 1e-4
ITERATIVE_TOL_RMSE: float = 1e-6
ITERATIVE_DAMPING: float = 0.5
ITERATIVE_INITIAL_CONCENTRATION: float = 1e-4


def get_default_scattering_parameters() -> dict[str, float]:
    """Return the default fixed-scattering parameter set for fixed-scattering solvers."""
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


def get_default_background_parameters() -> dict[str, float | str]:
    """Return the default background basis configuration."""
    return {
        "model": BACKGROUND_MODEL_CONSTANT,
        "value": BACKGROUND_CONSTANT_VALUE,
        "exp_start": BACKGROUND_EXP_START,
        "exp_end": BACKGROUND_EXP_END,
        "exp_shape": BACKGROUND_EXP_SHAPE,
        "exp_offset": BACKGROUND_EXP_OFFSET,
    }


def validate_background_parameters(params: dict) -> dict[str, float | str]:
    """Coerce and validate background basis parameters from UI or API input."""
    model = str(params.get("model", BACKGROUND_MODEL_CONSTANT)).strip().lower()
    if model not in SUPPORTED_BACKGROUND_MODELS:
        raise ValueError(
            f"Unsupported background model: {model!r}. "
            f"Expected one of {SUPPORTED_BACKGROUND_MODELS}."
        )

    value = float(params.get("value", BACKGROUND_CONSTANT_VALUE))
    exp_start = float(params.get("exp_start", BACKGROUND_EXP_START))
    exp_end = float(params.get("exp_end", BACKGROUND_EXP_END))
    exp_shape = float(params.get("exp_shape", BACKGROUND_EXP_SHAPE))
    exp_offset = float(params.get("exp_offset", BACKGROUND_EXP_OFFSET))

    for key, item in (
        ("value", value),
        ("exp_start", exp_start),
        ("exp_end", exp_end),
        ("exp_shape", exp_shape),
        ("exp_offset", exp_offset),
    ):
        if not np.isfinite(item):
            raise ValueError(f"{key} must be finite.")

    if exp_shape <= 0:
        raise ValueError("exp_shape must be > 0.")
    if exp_start <= 0:
        raise ValueError("exp_start must be > 0.")
    if exp_end < 0:
        raise ValueError("exp_end must be >= 0.")

    return {
        "model": model,
        "value": value,
        "exp_start": exp_start,
        "exp_end": exp_end,
        "exp_shape": exp_shape,
        "exp_offset": exp_offset,
    }


def build_background_profile(
    led_wavelengths: list,
    model: str = BACKGROUND_MODEL_CONSTANT,
    value: float = BACKGROUND_CONSTANT_VALUE,
    exp_start: float = BACKGROUND_EXP_START,
    exp_end: float = BACKGROUND_EXP_END,
    exp_shape: float = BACKGROUND_EXP_SHAPE,
    exp_offset: float = BACKGROUND_EXP_OFFSET,
) -> np.ndarray:
    """Return one background basis value per LED band."""
    params = validate_background_parameters({
        "model": model,
        "value": value,
        "exp_start": exp_start,
        "exp_end": exp_end,
        "exp_shape": exp_shape,
        "exp_offset": exp_offset,
    })
    wavelengths = np.asarray(led_wavelengths, dtype=float).reshape(-1)

    if params["model"] == BACKGROUND_MODEL_CONSTANT:
        return np.full(wavelengths.shape, float(params["value"]), dtype=float)

    if wavelengths.size == 0:
        return np.asarray([], dtype=float)
    wl_min = float(np.nanmin(wavelengths))
    wl_max = float(np.nanmax(wavelengths))
    if not np.isfinite(wl_min) or not np.isfinite(wl_max):
        raise ValueError("led_wavelengths must be finite.")
    if wl_max == wl_min:
        return np.full(wavelengths.shape, float(params["exp_start"]), dtype=float)

    t = (wavelengths - wl_min) / (wl_max - wl_min)
    offset = float(params["exp_offset"])
    exp_start_value = float(params["exp_start"])
    exp_end_value = float(params["exp_end"])
    if exp_end_value == 0.0:
        profile = offset + exp_start_value * np.where(t <= 0.0, 1.0, 0.0)
    else:
        profile = offset + exp_start_value * (
            exp_end_value / exp_start_value
        ) ** (t ** float(params["exp_shape"]))
    return _validate_finite("background_profile", profile)


def get_default_iterative_solver_parameters() -> dict[str, float | int]:
    """Return the default convergence parameters for the iterative solver."""
    return {
        "max_iter": ITERATIVE_MAX_ITER,
        "tol_rel": ITERATIVE_TOL_REL,
        "tol_rmse": ITERATIVE_TOL_RMSE,
        "damping": ITERATIVE_DAMPING,
        "initial_concentration": ITERATIVE_INITIAL_CONCENTRATION,
    }


def validate_iterative_solver_parameters(params: dict) -> dict[str, float | int]:
    """Coerce and validate iterative-solver controls from UI or API input."""
    required_keys = (
        "max_iter",
        "tol_rel",
        "tol_rmse",
        "damping",
        "initial_concentration",
    )

    missing = [key for key in required_keys if key not in params]
    if missing:
        raise ValueError(f"Missing iterative solver parameters: {', '.join(missing)}")

    max_iter_raw = float(params["max_iter"])
    if not np.isfinite(max_iter_raw) or not max_iter_raw.is_integer():
        raise ValueError("max_iter must be an integer.")
    max_iter = int(max_iter_raw)

    validated = {
        "max_iter": max_iter,
        "tol_rel": float(params["tol_rel"]),
        "tol_rmse": float(params["tol_rmse"]),
        "damping": float(params["damping"]),
        "initial_concentration": float(params["initial_concentration"]),
    }

    for key, value in validated.items():
        if not np.isfinite(float(value)):
            raise ValueError(f"{key} must be finite.")

    if validated["max_iter"] < 1:
        raise ValueError("max_iter must be >= 1.")
    if validated["tol_rel"] <= 0:
        raise ValueError("tol_rel must be > 0.")
    if validated["tol_rmse"] < 0:
        raise ValueError("tol_rmse must be >= 0.")
    if not (0.0 < validated["damping"] <= 1.0):
        raise ValueError("damping must satisfy 0 < damping <= 1.")
    if validated["initial_concentration"] < 0:
        raise ValueError("initial_concentration must be >= 0.")

    return validated


def build_fixed_scattering_spectrum(
    common_wl: np.ndarray,
    lambda0_nm: float = SCATTERING_REFERENCE_WAVELENGTH_NM,
    mu_s_500_cm1: float = SCATTERING_MU_S_500_CM1,
    power_b: float = SCATTERING_POWER_B,
    lipofundin_fraction: float = SCATTERING_LIPOFUNDIN_FRACTION,
    anisotropy_g: float = SCATTERING_ANISOTROPY_G,
) -> np.ndarray:
    """Return the wavelength-resolved reduced scattering prior μs'(λ)."""
    params = validate_scattering_parameters({
        "lambda0_nm": lambda0_nm,
        "mu_s_500_cm1": mu_s_500_cm1,
        "power_b": power_b,
        "lipofundin_fraction": lipofundin_fraction,
        "anisotropy_g": anisotropy_g,
    })

    wl_safe = np.clip(np.asarray(common_wl, dtype=float), 1e-6, None)
    mu_s = params["mu_s_500_cm1"] * (wl_safe / params["lambda0_nm"]) ** (-params["power_b"])
    mu_s *= params["lipofundin_fraction"]
    mu_s_prime = mu_s * (1.0 - params["anisotropy_g"])
    return np.nan_to_num(mu_s_prime, nan=0.0, posinf=0.0, neginf=0.0)


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
        wl_prepared, coeff_prepared = _prepare_interp_axis(wl, coeff)
        f = interp1d(
            wl_prepared,
            coeff_prepared,
            kind="linear",
            fill_value="extrapolate",
            bounds_error=False,
        )
        chrom_interp[name] = f(common_wl)

    return chromophore_names, chrom_interp


def _prepare_interp_axis(
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Sort and collapse duplicate x-values before interpolation."""
    x_arr = np.asarray(x, dtype=float).reshape(-1)
    y_arr = np.asarray(y, dtype=float).reshape(-1)

    if x_arr.shape[0] != y_arr.shape[0]:
        raise ValueError("Interpolation axis and values must have matching lengths.")

    order = np.argsort(x_arr, kind="mergesort")
    x_sorted = x_arr[order]
    y_sorted = y_arr[order]

    unique_x, inverse = np.unique(x_sorted, return_inverse=True)
    if unique_x.shape[0] < 2:
        raise ValueError("Interpolation requires at least two unique x-values.")
    if unique_x.shape[0] == x_sorted.shape[0]:
        return x_sorted, y_sorted

    sums = np.zeros_like(unique_x, dtype=float)
    counts = np.zeros_like(unique_x, dtype=float)
    np.add.at(sums, inverse, y_sorted)
    np.add.at(counts, inverse, 1.0)
    return unique_x, sums / counts


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
    background_value: float = BACKGROUND_CONSTANT_VALUE,
    background_model: str = BACKGROUND_MODEL_CONSTANT,
    background_exp_start: float = BACKGROUND_EXP_START,
    background_exp_end: float = BACKGROUND_EXP_END,
    background_exp_shape: float = BACKGROUND_EXP_SHAPE,
    background_exp_offset: float = BACKGROUND_EXP_OFFSET,
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
        7. Append background column (constant or exponential basis).

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
        Value for the constant background column (default 2500.0)
    background_model : str, optional
        "constant" or "exponential" background basis.
    background_exp_start, background_exp_end : float, optional
        Exponential background values at the shortest and longest LED
        wavelengths respectively.
    background_exp_shape : float, optional
        Curvature parameter; values above 1 delay the decay and values below
        1 make it happen earlier.
    background_exp_offset : float, optional
        Additive baseline/floor for the exponential background.

    Returns
    -------
    A : np.ndarray, shape (N_LED, N_components)
        Columns: [chromophores, optional background basis]
    chromophore_names : list[str]
        Column labels (without background)
    """
    common_wl, led_profiles = _normalized_led_profiles(
        led_emission_wl,
        led_emission,
        led_wavelengths,
    )

    # Interpolate penetration depth onto common grid
    pen_wl_prepared, pen_depth_prepared = _prepare_interp_axis(
        penetration_wl,
        penetration_depth,
    )
    f_depth = interp1d(
        pen_wl_prepared, pen_depth_prepared,
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
    background_profile = None
    if include_background:
        background_profile = build_background_profile(
            led_wavelengths,
            model=background_model,
            value=background_value,
            exp_start=background_exp_start,
            exp_end=background_exp_end,
            exp_shape=background_exp_shape,
            exp_offset=background_exp_offset,
        )

    for i, phi in enumerate(led_profiles):
        # Overlap pathlength: l^n = ∫ phi_n(λ) * l(λ) dλ
        l_n = np.trapezoid(phi * depth_interp, common_wl)

        # Overlap extinction for each chromophore
        for j, name in enumerate(chromophore_names):
            eps_k_n = np.trapezoid(phi * chrom_interp[name], common_wl)
            A[i, j] = l_n * eps_k_n

        # Background column
        if include_background:
            A[i, -1] = background_profile[i]

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
    common_wl, led_profiles = _normalized_led_profiles(
        led_emission_wl,
        led_emission,
        led_wavelengths,
    )

    mu_s_prime_wl = build_fixed_scattering_spectrum(
        common_wl,
        lambda0_nm=lambda0_nm,
        mu_s_500_cm1=mu_s_500_cm1,
        power_b=power_b,
        lipofundin_fraction=lipofundin_fraction,
        anisotropy_g=anisotropy_g,
    )

    mu_s_prime = np.zeros(len(led_wavelengths))
    for i, phi in enumerate(led_profiles):
        mu_s_prime[i] = np.trapezoid(phi * mu_s_prime_wl, common_wl)

    return mu_s_prime


def _validate_finite(name: str, values: np.ndarray) -> np.ndarray:
    """Raise when an intermediate array contains NaN or inf values."""
    arr = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite values.")
    return arr


def _mean_finite_concentrations(concentrations: np.ndarray) -> np.ndarray:
    """Return per-component spatial means while ignoring non-finite values."""
    conc = np.asarray(concentrations, dtype=float)
    finite = np.isfinite(conc)
    counts = finite.sum(axis=(0, 1))
    sums = np.where(finite, conc, 0.0).sum(axis=(0, 1))

    means = np.zeros(conc.shape[2], dtype=float)
    np.divide(sums, counts, out=means, where=counts > 0)
    return means


def estimate_effective_pathlength(
    concentrations: np.ndarray,
    chromophore_names: list,
    chromophore_spectra: dict,
    common_wl: np.ndarray,
    lambda0_nm: float = SCATTERING_REFERENCE_WAVELENGTH_NM,
    mu_s_500_cm1: float = SCATTERING_MU_S_500_CM1,
    power_b: float = SCATTERING_POWER_B,
    lipofundin_fraction: float = SCATTERING_LIPOFUNDIN_FRACTION,
    anisotropy_g: float = SCATTERING_ANISOTROPY_G,
    eps: float = 1e-10,
) -> np.ndarray:
    """Estimate wavelength-dependent effective pathlength from mean absorption."""
    if concentrations.ndim != 3:
        raise ValueError("concentrations must have shape (H, W, N_components).")

    common_wl = np.asarray(common_wl, dtype=float)
    c_mean = _mean_finite_concentrations(concentrations)
    if c_mean.shape[0] != len(chromophore_names):
        raise ValueError(
            "The number of concentration channels must match chromophore_names."
        )

    mu_a = np.zeros_like(common_wl, dtype=float)
    for idx, name in enumerate(chromophore_names):
        if name not in chromophore_spectra:
            raise KeyError(f"Chromophore spectrum not found: {name}")
        wl, coeff = chromophore_spectra[name]
        wl_prepared, coeff_prepared = _prepare_interp_axis(wl, coeff)
        interpolator = interp1d(
            wl_prepared,
            coeff_prepared,
            kind="linear",
            fill_value="extrapolate",
            bounds_error=False,
        )
        coeff_interp = np.asarray(interpolator(common_wl), dtype=float)
        coeff_interp = np.nan_to_num(coeff_interp, nan=0.0, posinf=0.0, neginf=0.0)
        mu_a += max(float(c_mean[idx]), 0.0) * np.clip(coeff_interp, 0.0, None)

    mu_a = np.clip(mu_a, eps, None)
    mu_s_prime = build_fixed_scattering_spectrum(
        common_wl,
        lambda0_nm=lambda0_nm,
        mu_s_500_cm1=mu_s_500_cm1,
        power_b=power_b,
        lipofundin_fraction=lipofundin_fraction,
        anisotropy_g=anisotropy_g,
    )
    mu_s_prime = np.clip(mu_s_prime, eps, None)

    mu_eff = np.sqrt(3.0 * mu_a * (mu_a + mu_s_prime))
    l_eff = 1.0 / np.clip(mu_eff, eps, None)
    return _validate_finite("effective_pathlength", l_eff)


def solve_unmixing_iterative(
    od_cube: np.ndarray,
    static_A: np.ndarray,
    led_emission_wl: np.ndarray,
    led_emission: dict,
    chromophore_spectra: dict,
    led_wavelengths: list,
    chromophore_names: list | None = None,
    include_background: bool = False,
    background_value: float = BACKGROUND_CONSTANT_VALUE,
    background_model: str = BACKGROUND_MODEL_CONSTANT,
    background_exp_start: float = BACKGROUND_EXP_START,
    background_exp_end: float = BACKGROUND_EXP_END,
    background_exp_shape: float = BACKGROUND_EXP_SHAPE,
    background_exp_offset: float = BACKGROUND_EXP_OFFSET,
    max_iter: int = ITERATIVE_MAX_ITER,
    tol_rel: float = ITERATIVE_TOL_REL,
    tol_rmse: float = ITERATIVE_TOL_RMSE,
    damping: float = ITERATIVE_DAMPING,
    initial_concentration: float = ITERATIVE_INITIAL_CONCENTRATION,
    scattering_parameters: dict | None = None,
) -> tuple:
    """Iterative overlap-matrix unmixing with a diffusion-inspired pathlength."""
    iterative_params = validate_iterative_solver_parameters({
        "max_iter": max_iter,
        "tol_rel": tol_rel,
        "tol_rmse": tol_rmse,
        "damping": damping,
        "initial_concentration": initial_concentration,
    })
    max_iter = int(iterative_params["max_iter"])
    tol_rel = float(iterative_params["tol_rel"])
    tol_rmse = float(iterative_params["tol_rmse"])
    damping = float(iterative_params["damping"])
    initial_concentration = float(iterative_params["initial_concentration"])

    common_wl = np.asarray(led_emission_wl, dtype=float)
    chrom_names = (
        list(chromophore_spectra.keys())
        if chromophore_names is None
        else list(chromophore_names)
    )
    if not chrom_names and not include_background:
        raise ValueError(
            "Iterative solver requires at least one chromophore or a background channel."
        )

    params = get_default_scattering_parameters()
    if scattering_parameters is not None:
        params.update(scattering_parameters)
    params = validate_scattering_parameters(params)
    background_params = validate_background_parameters({
        "model": background_model,
        "value": background_value,
        "exp_start": background_exp_start,
        "exp_end": background_exp_end,
        "exp_shape": background_exp_shape,
        "exp_offset": background_exp_offset,
    })

    H, W, _ = od_cube.shape
    n_chrom = len(chrom_names)

    history = []
    stop_reason = "max_iter"
    iterative_error = None
    fallback_used = False
    fallback_reason = None
    prev_mean_rmse = None
    A_last = np.asarray(static_A, dtype=float)
    pathlength_used = common_wl.copy()
    best_concentrations = None
    best_rmse_map = None
    best_fitted_od = None
    best_A = A_last.copy()
    best_pathlength = pathlength_used.copy()
    best_iter = 0
    best_mean_rmse = float("inf")

    current_conc_map = np.full(
        (H, W, n_chrom),
        max(float(initial_concentration), 0.0),
        dtype=float,
    )
    l_curr = estimate_effective_pathlength(
        concentrations=current_conc_map,
        chromophore_names=chrom_names,
        chromophore_spectra=chromophore_spectra,
        common_wl=common_wl,
        **params,
    )

    try:
        for it in range(max_iter):
            A_iter, _ = build_overlap_matrix(
                led_emission_wl=common_wl,
                led_emission=led_emission,
                chromophore_spectra=chromophore_spectra,
                penetration_wl=common_wl,
                penetration_depth=l_curr,
                led_wavelengths=led_wavelengths,
                chromophore_names=chrom_names,
                include_background=include_background,
                background_value=background_params["value"],
                background_model=background_params["model"],
                background_exp_start=background_params["exp_start"],
                background_exp_end=background_params["exp_end"],
                background_exp_shape=background_params["exp_shape"],
                background_exp_offset=background_params["exp_offset"],
            )
            A_iter = _validate_finite("overlap_matrix", A_iter)
            concentrations, rmse_map, fitted_od = _solve_unmixing_nnls(od_cube, A_iter)
            concentrations = _validate_finite("concentrations", concentrations)
            rmse_map = _validate_finite("rmse_map", rmse_map)

            A_last = A_iter
            pathlength_used = l_curr.copy()
            mean_rmse = float(np.nanmean(rmse_map))
            if mean_rmse < best_mean_rmse:
                best_concentrations = concentrations.copy()
                best_rmse_map = rmse_map.copy()
                best_fitted_od = fitted_od.copy()
                best_A = A_iter.copy()
                best_pathlength = l_curr.copy()
                best_iter = it + 1
                best_mean_rmse = mean_rmse

            conc_only = concentrations[:, :, :n_chrom]
            l_model = estimate_effective_pathlength(
                concentrations=conc_only,
                chromophore_names=chrom_names,
                chromophore_spectra=chromophore_spectra,
                common_wl=common_wl,
                **params,
            )
            l_next = _validate_finite(
                "damped_pathlength",
                (1.0 - damping) * l_curr + damping * l_model,
            )

            rel_change = np.linalg.norm(l_next - l_curr) / (np.linalg.norm(l_curr) + 1e-12)
            rmse_improvement = (
                float("inf") if prev_mean_rmse is None else float(prev_mean_rmse - mean_rmse)
            )
            history.append(
                {
                    "iter": it + 1,
                    "rel_change_l": float(rel_change),
                    "mean_rmse": mean_rmse,
                    "rmse_improvement": rmse_improvement,
                }
            )

            if rel_change < tol_rel:
                stop_reason = "tol_rel"
                break
            if prev_mean_rmse is not None and 0.0 <= rmse_improvement < tol_rmse:
                stop_reason = "tol_rmse"
                break

            prev_mean_rmse = mean_rmse
            l_curr = l_next

    except Exception as exc:
        stop_reason = "iterative_error"
        iterative_error = str(exc)
        fallback_used = True
        if best_concentrations is not None:
            fallback_reason = (
                "Iterative unmixing stopped after an error; the best successful iterate was used."
            )
            concentrations = best_concentrations
            rmse_map = best_rmse_map
            fitted_od = best_fitted_od
            A_last = best_A
            pathlength_used = best_pathlength
        else:
            fallback_reason = "Iterative unmixing failed; static overlap matrix fallback was used."
            concentrations, rmse_map, fitted_od = _solve_unmixing_nnls(od_cube, A_last)
            pathlength_used = l_curr

    if best_concentrations is not None and stop_reason != "iterative_error":
        concentrations = best_concentrations
        rmse_map = best_rmse_map
        fitted_od = best_fitted_od
        A_last = best_A
        pathlength_used = best_pathlength

    returned_iter = best_iter if best_iter > 0 else len(history)
    returned_mean_rmse = (
        best_mean_rmse if best_iter > 0 else float(np.nanmean(rmse_map))
    )

    solver_info = {
        "method": "iterative",
        "base_method": "nnls",
        "include_background": bool(include_background),
        "background_parameters": dict(background_params),
        "stop_reason": stop_reason,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "iterative_error": iterative_error,
        "n_iter": len(history),
        "max_iter": int(max_iter),
        "history": history,
        "iterative_parameters": dict(iterative_params),
        "best_iter": int(best_iter) if best_iter > 0 else None,
        "best_mean_rmse": float(best_mean_rmse) if best_iter > 0 else None,
        "returned_iter": int(returned_iter),
        "returned_mean_rmse": float(returned_mean_rmse),
        "stop_thresholds": {
            "tol_rel": float(tol_rel),
            "tol_rmse": float(tol_rmse),
            "max_iter": int(max_iter),
        },
        "pathlength_spectrum": pathlength_used,
        "A_used": A_last,
        "scattering_parameters": dict(params),
    }
    return concentrations, rmse_map, fitted_od, solver_info


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
