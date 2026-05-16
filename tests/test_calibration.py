from __future__ import annotations

import json

import numpy as np
import pytest

from app.core.calibration import (
    CalibrationModel,
    apply_calibration,
    calibration_clamp_counts,
    fit_calibration,
    load_calibration,
    model_summary_for_metadata,
    save_calibration,
)


def test_fit_log_linear_synthetic_recovers_coefficients():
    truth = np.array([1.0, 10.0, 100.0, 1000.0])
    index = 0.02 * np.log10(truth) + 0.003

    model = fit_calibration(index, truth)

    assert model.fit_type == "log_linear"
    assert model.coefficients["slope"] == pytest.approx(0.02)
    assert model.coefficients["intercept"] == pytest.approx(0.003)
    assert model.fit_quality["in_sample_r2"] == pytest.approx(1.0)


def test_apply_calibration_inverts_synthetic_fit():
    truth = np.array([5.0, 25.0, 125.0])
    index = 0.015 * np.log10(truth) - 0.001
    model = fit_calibration(index, truth)

    estimated = apply_calibration(index, model)

    np.testing.assert_allclose(estimated, truth, rtol=1e-10, atol=1e-10)


def test_apply_calibration_clips_to_domain_and_reports_counts():
    model = CalibrationModel(
        coefficients={"slope": 0.02, "intercept": 0.0},
        calibration_domain={"bilirubin_uM_min": 10.0, "bilirubin_uM_max": 100.0},
    )
    index = 0.02 * np.log10(np.array([1.0, 50.0, 200.0]))

    estimated = apply_calibration(index, model)
    counts = calibration_clamp_counts(index, model)

    np.testing.assert_allclose(estimated, [10.0, 50.0, 100.0])
    assert counts == {"n_pixels_clamped_low": 1, "n_pixels_clamped_high": 1}


def test_save_load_roundtrip(tmp_path):
    model = CalibrationModel(
        index_formula="OD450 - OD517",
        coefficients={"slope": 0.014, "intercept": -0.0002},
        k_hb_correction=None,
        calibration_domain={"bilirubin_uM_min": 8.4, "bilirubin_uM_max": 270.0},
        fit_quality={"in_sample_r2": 0.94, "loo_r2": -4.4, "n_samples": 6},
        independently_validated=False,
    )
    path = tmp_path / "calibration.json"

    save_calibration(model, path)
    loaded = load_calibration(path)

    assert loaded == model


def test_load_rejects_unknown_schema_version(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 99, "fit_type": "log_linear", "coefficients": {"slope": 1, "intercept": 0}}))

    with pytest.raises(ValueError, match="schema_version"):
        load_calibration(path)


