"""Calibration helpers for bilirubin-index forward models.

The models in this module convert a dimensionless bilirubin diagnostic index
(e.g. OD450 - OD517) into a domain-calibrated estimate. They are not spectral
unmixing concentration solvers and must carry calibration-domain metadata.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA_VERSION = 1
DEFAULT_DISCLAIMER = (
    "⚠ DISCLAIMER: This is a domain-calibrated diagnostic estimate from a "
    "two-band bilirubin index, not an absolute physical bilirubin concentration "
    "and not a spectral-unmixing result. Interpret only within the stated "
    "calibration domain."
)


@dataclass(eq=True)
class CalibrationModel:
    """Serializable bilirubin-index calibration model."""

    schema_version: int = SCHEMA_VERSION
    fit_type: str = "log_linear"
    index_formula: str = "OD450 - OD517"
    coefficients: dict[str, float] = field(default_factory=dict)
    k_hb_correction: float | None = None
    calibration_domain: dict[str, Any] = field(default_factory=dict)
    fit_quality: dict[str, Any] = field(default_factory=dict)
    disclaimer: str = DEFAULT_DISCLAIMER
    independently_validated: bool = False

    @property
    def slope(self) -> float:
        try:
            return float(self.coefficients["slope"])
        except KeyError:
            raise AttributeError("CalibrationModel has no 'slope' coefficient.")

    @property
    def intercept(self) -> float:
        try:
            return float(self.coefficients["intercept"])
        except KeyError:
            raise AttributeError("CalibrationModel has no 'intercept' coefficient.")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if not data.get("disclaimer"):
            data["disclaimer"] = DEFAULT_DISCLAIMER
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibrationModel":
        _validate_model_dict(data)
        return cls(
            schema_version=int(data["schema_version"]),
            fit_type=str(data["fit_type"]),
            index_formula=str(data.get("index_formula", "OD450 - OD517")),
            coefficients={k: float(v) for k, v in data["coefficients"].items()},
            k_hb_correction=(
                None if data.get("k_hb_correction") is None else float(data["k_hb_correction"])
            ),
            calibration_domain=dict(data.get("calibration_domain", {})),
            fit_quality=dict(data.get("fit_quality", {})),
            disclaimer=str(data.get("disclaimer") or DEFAULT_DISCLAIMER),
            independently_validated=bool(data.get("independently_validated", False)),
        )


def fit_calibration(
    index_values: np.ndarray,
    truth_uM: np.ndarray,
    *,
    fit_type: str = "log_linear",
    index_formula: str = "OD450 - OD517",
    k_hb_correction: float | None = None,
    calibration_domain: dict[str, Any] | None = None,
    independently_validated: bool = False,
) -> CalibrationModel:
    """Fit a bilirubin-index calibration model.

    For ``fit_type='log_linear'`` the fitted forward model is::

        index = slope * log10(truth_uM) + intercept
    """
    index = np.asarray(index_values, dtype=float).reshape(-1)
    truth = np.asarray(truth_uM, dtype=float).reshape(-1)
    if index.shape != truth.shape:
        raise ValueError("index_values and truth_uM must have the same shape.")
    if index.size < 3:
        raise ValueError("At least three calibration samples are required.")
    if np.any(~np.isfinite(index)) or np.any(~np.isfinite(truth)):
        raise ValueError("Calibration inputs must be finite.")
    if np.any(truth <= 0):
        raise ValueError("truth_uM must be positive for log-linear calibration.")
    if fit_type != "log_linear":
        raise ValueError(f"Unsupported calibration fit_type: {fit_type!r}")
    if np.allclose(index, index[0]):
        raise ValueError("Calibration index values are constant; cannot fit a log-linear model.")

    x = np.log10(truth)
    slope, intercept = _linear_coefficients(x, index)
    fitted_index = slope * x + intercept
    in_sample_r2 = _r2_score(index, fitted_index)
    fitted_uM = _invert_log_linear(index, slope, intercept)
    loo_uM = _loo_predictions(index, truth)
    loo_r2 = _r2_score(truth, loo_uM)
    rmse_uM = float(np.sqrt(np.nanmean((fitted_uM - truth) ** 2)))

    domain = dict(calibration_domain or {})
    domain.setdefault("bilirubin_uM_min", float(np.min(truth)))
    domain.setdefault("bilirubin_uM_max", float(np.max(truth)))

    return CalibrationModel(
        fit_type=fit_type,
        index_formula=index_formula,
        coefficients={"slope": float(slope), "intercept": float(intercept)},
        k_hb_correction=k_hb_correction,
        calibration_domain=domain,
        fit_quality={
            "in_sample_r2": float(in_sample_r2),
            "loo_r2": float(loo_r2),
            "rmse_uM": rmse_uM,
            "n_samples": int(index.size),
        },
        disclaimer=DEFAULT_DISCLAIMER,
        independently_validated=independently_validated,
    )


def apply_calibration(
    index_values: np.ndarray,
    model: CalibrationModel,
    *,
    clip_to_domain: bool = True,
) -> np.ndarray:
    """Apply a calibration model to an index map or vector.

    Returns a numeric estimate in the model's calibration scale. Values are
    clipped to the calibration-domain min/max by default to avoid silent
    extrapolation beyond the fitted range.
    """
    if model.fit_type != "log_linear":
        raise ValueError(f"Unsupported calibration fit_type: {model.fit_type!r}")
    est = _invert_log_linear(np.asarray(index_values, dtype=float), model.slope, model.intercept)
    if clip_to_domain:
        min_uM, max_uM = _domain_bounds(model)
        if min_uM is not None and max_uM is not None:
            est = np.clip(est, min_uM, max_uM)
    return est


def calibration_clamp_counts(index_values: np.ndarray, model: CalibrationModel) -> dict[str, int]:
    """Return low/high pixel counts that would be clipped by apply_calibration."""
    raw = _invert_log_linear(np.asarray(index_values, dtype=float), model.slope, model.intercept)
    min_uM, max_uM = _domain_bounds(model)
    if min_uM is None or max_uM is None:
        return {"n_pixels_clamped_low": 0, "n_pixels_clamped_high": 0}
    finite = np.isfinite(raw)
    return {
        "n_pixels_clamped_low": int(np.sum(finite & (raw < min_uM))),
        "n_pixels_clamped_high": int(np.sum(finite & (raw > max_uM))),
    }


def save_calibration(model: CalibrationModel, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model.to_dict(), indent=2, sort_keys=True) + "\n")


def load_calibration(path: str | Path) -> CalibrationModel:
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("Calibration JSON must contain an object.")
    return CalibrationModel.from_dict(data)


def get_default_calibration_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "calibrations" / "bilirubin_a1a6_log_linear.json"


def model_summary_for_metadata(model: CalibrationModel | dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a compact calibration metadata block for exports."""
    if model is None:
        return None
    if isinstance(model, CalibrationModel):
        data = model.to_dict()
    elif isinstance(model, dict) and "coefficients" in model:
        data = model
    else:
        return None
    return {
        "disclaimer": data.get("disclaimer") or DEFAULT_DISCLAIMER,
        "independently_validated": bool(data.get("independently_validated", False)),
        "fit_type": data.get("fit_type"),
        "index_formula": data.get("index_formula"),
        "coefficients": data.get("coefficients", {}),
        "k_hb_correction": data.get("k_hb_correction"),
        "calibration_domain": data.get("calibration_domain", {}),
        "fit_quality": data.get("fit_quality", {}),
    }


