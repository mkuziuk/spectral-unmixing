from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.core import io, processing


ROOT = Path(__file__).resolve().parents[1]
DNG_DERIVED_ROOT = ROOT / "liquid_phantoms_for_unmixing_dng_cropped"
DATA_DIR = ROOT / "data"
CHROMOPHORE_NAMES = ["hb_agat_extr", "bili_agat"]
GROUND_TRUTH_UM = {
    "A1": {"hb_agat_extr": 100.0, "bili_agat": 270.0},
    "A2": {"hb_agat_extr": 100.0, "bili_agat": 135.0},
    "A3": {"hb_agat_extr": 100.0, "bili_agat": 67.5},
    "A4": {"hb_agat_extr": 100.0, "bili_agat": 33.75},
    "A5": {"hb_agat_extr": 100.0, "bili_agat": 16.875},
    "A6": {"hb_agat_extr": 100.0, "bili_agat": 8.4375},
}


def _run_km_phantom_series():
    if not DNG_DERIVED_ROOT.exists():
        pytest.skip(f"DNG-derived phantom folder not found: {DNG_DERIVED_ROOT}")

    info = io.detect_folders(str(DNG_DERIVED_ROOT))
    ref_cube = io.load_image_cube(info["ref_dir"], info["wavelengths"])
    dark_cube = io.load_image_cube(info["dark_ref_dir"], info["wavelengths"])

    chromophore_spectra = io.load_chromophore_spectra(str(DATA_DIR))
    missing = [name for name in CHROMOPHORE_NAMES if name not in chromophore_spectra]
    if missing:
        pytest.skip(f"Required Agati spectra missing: {missing}")

    led_wl, led_emission = io.load_led_emission(str(DATA_DIR), info["wavelengths"])
    absorption_matrix, chrom_names = processing.build_absorption_matrix(
        led_wl,
        led_emission,
        chromophore_spectra,
        info["wavelengths"],
        chromophore_names=CHROMOPHORE_NAMES,
        clip_negative_extinction=True,
    )
    mus_prime = processing.build_fixed_scattering_profile(
        led_wl,
        led_emission,
        info["wavelengths"],
        **processing.get_default_scattering_parameters(),
    )

    rows = []
    for sample_dir, sample_name in zip(info["samples"], info["sample_names"]):
        sample_cube = io.load_image_cube(sample_dir, info["wavelengths"])
        reflectance = processing.compute_reflectance(sample_cube, ref_cube, dark_cube)
        concentrations, rmse_map, fitted_od = processing.solve_unmixing_km(
            reflectance,
            absorption_matrix,
            mus_prime,
        )

        finite_conc = np.isfinite(concentrations)
        median_m = np.nanmedian(np.where(finite_conc, concentrations, np.nan), axis=(0, 1))
        mean_m = np.nanmean(np.where(finite_conc, concentrations, np.nan), axis=(0, 1))
        rows.append(
            {
                "sample": sample_name,
                "median_uM": median_m * 1e6,
                "mean_uM": mean_m * 1e6,
                "rmse_mean": float(np.nanmean(rmse_map)),
                "finite_fraction": float(np.mean(np.isfinite(concentrations))),
                "fitted_od_shape": fitted_od.shape,
            }
        )
    return info, chrom_names, absorption_matrix, mus_prime, rows


def test_km_solver_runs_on_dng_derived_phantom_series():
    """Exploratory DNG-derived phantom validation smoke test.

    This intentionally asserts only finite execution and payload sanity. Absolute
    concentration/trend assertions are deferred until the KM scale and scattering
    calibration are settled; the printed table compares against the known series.
    """
    info, chrom_names, absorption_matrix, mus_prime, rows = _run_km_phantom_series()

    assert chrom_names == CHROMOPHORE_NAMES
    assert info["wavelengths"] == [450, 517, 671, 775, 803, 851, 888, 939]
    assert absorption_matrix.shape == (len(info["wavelengths"]), len(CHROMOPHORE_NAMES))
    assert np.all(absorption_matrix >= 0.0)
    assert mus_prime.shape == (len(info["wavelengths"]),)
    assert set(row["sample"] for row in rows) == set(GROUND_TRUTH_UM)

    print("\nKM DNG-derived phantom validation (concentrations in µM):")
    print("sample, hb_median, hb_truth, bili_median, bili_truth, rmse_mean, finite_fraction")
    for row in rows:
        sample = row["sample"]
        hb_median, bili_median = row["median_uM"]
        print(
            f"{sample}, "
            f"{hb_median:.6g}, {GROUND_TRUTH_UM[sample]['hb_agat_extr']:.6g}, "
            f"{bili_median:.6g}, {GROUND_TRUTH_UM[sample]['bili_agat']:.6g}, "
            f"{row['rmse_mean']:.6g}, {row['finite_fraction']:.6g}"
        )
        assert np.all(np.isfinite(row["median_uM"]))
        assert np.all(np.isfinite(row["mean_uM"]))
        assert row["finite_fraction"] == 1.0
        assert row["fitted_od_shape"][-1] == len(info["wavelengths"])
        assert row["rmse_mean"] >= 0.0