def test_load_rejects_missing_coefficients(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": 1, "fit_type": "log_linear"}))

    with pytest.raises(ValueError, match="missing"):
        load_calibration(path)


@pytest.mark.parametrize("truth", [np.array([0.0, 1.0, 2.0]), np.array([-1.0, 1.0, 2.0])])
def test_fit_raises_on_non_positive_truth(truth):
    with pytest.raises(ValueError, match="positive"):
        fit_calibration(np.array([0.1, 0.2, 0.3]), truth)


def test_fit_raises_on_too_few_samples():
    with pytest.raises(ValueError, match="At least three"):
        fit_calibration(np.array([0.1, 0.2]), np.array([10.0, 20.0]))


def test_disclaimer_is_prominent():
    model = fit_calibration(np.array([0.1, 0.2, 0.3]), np.array([1.0, 10.0, 100.0]))

    assert "DISCLAIMER" in model.disclaimer
    assert not model.independently_validated


# ---------------------------------------------------------------------------
# hardening: edge cases and error paths
# ---------------------------------------------------------------------------


def test_fit_rejects_constant_index_values():
    """All-same index values should raise — zero-variance cannot fit a line."""
    truth = np.array([1.0, 10.0, 100.0])
    index = np.array([0.05, 0.05, 0.05])
    with pytest.raises(ValueError, match="constant"):
        fit_calibration(index, truth)


def test_fit_with_near_constant_index_still_fits():
    """Nearly-constant index values with tiny variation should still produce a model."""
    truth = np.array([1.0, 10.0, 100.0])
    index = np.array([0.05001, 0.05000, 0.04999])  # tiny but real variation
    model = fit_calibration(index, truth)
    assert model.fit_quality["n_samples"] == 3
    assert "slope" in model.coefficients


def test_fit_rejects_nonfinite_index():
    truth = np.array([1.0, 10.0, 100.0])
    index = np.array([0.1, np.nan, 0.3])
    with pytest.raises(ValueError, match="finite"):
        fit_calibration(index, truth)


def test_fit_rejects_nonfinite_truth():
    truth = np.array([1.0, np.inf, 100.0])
    index = np.array([0.1, 0.2, 0.3])
    with pytest.raises(ValueError, match="finite"):
        fit_calibration(index, truth)


def test_fit_rejects_shape_mismatch():
    with pytest.raises(ValueError, match="same shape"):
        fit_calibration(np.array([0.1, 0.2, 0.3]), np.array([10.0, 100.0]))


def test_apply_calibration_handles_nan_input():
    model = CalibrationModel(coefficients={"slope": 0.02, "intercept": 0.0})
    index = np.array([0.02 * np.log10(50.0), np.nan, 0.02 * np.log10(100.0)])
    estimated = apply_calibration(index, model)
    assert np.isnan(estimated[1])
    assert estimated[0] == pytest.approx(50.0)
    assert estimated[2] == pytest.approx(100.0)


def test_apply_calibration_no_clipping():
    model = CalibrationModel(
        coefficients={"slope": 0.02, "intercept": 0.0},
        calibration_domain={"bilirubin_uM_min": 10.0, "bilirubin_uM_max": 100.0},
    )
    index = 0.02 * np.log10(np.array([1.0, 200.0]))
    estimated = apply_calibration(index, model, clip_to_domain=False)
    # Without clipping, we get the raw inversion
    np.testing.assert_allclose(estimated, [1.0, 200.0], rtol=1e-10)


def test_apply_calibration_raises_on_unsupported_fit_type():
    model = CalibrationModel(
        fit_type="linear", 
        coefficients={"slope": 1.0, "intercept": 0.0},
    )
    with pytest.raises(ValueError, match="Unsupported"):
        apply_calibration(np.array([0.1]), model)


def test_calibration_clamp_counts_no_domain():
    model = CalibrationModel(coefficients={"slope": 0.02, "intercept": 0.0})
    index = 0.02 * np.log10(np.array([1.0, 50.0, 200.0]))
    counts = calibration_clamp_counts(index, model)
    assert counts == {"n_pixels_clamped_low": 0, "n_pixels_clamped_high": 0}


def test_calibration_clamp_counts_with_nans():
    model = CalibrationModel(
        coefficients={"slope": 0.02, "intercept": 0.0},
        calibration_domain={"bilirubin_uM_min": 10.0, "bilirubin_uM_max": 100.0},
    )
    index = np.array([0.02 * np.log10(5.0), np.nan, 0.02 * np.log10(150.0)])
    counts = calibration_clamp_counts(index, model)
    # Only finite pixels counted; NaN excluded
    assert counts["n_pixels_clamped_low"] == 1
    assert counts["n_pixels_clamped_high"] == 1


def test_load_rejects_non_dict_json(tmp_path):
    path = tmp_path / "arr.json"
    path.write_text("[1, 2, 3]")
    with pytest.raises(ValueError, match="object"):
        load_calibration(path)


def test_load_rejects_nonfinite_coefficients(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "fit_type": "log_linear",
                "coefficients": {"slope": float("nan"), "intercept": 0.0},
            }
        )
    )
    with pytest.raises(ValueError, match="finite"):
        load_calibration(path)