def _validate_model_dict(data: dict[str, Any]) -> None:
    required = ["schema_version", "fit_type", "coefficients"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Calibration JSON missing required keys: {', '.join(missing)}")
    if int(data["schema_version"]) != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported calibration schema_version {data['schema_version']!r}; expected {SCHEMA_VERSION}."
        )
    if data["fit_type"] != "log_linear":
        raise ValueError(f"Unsupported calibration fit_type: {data['fit_type']!r}")
    coeffs = data["coefficients"]
    if not isinstance(coeffs, dict) or "slope" not in coeffs or "intercept" not in coeffs:
        raise ValueError("Calibration coefficients must include slope and intercept.")
    slope = float(coeffs["slope"])
    intercept = float(coeffs["intercept"])
    if not np.isfinite(slope) or not np.isfinite(intercept):
        raise ValueError("Calibration coefficients must be finite.")
    if abs(slope) < 1e-12:
        raise ValueError("Calibration slope is too close to zero.")


def _linear_coefficients(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    design = np.column_stack([x, np.ones_like(x)])
    slope, intercept = np.linalg.lstsq(design, y, rcond=None)[0]
    return float(slope), float(intercept)


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    if int(np.sum(mask)) < 2:
        return float("nan")
    y_true = y_true[mask]
    y_pred = y_pred[mask]
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0


def _invert_log_linear(index: np.ndarray, slope: float, intercept: float) -> np.ndarray:
    if not np.isfinite(slope) or not np.isfinite(intercept):
        raise ValueError("Calibration coefficients must be finite.")
    if abs(slope) < 1e-12:
        raise ValueError("Calibration slope is too close to zero.")
    with np.errstate(over="ignore", invalid="ignore"):
        return 10 ** ((np.asarray(index, dtype=float) - intercept) / slope)


def _loo_predictions(index_values: np.ndarray, truth_uM: np.ndarray) -> np.ndarray:
    preds = np.full_like(truth_uM, np.nan, dtype=float)
    log_truth = np.log10(truth_uM)
    for idx in range(len(truth_uM)):
        mask = np.ones(len(truth_uM), dtype=bool)
        mask[idx] = False
        try:
            slope, intercept = _linear_coefficients(log_truth[mask], index_values[mask])
            preds[idx] = _invert_log_linear(index_values[idx], slope, intercept)
        except (ValueError, np.linalg.LinAlgError):
            preds[idx] = np.nan
    return preds


def _domain_bounds(model: CalibrationModel) -> tuple[float | None, float | None]:
    domain = model.calibration_domain or {}
    min_value = domain.get("bilirubin_uM_min", domain.get("bili_uM_min"))
    max_value = domain.get("bilirubin_uM_max", domain.get("bili_uM_max"))
    if min_value is None or max_value is None:
        return None, None
    return float(min_value), float(max_value)
