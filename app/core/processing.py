"""
Processing module for spectral unmixing.

Pipeline:
    raw cube → reflectance → optical density → spectral basis → solver → maps
"""

import logging
import numpy as np
from scipy.interpolate import interp1d
from scipy.optimize import nnls
import itertools

logger = logging.getLogger(__name__)


SUPPORTED_UNMIXING_METHODS: tuple[str, ...] = ("ls", "nnls", "mu_a", "diffusion", "slab")
LN10: float = float(np.log(10.0))

# Fixed scattering prior used by the mu_a inversion solver.
SCATTERING_MODEL_POWER_LAW: str = "power_law"
SCATTERING_MODEL_SPECTRUM: str = "spectrum"
SUPPORTED_SCATTERING_MODELS: tuple[str, ...] = (
    SCATTERING_MODEL_POWER_LAW,
    SCATTERING_MODEL_SPECTRUM,
)
SCATTERING_REFERENCE_WAVELENGTH_NM: float = 500.0
SCATTERING_MU_S_500_CM1: float = 120.0
SCATTERING_POWER_B: float = 1.0
SCATTERING_LIPOFUNDIN_FRACTION: float = 0.25
SCATTERING_ANISOTROPY_G: float = 0.8

# Background basis defaults used by the LS/NNLS overlap-matrix solvers.
BACKGROUND_MODEL_CONSTANT: str = "constant"
BACKGROUND_MODEL_EXPONENTIAL: str = "exponential"
BACKGROUND_MODEL_SLOPE: str = "slope"
BACKGROUND_MODEL_SCATTERING: str = "scattering"
SUPPORTED_BACKGROUND_MODELS: tuple[str, ...] = (
    BACKGROUND_MODEL_CONSTANT,
    BACKGROUND_MODEL_EXPONENTIAL,
    BACKGROUND_MODEL_SLOPE,
    BACKGROUND_MODEL_SCATTERING,
)
BACKGROUND_CONSTANT_VALUE: float = 2500.0
BACKGROUND_EXP_START: float = 1.0
BACKGROUND_EXP_END: float = 0.1
BACKGROUND_EXP_SHAPE: float = 1.0
BACKGROUND_EXP_OFFSET: float = 0.0
BACKGROUND_SLOPE_START: float = 1.0
BACKGROUND_SLOPE_END: float = 0.1
BACKGROUND_SCATTERING_LAMBDA0_NM: float = SCATTERING_REFERENCE_WAVELENGTH_NM
BACKGROUND_SCATTERING_POWER_B: float = SCATTERING_POWER_B

# Iterative solver convergence defaults.
ITERATIVE_MAX_ITER: int = 25
ITERATIVE_TOL_REL: float = 1e-4
ITERATIVE_TOL_RMSE: float = 1e-6
ITERATIVE_DAMPING: float = 0.5
ITERATIVE_INITIAL_CONCENTRATION: float = 1e-4

# Welch diffusion-solver defaults.
DIFFUSION_N_TISSUE: float = 1.4
DIFFUSION_N_OUT: float = 1.0
DIFFUSION_MU_A_MIN: float = 1e-6
DIFFUSION_MU_A_MAX: float = 10.0
DIFFUSION_N_GRID: int = 512

# Slab diffusion-model defaults (ported from DiffusionModelForSlab).
SLAB_DEFAULT_NAME: str = "DiffSlab"
SLAB_DEFAULT_MODE: str = "collim"
SLAB_N_TISSUE: float = 1.4
SLAB_THICKNESS_MM: float = 10.0
SLAB_C_MAX: float = 1.3e-4
SLAB_C_STEPS: int = 100


def get_default_scattering_parameters() -> dict:
    """Return the default fixed-scattering parameter set for fixed-scattering solvers."""
    return {
        "model": SCATTERING_MODEL_POWER_LAW,
        "spectrum_path": "",
        "lambda0_nm": SCATTERING_REFERENCE_WAVELENGTH_NM,
        "mu_s_500_cm1": SCATTERING_MU_S_500_CM1,
        "power_b": SCATTERING_POWER_B,
        "lipofundin_fraction": SCATTERING_LIPOFUNDIN_FRACTION,
        "anisotropy_g": SCATTERING_ANISOTROPY_G,
    }


def _validate_scattering_common(params: dict) -> dict:
    """Validate parameters shared by power-law and spectrum scattering models."""
    lipofundin_fraction = float(
        params.get("lipofundin_fraction", SCATTERING_LIPOFUNDIN_FRACTION)
    )
    anisotropy_g = float(params.get("anisotropy_g", SCATTERING_ANISOTROPY_G))
    if lipofundin_fraction < 0:
        raise ValueError("lipofundin_fraction must be >= 0.")
    if not (0 <= anisotropy_g < 1):
        raise ValueError("anisotropy_g must satisfy 0 <= g < 1.")
    return {
        "lipofundin_fraction": lipofundin_fraction,
        "anisotropy_g": anisotropy_g,
    }


def validate_scattering_parameters(params: dict) -> dict:
    """Coerce and validate fixed-scattering parameters from UI input."""
    from app.core import io as loader

    model = str(params.get("model", SCATTERING_MODEL_POWER_LAW)).strip().lower()
    if model not in SUPPORTED_SCATTERING_MODELS:
        raise ValueError(
            f"Unsupported scattering model '{model}'. "
            f"Expected one of: {', '.join(SUPPORTED_SCATTERING_MODELS)}."
        )

    validated: dict = {"model": model, **_validate_scattering_common(params)}

    if model == SCATTERING_MODEL_POWER_LAW:
        required_keys = ("lambda0_nm", "mu_s_500_cm1", "power_b")
        missing = [key for key in required_keys if key not in params]
        if missing:
            raise ValueError(f"Missing scattering parameters: {', '.join(missing)}")

        validated.update({key: float(params[key]) for key in required_keys})
        validated["spectrum_path"] = str(params.get("spectrum_path", "")).strip()

        if validated["lambda0_nm"] <= 0:
            raise ValueError("lambda0_nm must be > 0.")
        if validated["mu_s_500_cm1"] <= 0:
            raise ValueError("mu_s_500_cm1 must be > 0.")
        return validated

    spectrum_path = str(params.get("spectrum_path", "")).strip()
    if not spectrum_path:
        raise ValueError("spectrum_path is required when scattering model is 'spectrum'.")

    if "spectrum_wavelengths_nm" in params and "spectrum_values_cm1" in params:
        wl = np.asarray(params["spectrum_wavelengths_nm"], dtype=float)
        values = np.asarray(params["spectrum_values_cm1"], dtype=float)
    else:
        wl, values = loader.load_mu_s_prime_spectrum(spectrum_path)

    validated["spectrum_path"] = spectrum_path
    validated["spectrum_wavelengths_nm"] = wl
    validated["spectrum_values_cm1"] = values
    return validated