def test_model_slope_and_intercept_missing_raises():
    model = CalibrationModel(coefficients={})
    with pytest.raises(AttributeError, match="slope"):
        _ = model.slope
    with pytest.raises(AttributeError, match="intercept"):
        _ = model.intercept


def test_save_creates_parent_directories(tmp_path):
    model = CalibrationModel(
        coefficients={"slope": 0.01, "intercept": 0.0},
        calibration_domain={"bilirubin_uM_min": 1.0, "bilirubin_uM_max": 100.0},
    )
    path = tmp_path / "deep" / "nested" / "cal.json"
    save_calibration(model, path)
    assert path.exists()


def test_model_summary_for_metadata_with_none():
    assert model_summary_for_metadata(None) is None


def test_model_summary_for_metadata_with_dict():
    data = {
        "coefficients": {"slope": 0.01, "intercept": 0.0},
        "disclaimer": "test",
        "independently_validated": True,
        "fit_type": "log_linear",
        "index_formula": "OD450 - OD517",
        "calibration_domain": {"bili_uM_min": 1.0},
        "fit_quality": {"n_samples": 6},
    }
    summary = model_summary_for_metadata(data)
    assert summary is not None
    assert summary["coefficients"] == {"slope": 0.01, "intercept": 0.0}


def test_model_summary_for_metadata_without_coefficients_returns_none():
    assert model_summary_for_metadata({"foo": "bar"}) is None


def test_model_summary_for_metadata_from_calibration_model():
    model = CalibrationModel(
        coefficients={"slope": 0.01, "intercept": 0.0},
        k_hb_correction=0.02,
        calibration_domain={"bilirubin_uM_min": 8.4},
        fit_quality={"in_sample_r2": 0.9, "loo_r2": 0.5},
        independently_validated=False,
    )
    summary = model_summary_for_metadata(model)
    assert summary is not None
    assert summary["k_hb_correction"] == 0.02
    assert summary["coefficients"]["slope"] == 0.01
    assert not summary["independently_validated"]


def test_fit_calibration_with_only_three_samples():
    """Minimum viable calibration: 3 samples."""
    truth = np.array([8.4, 67.5, 270.0])
    index = 0.014 * np.log10(truth) - 0.0002
    model = fit_calibration(index, truth)
    assert model.fit_quality["n_samples"] == 3
    assert model.fit_quality["in_sample_r2"] == pytest.approx(1.0)
    # LOO should exist
    assert "loo_r2" in model.fit_quality


def test_save_load_roundtrip_full_model(tmp_path):
    """Round-trip a model with all fields populated including k_hb_correction."""
    model = CalibrationModel(
        fit_type="log_linear",
        index_formula="OD450 - OD517 - 0.02*OD671",
        coefficients={"slope": 0.014, "intercept": -0.00024},
        k_hb_correction=0.02,
        calibration_domain={
            "bilirubin_uM_min": 8.4,
            "bilirubin_uM_max": 270.0,
            "hb_uM": 100.0,
            "dataset": "test",
            "wavelengths": [450, 517, 671],
            "phantoms": ["A1", "A2", "A3", "A4", "A5", "A6"],
        },
        fit_quality={
            "in_sample_r2": 0.942,
            "loo_r2": -4.4,
            "rmse_uM": 120.0,
            "n_samples": 6,
        },
        disclaimer="Custom disclaimer.",
        independently_validated=False,
    )
    path = tmp_path / "full_model.json"
    save_calibration(model, path)

    loaded = load_calibration(path)

    assert loaded == model
    assert loaded.k_hb_correction == 0.02
    assert loaded.calibration_domain["hb_uM"] == 100.0
    assert loaded.calibration_domain["phantoms"] == ["A1", "A2", "A3", "A4", "A5", "A6"]
    assert loaded.disclaimer == "Custom disclaimer."


def test_get_default_calibration_path():
    from app.core.calibration import get_default_calibration_path
    p = get_default_calibration_path()
    assert p.name == "bilirubin_a1a6_log_linear.json"
    assert p.parent.name in ("calibrations", "data")