def interpolate_mu_s_prime_spectrum(
    spectrum_wavelengths_nm: np.ndarray,
    spectrum_values_cm1: np.ndarray,
    target_wl: np.ndarray,
) -> np.ndarray:
    """
    Resample a tabular μs'(λ) spectrum onto the solver wavelength grid.

    Input CSV spectra are typically sampled every few nm (e.g. 351–800 nm).
    The LED ``common_wl`` axis from ``leds_emission.csv`` can span a wider range
    (e.g. 195–1020 nm). Wavelengths below/above the tabulated range use the
  nearest edge value; band integration still weights by LED emission, so tails
    outside the CSV usually contribute little.
    """
    wl_prepared, values_prepared = _prepare_interp_axis(
        spectrum_wavelengths_nm,
        spectrum_values_cm1,
    )
    target = np.asarray(target_wl, dtype=float)

    interpolator = interp1d(
        wl_prepared,
        values_prepared,
        kind="linear",
        bounds_error=False,
        fill_value=(float(values_prepared[0]), float(values_prepared[-1])),
    )
    mu_s_prime = np.asarray(interpolator(target), dtype=float)
    mu_s_prime = np.nan_to_num(mu_s_prime, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(mu_s_prime, 0.0, None)


def get_default_background_parameters() -> dict[str, float | str]:
    """Return the default background basis configuration."""
    return {
        "model": BACKGROUND_MODEL_CONSTANT,
        "value": BACKGROUND_CONSTANT_VALUE,
        "exp_start": BACKGROUND_EXP_START,
        "exp_end": BACKGROUND_EXP_END,
        "exp_shape": BACKGROUND_EXP_SHAPE,
        "exp_offset": BACKGROUND_EXP_OFFSET,
        "slope_start": BACKGROUND_SLOPE_START,
        "slope_end": BACKGROUND_SLOPE_END,
        "scattering_lambda0_nm": BACKGROUND_SCATTERING_LAMBDA0_NM,
        "scattering_power_b": BACKGROUND_SCATTERING_POWER_B,
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
    slope_start = float(params.get("slope_start", BACKGROUND_SLOPE_START))
    slope_end = float(params.get("slope_end", BACKGROUND_SLOPE_END))
    scattering_lambda0_nm = float(
        params.get("scattering_lambda0_nm", BACKGROUND_SCATTERING_LAMBDA0_NM)
    )
    scattering_power_b = float(
        params.get("scattering_power_b", BACKGROUND_SCATTERING_POWER_B)
    )

    for key, item in (
        ("value", value),
        ("exp_start", exp_start),
        ("exp_end", exp_end),
        ("exp_shape", exp_shape),
        ("exp_offset", exp_offset),
        ("slope_start", slope_start),
        ("slope_end", slope_end),
        ("scattering_lambda0_nm", scattering_lambda0_nm),
        ("scattering_power_b", scattering_power_b),
    ):
        if not np.isfinite(item):
            raise ValueError(f"{key} must be finite.")

    if exp_shape <= 0:
        raise ValueError("exp_shape must be > 0.")
    if exp_start <= 0:
        raise ValueError("exp_start must be > 0.")
    if exp_end < 0:
        raise ValueError("exp_end must be >= 0.")
    if scattering_lambda0_nm <= 0:
        raise ValueError("scattering_lambda0_nm must be > 0.")
    if scattering_power_b < 0:
        raise ValueError("scattering_power_b must be >= 0.")

    return {
        "model": model,
        "value": value,
        "exp_start": exp_start,
        "exp_end": exp_end,
        "exp_shape": exp_shape,
        "exp_offset": exp_offset,
        "slope_start": slope_start,
        "slope_end": slope_end,
        "scattering_lambda0_nm": scattering_lambda0_nm,
        "scattering_power_b": scattering_power_b,
    }


def build_background_profile(
    led_wavelengths: list,
    model: str = BACKGROUND_MODEL_CONSTANT,
    value: float = BACKGROUND_CONSTANT_VALUE,
    exp_start: float = BACKGROUND_EXP_START,
    exp_end: float = BACKGROUND_EXP_END,
    exp_shape: float = BACKGROUND_EXP_SHAPE,
    exp_offset: float = BACKGROUND_EXP_OFFSET,
    slope_start: float = BACKGROUND_SLOPE_START,
    slope_end: float = BACKGROUND_SLOPE_END,
    scattering_lambda0_nm: float = BACKGROUND_SCATTERING_LAMBDA0_NM,
    scattering_power_b: float = BACKGROUND_SCATTERING_POWER_B,
) -> np.ndarray:
    """Return one background basis value per LED band."""
    params = validate_background_parameters({
        "model": model,
        "value": value,
        "exp_start": exp_start,
        "exp_end": exp_end,
        "exp_shape": exp_shape,
        "exp_offset": exp_offset,
        "slope_start": slope_start,
        "slope_end": slope_end,
        "scattering_lambda0_nm": scattering_lambda0_nm,
        "scattering_power_b": scattering_power_b,
    })
    wavelengths = np.asarray(led_wavelengths, dtype=float).reshape(-1)

    if params["model"] == BACKGROUND_MODEL_CONSTANT:
        return np.full(wavelengths.shape, float(params["value"]), dtype=float)

    if wavelengths.size == 0:
        return np.asarray([], dtype=float)
    if params["model"] == BACKGROUND_MODEL_SCATTERING:
        wl_safe = np.clip(wavelengths, 1e-6, None)
        lambda0 = float(params["scattering_lambda0_nm"])
        b = float(params["scattering_power_b"])
        # Power-law shape normalized to 1 at lambda0.
        profile = (wl_safe / lambda0) ** (-b)
        return _validate_finite("background_profile", profile)
    wl_min = float(np.nanmin(wavelengths))
    wl_max = float(np.nanmax(wavelengths))
    if not np.isfinite(wl_min) or not np.isfinite(wl_max):
        raise ValueError("led_wavelengths must be finite.")
    if wl_max == wl_min:
        if params["model"] == BACKGROUND_MODEL_SLOPE:
            return np.full(wavelengths.shape, float(params["slope_start"]), dtype=float)
        if params["model"] == BACKGROUND_MODEL_SCATTERING:
            return np.full(wavelengths.shape, 1.0, dtype=float)
        return np.full(wavelengths.shape, float(params["exp_start"]), dtype=float)

    t = (wavelengths - wl_min) / (wl_max - wl_min)
    if params["model"] == BACKGROUND_MODEL_SLOPE:
        profile = float(params["slope_start"]) + (
            float(params["slope_end"]) - float(params["slope_start"])
        ) * t
        return _validate_finite("background_profile", profile)

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


def get_default_diffusion_parameters() -> dict[str, float | int]:
    """Return default Welch diffusion inversion parameters."""
    return {
        "n_tissue": DIFFUSION_N_TISSUE,
        "n_out": DIFFUSION_N_OUT,
        "mu_a_min": DIFFUSION_MU_A_MIN,
        "mu_a_max": DIFFUSION_MU_A_MAX,
        "n_grid": DIFFUSION_N_GRID,
    }


def validate_diffusion_parameters(params: dict) -> dict[str, float | int]:
    """Coerce and validate Welch diffusion inversion parameters from UI/API input."""
    required = ("n_tissue", "n_out", "mu_a_min", "mu_a_max", "n_grid")
    missing = [k for k in required if k not in params]
    if missing:
        raise ValueError(f"Missing diffusion parameters: {', '.join(missing)}")

    validated: dict[str, float | int] = {
        "n_tissue": float(params["n_tissue"]),
        "n_out": float(params["n_out"]),
        "mu_a_min": float(params["mu_a_min"]),
        "mu_a_max": float(params["mu_a_max"]),
        "n_grid": int(params["n_grid"]),
    }

    if validated["n_tissue"] <= 0.0:
        raise ValueError("n_tissue must be > 0.")
    if validated["n_out"] <= 0.0:
        raise ValueError("n_out must be > 0.")
    if validated["mu_a_min"] <= 0.0:
        raise ValueError("mu_a_min must be > 0.")
    if validated["mu_a_max"] <= 0.0:
        raise ValueError("mu_a_max must be > 0.")
    if validated["mu_a_max"] <= validated["mu_a_min"]:
        raise ValueError("mu_a_max must be > mu_a_min.")
    if validated["n_grid"] < 32:
        raise ValueError("n_grid must be >= 32.")

    return validated


def get_default_slab_parameters() -> dict[str, float | int | str]:
    """Return default parameters for the slab diffusion model solver."""
    return {
        "n_tissue": SLAB_N_TISSUE,
        "thickness_mm": SLAB_THICKNESS_MM,
        "mode": SLAB_DEFAULT_MODE,
        "c_max": SLAB_C_MAX,
        "c_steps": SLAB_C_STEPS,
        "anisotropy_g": SCATTERING_ANISOTROPY_G,
    }


def validate_slab_parameters(params: dict) -> dict[str, float | int | str]:
    """Coerce and validate slab diffusion model parameters."""
    required = ("n_tissue", "thickness_mm", "mode", "c_max", "c_steps", "anisotropy_g")
    missing = [k for k in required if k not in params]
    if missing:
        raise ValueError(f"Missing slab parameters: {', '.join(missing)}")

    mode = str(params["mode"]).strip().lower()
    if mode not in {"diffuse", "collim"}:
        raise ValueError("mode must be either 'diffuse' or 'collim'.")

    validated: dict[str, float | int | str] = {
        "n_tissue": float(params["n_tissue"]),
        "thickness_mm": float(params["thickness_mm"]),
        "mode": mode,
        "c_max": float(params["c_max"]),
        "c_steps": int(params["c_steps"]),
        "anisotropy_g": float(params["anisotropy_g"]),
    }

    if validated["n_tissue"] <= 0:
        raise ValueError("n_tissue must be > 0.")
    if validated["thickness_mm"] <= 0:
        raise ValueError("thickness_mm must be > 0.")
    if validated["c_max"] <= 0:
        raise ValueError("c_max must be > 0.")
    if validated["c_steps"] < 2:
        raise ValueError("c_steps must be >= 2.")
    if not (0.0 <= float(validated["anisotropy_g"]) < 1.0):
        raise ValueError("anisotropy_g must satisfy 0 <= g < 1.")

    return validated


def build_fixed_scattering_spectrum(
    common_wl: np.ndarray,
    scattering_parameters: dict | None = None,
    **legacy_parameters,
) -> np.ndarray:
    """Return the wavelength-resolved reduced scattering prior μs'(λ)."""
    if scattering_parameters is None:
        scattering_parameters = dict(legacy_parameters)
    elif legacy_parameters:
        scattering_parameters = {**scattering_parameters, **legacy_parameters}

    params = validate_scattering_parameters(scattering_parameters)
    wl_safe = np.clip(np.asarray(common_wl, dtype=float), 1e-6, None)

    if params["model"] == SCATTERING_MODEL_SPECTRUM:
        mu_s_prime = interpolate_mu_s_prime_spectrum(
            params["spectrum_wavelengths_nm"],
            params["spectrum_values_cm1"],
            wl_safe,
        )
        mu_s_prime *= params["lipofundin_fraction"]
        return np.nan_to_num(mu_s_prime, nan=0.0, posinf=0.0, neginf=0.0)

    mu_s = (
        params["mu_s_500_cm1"]
        * (wl_safe / params["lambda0_nm"]) ** (-params["power_b"])
    )
    mu_s *= params["lipofundin_fraction"]
    mu_s_prime = mu_s * (1.0 - params["anisotropy_g"])

    # Warn if non-finite values are being silently replaced.
    if not np.all(np.isfinite(mu_s_prime)):
        n_bad = int(np.sum(~np.isfinite(mu_s_prime)))
        logger.warning(
            "build_fixed_scattering_spectrum: %d non-finite value(s) "
            "replaced with 0.0; check scattering parameters.",
            n_bad,
        )

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
    # --- Shape validation ---------------------------------------------------
    sample_cube = np.asarray(sample_cube, dtype=float)
    ref_cube = np.asarray(ref_cube, dtype=float)
    dark_cube = np.asarray(dark_cube, dtype=float)

    for name, arr in (
        ("sample_cube", sample_cube),
        ("ref_cube", ref_cube),
        ("dark_cube", dark_cube),
    ):
        if arr.ndim != 3:
            raise ValueError(f"{name} must be a 3-D array (H, W, N_bands), got ndim={arr.ndim}.")
        if arr.shape[-1] == 0:
            raise ValueError(f"{name} must have at least one spectral band.")
        if arr.shape[0] == 0 or arr.shape[1] == 0:
            raise ValueError(f"{name} spatial dimensions must be >= 1.")

    shape = sample_cube.shape
    if ref_cube.shape != shape or dark_cube.shape != shape:
        raise ValueError(
            f"Shape mismatch: sample_cube {sample_cube.shape}, "
            f"ref_cube {ref_cube.shape}, dark_cube {dark_cube.shape} "
            f"(all must be identical)."
        )
    # -----------------------------------------------------------------------
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
        if led_nm not in led_emission:
            raise KeyError(
                f"LED emission data missing for centre wavelength {led_nm}. "
                f"Available keys: {list(led_emission)}."
            )
        phi = np.asarray(led_emission[led_nm], dtype=float).copy()
        area = np.trapezoid(phi, common_wl)
        if area <= 0:
            logger.warning(
                "LED profile for %s nm has zero or negative area (%.3g); "
                "normalisation is skipped.",
                led_nm,
                float(area),
            )
        else:
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
    background_slope_start: float = BACKGROUND_SLOPE_START,
    background_slope_end: float = BACKGROUND_SLOPE_END,
    background_scattering_lambda0_nm: float = BACKGROUND_SCATTERING_LAMBDA0_NM,
    background_scattering_power_b: float = BACKGROUND_SCATTERING_POWER_B,
    chromophore_scale: float = 1.0,
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
        7. Append background column (constant, exponential, or slope basis).

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
        "constant", "exponential", or "slope" background basis.
    background_exp_start, background_exp_end : float, optional
        Exponential background values at the shortest and longest LED
        wavelengths respectively.
    background_exp_shape : float, optional
        Curvature parameter; values above 1 delay the decay and values below
        1 make it happen earlier.
    background_exp_offset : float, optional
        Additive baseline/floor for the exponential background.
    background_slope_start, background_slope_end : float, optional
        Linear slope background values at the shortest and longest LED
        wavelengths respectively.
    background_scattering_lambda0_nm, background_scattering_power_b : float, optional
        Power-law scattering-shaped background basis parameters used when
        background_model="scattering".
    chromophore_scale : float, optional
        Multiplier applied to chromophore extinction overlaps (use ``LN10`` when
        CSV extinctions are decadic and OD uses log10 reflectance).

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
    pen_wl_arr = np.asarray(penetration_wl, dtype=float).reshape(-1)
    pen_depth_arr = np.asarray(penetration_depth, dtype=float).reshape(-1)
    if len(pen_wl_arr) != len(pen_depth_arr):
        raise ValueError(
            "penetration_wl and penetration_depth must have the same length."
        )
    if not np.all(np.isfinite(pen_wl_arr)):
        raise ValueError("penetration_wl contains non-finite values.")
    if not np.all(np.isfinite(pen_depth_arr)):
        raise ValueError("penetration_depth contains non-finite values.")

    pen_wl_prepared, pen_depth_prepared = _prepare_interp_axis(
        pen_wl_arr,
        pen_depth_arr,
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
    chromophore_scale = float(chromophore_scale)
    if not np.isfinite(chromophore_scale) or chromophore_scale <= 0:
        raise ValueError("chromophore_scale must be a finite number > 0.")

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
            slope_start=background_slope_start,
            slope_end=background_slope_end,
            scattering_lambda0_nm=background_scattering_lambda0_nm,
            scattering_power_b=background_scattering_power_b,
        )

    for i, phi in enumerate(led_profiles):
        # Overlap pathlength: l^n = ∫ phi_n(λ) * l(λ) dλ
        l_n = np.trapezoid(phi * depth_interp, common_wl)

        # Overlap extinction for each chromophore
        for j, name in enumerate(chromophore_names):
            eps_k_n = chromophore_scale * np.trapezoid(phi * chrom_interp[name], common_wl)
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
    chromophore_scale: float = 1.0,
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
    chromophore_scale = float(chromophore_scale)
    if not np.isfinite(chromophore_scale) or chromophore_scale <= 0:
        raise ValueError("chromophore_scale must be a finite number > 0.")

    chromophore_names, chrom_interp = _interpolate_chromophore_spectra(
        common_wl,
        chromophore_spectra,
        chromophore_names=chromophore_names,
    )

    E = np.zeros((len(led_wavelengths), len(chromophore_names)))
    for i, phi in enumerate(led_profiles):
        for j, name in enumerate(chromophore_names):
            E[i, j] = chromophore_scale * np.trapezoid(phi * chrom_interp[name], common_wl)

    return E, chromophore_names


def build_fixed_scattering_profile(
    led_emission_wl: np.ndarray,
    led_emission: dict,
    led_wavelengths: list,
    scattering_parameters: dict | None = None,
    **legacy_parameters,
) -> np.ndarray:
    """
    Build the LED-band reduced scattering prior μs'(λ) for the fixed-scattering solver.
    """
    if scattering_parameters is None:
        scattering_parameters = dict(legacy_parameters)
    elif legacy_parameters:
        scattering_parameters = {**scattering_parameters, **legacy_parameters}

    common_wl, led_profiles = _normalized_led_profiles(
        led_emission_wl,
        led_emission,
        led_wavelengths,
    )

    mu_s_prime_wl = build_fixed_scattering_spectrum(
        common_wl,
        scattering_parameters=scattering_parameters,
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
    scattering_parameters: dict | None = None,
    chromophore_scale: float = 1.0,
    eps: float = 1e-10,
    **legacy_parameters,
) -> np.ndarray:
    """Estimate wavelength-dependent effective pathlength from mean absorption."""
    chromophore_scale = float(chromophore_scale)
    if not np.isfinite(chromophore_scale) or chromophore_scale <= 0:
        raise ValueError("chromophore_scale must be a finite number > 0.")
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
        mu_a += (
            max(float(c_mean[idx]), 0.0)
            * chromophore_scale
            * np.clip(coeff_interp, 0.0, None)
        )

    mu_a = np.clip(mu_a, eps, None)
    if scattering_parameters is None:
        scattering_parameters = dict(legacy_parameters)
    elif legacy_parameters:
        scattering_parameters = {**scattering_parameters, **legacy_parameters}

    mu_s_prime = build_fixed_scattering_spectrum(
        common_wl,
        scattering_parameters=scattering_parameters,
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
    background_slope_start: float = BACKGROUND_SLOPE_START,
    background_slope_end: float = BACKGROUND_SLOPE_END,
    background_scattering_lambda0_nm: float = BACKGROUND_SCATTERING_LAMBDA0_NM,
    background_scattering_power_b: float = BACKGROUND_SCATTERING_POWER_B,
    max_iter: int = ITERATIVE_MAX_ITER,
    tol_rel: float = ITERATIVE_TOL_REL,
    tol_rmse: float = ITERATIVE_TOL_RMSE,
    damping: float = ITERATIVE_DAMPING,
    initial_concentration: float = ITERATIVE_INITIAL_CONCENTRATION,
    scattering_parameters: dict | None = None,
    chromophore_scale: float = 1.0,
) -> tuple:
    """Iterative overlap-matrix unmixing with a diffusion-inspired pathlength."""
    chromophore_scale = float(chromophore_scale)
    if not np.isfinite(chromophore_scale) or chromophore_scale <= 0:
        raise ValueError("chromophore_scale must be a finite number > 0.")
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
        "slope_start": background_slope_start,
        "slope_end": background_slope_end,
        "scattering_lambda0_nm": background_scattering_lambda0_nm,
        "scattering_power_b": background_scattering_power_b,
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

    try:
        l_curr = estimate_effective_pathlength(
            concentrations=current_conc_map,
            chromophore_names=chrom_names,
            chromophore_spectra=chromophore_spectra,
            common_wl=common_wl,
            scattering_parameters=params,
            chromophore_scale=chromophore_scale,
        )

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
                background_slope_start=background_params["slope_start"],
                background_slope_end=background_params["slope_end"],
                background_scattering_lambda0_nm=background_params["scattering_lambda0_nm"],
                background_scattering_power_b=background_params["scattering_power_b"],
                chromophore_scale=chromophore_scale,
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
                scattering_parameters=params,
                chromophore_scale=chromophore_scale,
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

    except (ValueError, RuntimeError) as exc:
        stop_reason = "iterative_error"
        iterative_error = f"{type(exc).__name__}: {exc}"
        fallback_used = True
        logger.error(
            "Iterative unmixing error at iteration %d: %s",
            len(history) + 1,
            iterative_error,
        )
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
            fallback_reason = (
                "Iterative unmixing failed before any successful iterate; "
                "static overlap matrix fallback was used."
            )
            try:
                concentrations, rmse_map, fitted_od = _solve_unmixing_nnls(od_cube, A_last)
            except Exception as fallback_exc:
                logger.error(
                    "Static fallback also failed: %s",
                    fallback_exc,
                )
                raise RuntimeError(
                    f"Iterative unmixing error: {iterative_error}. "
                    f"Static fallback also failed: {fallback_exc}"
                ) from fallback_exc
            pathlength_used = common_wl.copy()

    except Exception as exc:
        logger.error(
            "Unexpected exception in iterative unmixing: %s",
            exc,
        )
        raise RuntimeError(
            f"Unexpected error in iterative unmixing: {exc}"
        ) from exc

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
        "chromophore_scale": float(chromophore_scale),
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
    diffusion_parameters: dict | None = None,
    slab_parameters: dict | None = None,
    slab_mua_env: np.ndarray | None = None,
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
    if method == "diffusion":
        if mus_prime is None:
            raise ValueError("mus_prime is required for method='diffusion'.")
        params = get_default_diffusion_parameters()
        if diffusion_parameters is not None:
            params.update(diffusion_parameters)
        params = validate_diffusion_parameters(params)
        return _solve_unmixing_diffusion(
            od_cube,
            A,
            mus_prime,
            n_tissue=float(params["n_tissue"]),
            n_out=float(params["n_out"]),
            mu_a_min=float(params["mu_a_min"]),
            mu_a_max=float(params["mu_a_max"]),
            n_grid=int(params["n_grid"]),
        )
    if method == "slab":
        if mus_prime is None:
            raise ValueError("mus_prime is required for method='slab'.")
        # This solver is defined for a single spectrum; we fit the mean spectrum
        # and broadcast the coefficients across the image.
        reflectance_cube = 10.0 ** (-np.asarray(od_cube, dtype=float))
        if reflectance_cube.ndim != 3:
            raise ValueError("od_cube must have shape (H, W, N_bands).")
        H, W, N = reflectance_cube.shape
        if A.shape[0] != N:
            raise ValueError("For method='slab', A must have one row per band.")
        mean_ref = np.nanmean(np.where(np.isfinite(reflectance_cube), reflectance_cube, np.nan), axis=(0, 1))
        best_C, sim_ref = solve_unmixing_slab(
            reflectance=mean_ref,
            extinction_coefs=A,
            mus_prime=mus_prime,
            slab_parameters=slab_parameters,
            mua_env=slab_mua_env,
        )
        concentrations = np.tile(best_C.reshape(1, 1, -1), (H, W, 1))
        fitted_od_vec = -np.log10(np.clip(sim_ref, 1e-12, None))
        fitted_od = np.tile(fitted_od_vec.reshape(1, 1, -1), (H, W, 1))
        residual_per_pixel = np.asarray(od_cube, dtype=float) - fitted_od
        rmse_map = np.sqrt(np.mean(residual_per_pixel ** 2, axis=2))
        return concentrations, rmse_map, fitted_od
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


def _welch_reflectance(
    mu_a: np.ndarray,
    mu_s_prime: np.ndarray,
    anisotropy_g: float,
    n_tissue: float,
    n_out: float = 1.0,
    eps: float = 1e-12,
) -> np.ndarray:
    """
    Welch-style diffusion approximation reflectance (Case 6.4.1.6).

    Maps optical properties -> diffuse wide-beam reflectance with a mismatched boundary.
    """
    mu_a = np.asarray(mu_a, dtype=float)
    mu_s_prime = np.asarray(mu_s_prime, dtype=float).reshape(-1)
    if mu_a.shape[-1] != mu_s_prime.shape[0]:
        raise ValueError("mu_a last dimension must match mu_s_prime length.")
    if not (0.0 <= float(anisotropy_g) < 1.0):
        raise ValueError("anisotropy_g must satisfy 0 <= g < 1.")
    if float(n_tissue) <= 0.0 or float(n_out) <= 0.0:
        raise ValueError("Refractive indices must be > 0.")

    mu_a_clipped = np.clip(mu_a, eps, None)
    mu_tr = mu_a_clipped + mu_s_prime
    mu_eff = np.sqrt(3.0 * mu_a_clipped * mu_tr)

    q = (mu_eff - 2.0 * mu_a_clipped) / np.clip(mu_eff + 2.0 * mu_a_clipped, eps, None)

    n_rel = float(n_tissue) / float(n_out)
    r21 = -1.440 / (n_rel ** 2) + 0.710 / n_rel + 0.668 + 0.0636 * n_rel
    r_sd = ((n_rel - 1.0) / (n_rel + 1.0)) ** 2

    den = 1.0 - r21 * q
    den = np.where(np.abs(den) < eps, np.sign(den) * eps, den)

    R_diffuse = (1.0 - r21) * (1.0 - r_sd) * (q / den)
    R_total = r_sd + R_diffuse
    return np.clip(R_total, 0.0, 1.0)


def _invert_welch_mu_a_from_reflectance(
    reflectance: np.ndarray,
    mu_s_prime: np.ndarray,
    anisotropy_g: float,
    n_tissue: float,
    n_out: float = 1.0,
    mu_a_min: float = 1e-6,
    mu_a_max: float = 10.0,
    n_grid: int = 512,
    eps: float = 1e-12,
) -> tuple[np.ndarray, np.ndarray]:
    """Invert Welch reflectance to estimate mu_a per band using a lookup table."""
    reflectance = np.asarray(reflectance, dtype=float)
    mu_s_prime = np.asarray(mu_s_prime, dtype=float).reshape(-1)
    if reflectance.shape[-1] != mu_s_prime.shape[0]:
        raise ValueError("reflectance last dimension must match mu_s_prime length.")
    if mu_a_min <= 0.0 or mu_a_max <= 0.0 or mu_a_max <= mu_a_min:
        raise ValueError("mu_a_min/mu_a_max must be positive and mu_a_max > mu_a_min.")
    n_grid = int(n_grid)
    if n_grid < 32:
        raise ValueError("n_grid must be >= 32.")

    R = np.clip(reflectance, 0.0, 1.0)
    finite = np.isfinite(R)
    mu_a_out = np.full_like(R, float(mu_a_min), dtype=float)

    mu_a_grid = np.logspace(np.log10(mu_a_min), np.log10(mu_a_max), n_grid, dtype=float)
    n_bands = mu_s_prime.shape[0]

    R_min = np.full(n_bands, np.nan, dtype=float)
    R_max = np.full(n_bands, np.nan, dtype=float)
    tables: list[tuple[np.ndarray, np.ndarray]] = []
    for b in range(n_bands):
        R_b = _welch_reflectance(
            mu_a_grid[:, np.newaxis],
            mu_s_prime=np.asarray([mu_s_prime[b]]),
            anisotropy_g=float(anisotropy_g),
            n_tissue=float(n_tissue),
            n_out=float(n_out),
            eps=eps,
        ).reshape(-1)
        order = np.argsort(R_b)
        R_sorted = R_b[order]
        mu_sorted = mu_a_grid[order]
        tables.append((R_sorted, mu_sorted))
        R_min[b] = float(np.nanmin(R_sorted))
        R_max[b] = float(np.nanmax(R_sorted))

    within = (R >= R_min) & (R <= R_max)
    valid = finite & within

    flat_R = R.reshape(-1, n_bands)
    flat_valid = valid.reshape(-1, n_bands)
    flat_mu = mu_a_out.reshape(-1, n_bands)
    for b in range(n_bands):
        ok = flat_valid[:, b]
        if not np.any(ok):
            continue
        R_sorted, mu_sorted = tables[b]
        flat_mu[ok, b] = np.interp(flat_R[ok, b], R_sorted, mu_sorted)

    return mu_a_out, valid


def _solve_unmixing_diffusion(
    od_cube: np.ndarray,
    E: np.ndarray,
    mus_prime: np.ndarray,
    anisotropy_g: float = SCATTERING_ANISOTROPY_G,
    n_tissue: float = 1.4,
    n_out: float = 1.0,
    mu_a_min: float = 1e-6,
    mu_a_max: float = 10.0,
    n_grid: int = 512,
    eps: float = 1e-12,
) -> tuple:
    """Welch diffusion OD→μa inversion followed by NNLS chromophore fit."""
    H, W, N = od_cube.shape
    n_components = E.shape[1]
    mus_prime = np.asarray(mus_prime, dtype=float).reshape(-1)

    if E.shape[0] != N:
        raise ValueError(
            "For method='diffusion', the absorption basis must have one row per OD band."
        )
    if mus_prime.shape[0] != N:
        raise ValueError(
            "For method='diffusion', mus_prime must have one entry per OD band."
        )

    reflectance = 10.0 ** (-np.asarray(od_cube, dtype=float))
    mu_a_est, valid = _invert_welch_mu_a_from_reflectance(
        reflectance,
        mu_s_prime=mus_prime,
        anisotropy_g=float(anisotropy_g),
        n_tissue=float(n_tissue),
        n_out=float(n_out),
        mu_a_min=float(mu_a_min),
        mu_a_max=float(mu_a_max),
        n_grid=int(n_grid),
        eps=eps,
    )

    Y = mu_a_est.reshape(-1, N)
    valid_flat = valid.reshape(-1, N)
    X = np.zeros((n_components, Y.shape[0]), dtype=float)
    fitted_mu_a = np.zeros((Y.shape[0], N), dtype=float)
    for i in range(Y.shape[0]):
        ok = valid_flat[i]
        if np.any(ok):
            X[:, i], _ = nnls(E[ok, :], Y[i, ok])
        fitted_mu_a[i, :] = E @ X[:, i]

    fitted_reflectance = _welch_reflectance(
        fitted_mu_a.reshape(H, W, N),
        mu_s_prime=mus_prime,
        anisotropy_g=float(anisotropy_g),
        n_tissue=float(n_tissue),
        n_out=float(n_out),
        eps=eps,
    )
    fitted_od = -np.log10(np.clip(fitted_reflectance, eps, None))

    concentrations = X.T.reshape(H, W, n_components)
    residual_per_pixel = np.asarray(od_cube, dtype=float) - fitted_od
    rmse_map = np.sqrt(np.mean(residual_per_pixel ** 2, axis=2))
    return concentrations, rmse_map, fitted_od


def _wnse(a: np.ndarray, b: np.ndarray) -> float:
    """Weighted-normalized squared error placeholder (ported from external code)."""
    a = np.asarray(a, dtype=float).reshape(-1)
    b = np.asarray(b, dtype=float).reshape(-1)
    if a.shape != b.shape:
        raise ValueError("wnse inputs must have the same shape.")
    diff = a - b
    return float(np.nanmean(diff * diff))


def _slab_r21_from_n(n: float) -> float:
    cos_theta_c = float(np.cos(np.arcsin(1.0 / float(n))))
    return float((cos_theta_c ** 2 + cos_theta_c ** 3) / (2.0 - cos_theta_c ** 2 + cos_theta_c ** 3))


def _slab_radiance_diffuse(mua: float, mus: float, g: float, n: float, z: float = 0.0) -> float:
    mu_eff = float(np.sqrt(3.0 * mua * (mua + (1.0 - g) * mus)))
    r_21 = _slab_r21_from_n(n)
    denom = mu_eff + 2.0 * mua
    if abs(denom) < 1e-12:
        logger.warning(f"_slab_radiance_diffuse: denominator (mu_eff + 2.0*mua) is near zero ({denom}), clamping to 1e-12")
        denom = 1e-12
    q = float((mu_eff - 2.0 * mua) / denom)

    denom_q = float(1.0 - r_21 * q)
    if abs(denom_q) < 1e-12:
        logger.warning(f"_slab_radiance_diffuse: denominator (1.0 - r_21*q) is near zero ({denom_q}), clamping to 1e-12")
        denom_q = 1e-12
    
    F_plus = float((1.0 / denom_q) * np.exp(-mu_eff * z))
    F_minus = float((q / denom_q) * np.exp(-mu_eff * z))

    return float((1.0 - r_21) * (F_minus - r_21 * F_plus))


def _slab_radiance_collim(mua: float, mus: float, g: float, n: float, d: float, z: float = 0.0) -> float:
    r_21 = _slab_r21_from_n(n)

    mu_tr = mua + mus * (1.0 - g)
    mu_t = mua + mus
    mu_eff = float(np.sqrt(3.0 * mua * mu_tr))

    S_p = (mus / 4.0) * ((5.0 + 9.0 * g) * mua + 5.0 * mus)
    S_m = (mus / 4.0) * ((1.0 - 3.0 * g) * mua + mus)

    # Protect against division by zero
    denom_A = mu_t ** 2 - mu_eff ** 2
    if abs(denom_A) < 1e-12:
        logger.warning(f"_slab_radiance_collim: denominator (mu_t**2 - mu_eff**2) is near zero ({denom_A}), clamping to 1e-12")
        denom_A = 1e-12
    
    A_p = -S_p / denom_A
    A_m = -S_m / denom_A

    denom = mu_eff + 2.0 * mua
    if abs(denom) < 1e-12:
        logger.warning(f"_slab_radiance_collim: denominator (mu_eff + 2.0*mua) is near zero ({denom}), clamping to 1e-12")
        denom = 1e-12
    q = (mu_eff - 2.0 * mua) / denom

    # Protect against division by zero for q
    if abs(q) < 1e-12:
        logger.warning(f"_slab_radiance_collim: parameter q is near zero ({q}), clamping to 1e-12")
        q = 1e-12

    # Denominator for A_mp and A_pm
    denom_AMP = q * np.exp(-mu_eff * d) - (1.0 / q) * np.exp(mu_eff * d)
    if abs(denom_AMP) < 1e-12:
        logger.warning(f"_slab_radiance_collim: denominator (q*exp(-mu_eff*d) - (1/q)*exp(mu_eff*d)) is near zero ({denom_AMP}), clamping to 1e-12")
        denom_AMP = 1e-12

    A_mp = (
        (-A_p * np.exp(-mu_eff * d) + (A_m / q) * np.exp(-mu_t * d))
        / denom_AMP
    )
    A_pm = (
        (((A_p / q) * np.exp(mu_eff * d) - A_m * np.exp(-mu_t * d)))
        / denom_AMP
    )

    A_pp = q * A_mp
    A_mm = q * A_pm

    F_p = A_pp * np.exp(mu_eff * z) + A_pm * np.exp(-mu_eff * z) + A_p * np.exp(-mu_t * z)
    F_m = A_mp * np.exp(mu_eff * z) + A_mm * np.exp(-mu_eff * z) + A_m * np.exp(-mu_t * z)

    return float((1.0 - r_21) * (F_m - r_21 * F_p))


def _slab_get_intensities(
    mua_env: np.ndarray,
    mus: np.ndarray,
    g: float,
    n: float,
    d: float,
    mode: str,
    coefficients: np.ndarray,
    extinction_coefs: np.ndarray,
) -> np.ndarray:
    res: list[float] = []
    for i in range(len(mua_env)):
        mua_total = float(mua_env[i] + LN10 * float(coefficients @ extinction_coefs[i]))
        mus_i = float(mus[i])
        if mode == "diffuse":
            R = _slab_radiance_diffuse(mua_total, mus_i, g=g, n=n, z=0.0)
        else:
            R = _slab_radiance_collim(mua_total, mus_i, g=g, n=n, d=d, z=0.0)
        res.append(R)
    return np.asarray(res, dtype=float)


def _slab_fit_data(
    reflectances: np.ndarray,
    extinction_coefs: np.ndarray,
    mua_env: np.ndarray,
    mus: np.ndarray,
    g: float,
    n: float,
    d: float,
    mode: str,
    c_max: float,
    c_steps: int,
) -> np.ndarray:
    reflectances = np.asarray(reflectances, dtype=float).reshape(-1)
    if np.any(~np.isfinite(reflectances)):
        raise ValueError("reflectances must be finite for slab fitting.")
    if reflectances.size != extinction_coefs.shape[0]:
        raise ValueError("reflectances length must match extinction_coefs rows.")

    n_components = extinction_coefs.shape[1]
    
    # Use logarithmic grid from 1e-8 to c_max for better coverage
    
    c_min = 1e-6
    n_components = extinction_coefs.shape[1]
    grid = np.linspace(c_min, float(c_max), int(c_steps))
    C_range = itertools.product(grid, repeat=n_components)

    min_err = float("inf")
    best_C = (-1.0) * np.ones(n_components, dtype=float)
    
    # Log grid search info
    n_combinations = int(len(grid) ** n_components)
    logger.info(f"_slab_fit_data: Grid search over {n_combinations} concentration combinations ({len(grid)}^{n_components})")
    denom_ref = float(np.max(reflectances)) if float(np.max(reflectances)) != 0.0 else 1.0
    ref_norm = reflectances / denom_ref

    for C in C_range:
        sim_refs = _slab_get_intensities(
            mua_env=mua_env,
            mus=mus,
            g=g,
            n=n,
            d=d,
            mode=mode,
            coefficients=np.asarray(C, dtype=float),
            extinction_coefs=extinction_coefs,
        )
        denom_sim = float(np.max(sim_refs)) if float(np.max(sim_refs)) != 0.0 else 1.0
        sim_norm = sim_refs / denom_sim
        err = _wnse(ref_norm, sim_norm)
        if err < min_err:
            min_err = err
            best_C = np.asarray(C, dtype=float)

    return best_C


def solve_unmixing_slab(
    reflectance: np.ndarray,
    extinction_coefs: np.ndarray,
    mus_prime: np.ndarray,
    slab_parameters: dict | None = None,
    mua_env: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Fit slab diffusion model coefficients to a single reflectance spectrum.

    This is a direct port of DiffusionModelForSlab.fit_data + get_intensities.

    Returns
    -------
    best_C : (N_components,)
    sim_reflectance : (N_bands,)
    """
    params = get_default_slab_parameters()
    if slab_parameters is not None:
        params.update(slab_parameters)
    params = validate_slab_parameters(params)

    reflectance = np.asarray(reflectance, dtype=float).reshape(-1)
    extinction_coefs = np.asarray(extinction_coefs, dtype=float)
    mus_prime = np.asarray(mus_prime, dtype=float).reshape(-1)
    if reflectance.shape[0] != extinction_coefs.shape[0]:
        raise ValueError("reflectance length must match extinction_coefs rows.")
    if mus_prime.shape[0] != reflectance.shape[0]:
        raise ValueError("mus_prime length must match reflectance length.")

    g = float(params["anisotropy_g"])

    mus = mus_prime / max(1.0 - g, 1e-12)
    mua_env_vec = np.zeros_like(reflectance) if mua_env is None else np.asarray(mua_env, dtype=float).reshape(-1)
    if mua_env_vec.shape[0] != reflectance.shape[0]:
        raise ValueError("mua_env length must match reflectance length.")

    best_C = _slab_fit_data(
        reflectances=reflectance,
        extinction_coefs=extinction_coefs,
        mua_env=mua_env_vec,
        mus=mus,
        g=g,
        n=float(params["n_tissue"]),
        d=float(params["thickness_mm"]),
        mode=str(params["mode"]),
        c_max=float(params["c_max"]),
        c_steps=int(params["c_steps"]),
    )
    sim_reflectance = _slab_get_intensities(
        mua_env=mua_env_vec,
        mus=mus,
        g=g,
        n=float(params["n_tissue"]),
        d=float(params["thickness_mm"]),
        mode=str(params["mode"]),
        coefficients=best_C,
        extinction_coefs=extinction_coefs,
    )
    return best_C, sim_reflectance


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
