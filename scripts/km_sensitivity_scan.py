#!/usr/bin/env python3
"""KM sensitivity scan for the DNG-derived A1-A6 phantom series.

This is a diagnostic script, not a unit test. It scans global scattering and
calibration parameters for the current classic Kubelka-Munk solver and reports
whether any physically plausible regime recovers the expected qualitative
phantom behavior:

- Hb approximately constant across A1-A6
- bilirubin decreasing from A1 to A6

The script intentionally avoids per-sample/per-chromophore tuning so it does not
fit away the phantom series.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import io, processing  # noqa: E402


DNG_DERIVED_ROOT = ROOT / "liquid_phantoms_for_unmixing_dng_cropped"
DATA_DIR = ROOT / "data"
CHROMOPHORE_NAMES = ["hb_agat_extr", "bili_agat"]
GROUND_TRUTH_UM = {
    "A1": (100.0, 270.0),
    "A2": (100.0, 135.0),
    "A3": (100.0, 67.5),
    "A4": (100.0, 33.75),
    "A5": (100.0, 16.875),
    "A6": (100.0, 8.4375),
}
DEFAULT_F_LIPO = processing.SCATTERING_LIPOFUNDIN_FRACTION
DEFAULT_G = processing.SCATTERING_ANISOTROPY_G
# Concentrations are solver-native M values; 1e-7 M = 0.1 µM. This is
# comfortably above numerical noise while still allowing weak low-end signals.
POSITIVE_CONCENTRATION_THRESHOLD_M = 1e-7


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=DNG_DERIVED_ROOT,
        help="DNG-derived phantom root folder (default: %(default)s)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help="Spectral data folder (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "research-reports" / "km_sensitivity_results.csv",
        help="CSV output path (default: %(default)s)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use a small development grid instead of the full scan.",
    )
    parser.add_argument(
        "--skip-calibration",
        action="store_true",
        help="Skip the 1-D global absorption-matrix calibration scan.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of top-ranked parameter rows to print (default: %(default)s).",
    )
    return parser.parse_args()


def sample_sort_key(name: str) -> int:
    return int(name[1:]) if name.startswith("A") and name[1:].isdigit() else 999


def spatial_medians(concentrations: np.ndarray) -> np.ndarray:
    medians = []
    for idx in range(concentrations.shape[-1]):
        values = concentrations[:, :, idx]
        finite = values[np.isfinite(values)]
        medians.append(float(np.median(finite)) if finite.size else 0.0)
    return np.asarray(medians, dtype=float)


def compute_metrics(
    hb_medians: np.ndarray,
    bili_medians: np.ndarray,
    rmse_means: Iterable[float],
) -> dict[str, float | int | bool]:
    eps = 1e-12
    positive_threshold = POSITIVE_CONCENTRATION_THRESHOLD_M
    hb_mean = float(np.mean(hb_medians))
    hb_present = hb_mean > positive_threshold
    hb_cov = float(np.std(hb_medians) / (hb_mean + eps)) if hb_present else 1.0
    bili_positive_mask = bili_medians > positive_threshold
    bili_positive_count = int(np.sum(bili_positive_mask))

    positive_bili = bili_medians[bili_positive_mask]
    if bili_medians.size >= 2 and bili_medians[0] > positive_threshold and bili_medians[-1] > positive_threshold:
        bili_range = float(bili_medians[0] / max(float(bili_medians[-1]), eps))
    elif positive_bili.size >= 2:
        bili_range = float(np.max(positive_bili) / max(float(np.min(positive_bili)), eps))
    else:
        bili_range = 0.0

    slopes = []
    strict_decreases = 0
    for left, right in zip(bili_medians[:-1], bili_medians[1:]):
        if left > positive_threshold and right > positive_threshold:
            if right < left:
                strict_decreases += 1
            slopes.append(float(np.log2(right / left)))
    bili_mono = strict_decreases if bili_positive_count >= 2 else 0
    bili_log2_slope = float(np.mean(slopes)) if slopes else 0.0
    bili_positive_a1 = bool(bili_medians[0] > positive_threshold) if bili_medians.size else False
    mean_rmse = float(np.mean(list(rmse_means)))

    slope_score = 0.0
    if len(slopes) >= 2:
        slope_score = max(0.0, 1.0 - abs(bili_log2_slope + 1.0))
    composite = (
        bili_positive_count / 6.0
        + bili_mono / 5.0
        + max(0.0, 1.0 - hb_cov)
        + min(1.0, bili_range / 10.0)
        + slope_score
    )

    return {
        "hb_cov": hb_cov,
        "hb_present": hb_present,
        "bili_mono": bili_mono,
        "bili_range": bili_range,
        "bili_log2_slope": bili_log2_slope,
        "bili_positive_a1": bili_positive_a1,
        "bili_positive_count": bili_positive_count,
        "mean_rmse": mean_rmse,
        "composite": composite,
    }


def load_context(root: Path, data_dir: Path) -> dict:
    info = io.detect_folders(str(root))
    sample_pairs = sorted(
        zip(info["samples"], info["sample_names"]),
        key=lambda item: sample_sort_key(item[1]),
    )
    info["samples"] = [path for path, _name in sample_pairs]
    info["sample_names"] = [name for _path, name in sample_pairs]

    ref_cube = io.load_image_cube(info["ref_dir"], info["wavelengths"])
    dark_cube = io.load_image_cube(info["dark_ref_dir"], info["wavelengths"])
    chromophore_spectra = io.load_chromophore_spectra(str(data_dir))
    missing = [name for name in CHROMOPHORE_NAMES if name not in chromophore_spectra]
    if missing:
        raise FileNotFoundError(f"Missing required spectra: {missing}")
    led_wl, led_emission = io.load_led_emission(str(data_dir), info["wavelengths"])

    absorption_matrix, chrom_names = processing.build_absorption_matrix(
        led_wl,
        led_emission,
        chromophore_spectra,
        info["wavelengths"],
        chromophore_names=CHROMOPHORE_NAMES,
        clip_negative_extinction=True,
    )

    samples = []
    for sample_dir, sample_name in zip(info["samples"], info["sample_names"]):
        cube = io.load_image_cube(sample_dir, info["wavelengths"])
        reflectance = processing.compute_reflectance(cube, ref_cube, dark_cube)
        samples.append({"name": sample_name, "reflectance": reflectance})

    return {
        "info": info,
        "led_wl": led_wl,
        "led_emission": led_emission,
        "absorption_matrix": absorption_matrix,
        "chrom_names": chrom_names,
        "samples": samples,
    }


def build_scattering_profile(
    led_wl: np.ndarray,
    led_emission: dict,
    wavelengths: list[int],
    effective_mu_s_500: float,
    power_b: float,
) -> np.ndarray:
    """Build band-averaged reduced scattering from effective μs'(500).

    ``effective_mu_s_500`` is the reduced scattering value after Lipofundin
    fraction and anisotropy scaling. ``build_fixed_scattering_profile`` expects
    the raw μs(500), so this helper divides by f_lipo * (1 - g).
    """
    # build_fixed_scattering_profile expects μs(500) before lipofundin and g scaling.
    raw_mu_s_500 = effective_mu_s_500 / (DEFAULT_F_LIPO * (1.0 - DEFAULT_G))
    return processing.build_fixed_scattering_profile(
        led_wl,
        led_emission,
        wavelengths,
        mu_s_500_cm1=raw_mu_s_500,
        power_b=power_b,
        lipofundin_fraction=DEFAULT_F_LIPO,
        anisotropy_g=DEFAULT_G,
    )


def evaluate_parameter_set(
    samples: list[dict],
    absorption_matrix: np.ndarray,
    mus_prime: np.ndarray,
    band_indices: np.ndarray,
) -> dict:
    E = absorption_matrix[band_indices, :]
    mus = mus_prime[band_indices]
    hb_medians = []
    bili_medians = []
    rmse_means = []

    for sample in samples:
        reflectance = sample["reflectance"][:, :, band_indices]
        concentrations, rmse_map, _fitted_od = processing.solve_unmixing_km(
            reflectance,
            E,
            mus,
        )
        medians = spatial_medians(concentrations)
        hb_medians.append(medians[0])
        bili_medians.append(medians[1])
        rmse_means.append(float(np.nanmean(rmse_map)))

    hb_arr = np.asarray(hb_medians, dtype=float)
    bili_arr = np.asarray(bili_medians, dtype=float)
    metrics = compute_metrics(hb_arr, bili_arr, rmse_means)
    for idx, sample in enumerate(samples):
        metrics[f"{sample['name']}_hb_uM"] = hb_arr[idx] * 1e6
        metrics[f"{sample['name']}_bili_uM"] = bili_arr[idx] * 1e6
    return metrics


def scan_scattering_grid(ctx: dict, quick: bool, band_label: str, band_indices: np.ndarray) -> list[dict]:
    if quick:
        effective_values = np.logspace(np.log10(0.5), np.log10(240.0), 5)
        b_values = np.linspace(0.5, 2.0, 4)
    else:
        effective_values = np.logspace(np.log10(0.5), np.log10(240.0), 20)
        b_values = np.linspace(0.1, 3.0, 15)

    rows = []
    for effective_mu_s_500 in effective_values:
        for power_b in b_values:
            mus_prime = build_scattering_profile(
                ctx["led_wl"],
                ctx["led_emission"],
                ctx["info"]["wavelengths"],
                float(effective_mu_s_500),
                float(power_b),
            )
            metrics = evaluate_parameter_set(
                ctx["samples"],
                ctx["absorption_matrix"],
                mus_prime,
                band_indices,
            )
            metrics.update(
                {
                    "scan": "scattering",
                    "band_subset": band_label,
                    "effective_mu_s_500": float(effective_mu_s_500),
                    "power_b": float(power_b),
                    "calibration_k": 1.0,
                }
            )
            rows.append(metrics)
    return rows


def scan_calibration_grid(ctx: dict, quick: bool, band_label: str, band_indices: np.ndarray) -> list[dict]:
    k_values = np.logspace(np.log10(0.01), np.log10(10.0), 8 if quick else 30)
    mus_prime = build_scattering_profile(
        ctx["led_wl"],
        ctx["led_emission"],
        ctx["info"]["wavelengths"],
        processing.SCATTERING_MU_S_500_CM1 * DEFAULT_F_LIPO * (1.0 - DEFAULT_G),
        processing.SCATTERING_POWER_B,
    )

    rows = []
    for calibration_k in k_values:
        metrics = evaluate_parameter_set(
            ctx["samples"],
            ctx["absorption_matrix"] * float(calibration_k),
            mus_prime,
            band_indices,
        )
        metrics.update(
            {
                "scan": "calibration",
                "band_subset": band_label,
                "effective_mu_s_500": processing.SCATTERING_MU_S_500_CM1 * DEFAULT_F_LIPO * (1.0 - DEFAULT_G),
                "power_b": processing.SCATTERING_POWER_B,
                "calibration_k": float(calibration_k),
            }
        )
        rows.append(metrics)
    return rows


def reflectance_ratio_sanity(ctx: dict) -> list[tuple[str, float]]:
    wavelengths = ctx["info"]["wavelengths"]
    idx_450 = wavelengths.index(450)
    idx_517 = wavelengths.index(517)
    ratios = []
    for sample in ctx["samples"]:
        med = np.median(sample["reflectance"].reshape(-1, len(wavelengths)), axis=0)
        ratios.append((sample["name"], float(med[idx_450] / med[idx_517])))
    return ratios


def print_top_rows(rows: list[dict], top: int) -> None:
    ranked = sorted(rows, key=lambda row: row["composite"], reverse=True)
    print("\nTop parameter combinations")
    print("rank, scan, subset, mu_s_eff_500, b, K, hb_cov, bili_mono, bili_pos_count, bili_range, log2_slope, bili_pos_A1, rmse, score")
    for rank, row in enumerate(ranked[:top], start=1):
        print(
            f"{rank}, {row['scan']}, {row['band_subset']}, "
            f"{row['effective_mu_s_500']:.6g}{' (fixed)' if row['scan'] == 'calibration' else ''}, "
            f"{row['power_b']:.6g}, {row['calibration_k']:.6g}, "
            f"{row['hb_cov']:.6g}, {row['bili_mono']}/5, {row['bili_positive_count']}/6, "
            f"{row['bili_range']:.6g}, {row['bili_log2_slope']:.6g}, {row['bili_positive_a1']}, "
            f"{row['mean_rmse']:.6g}, {row['composite']:.6g}"
        )

    for scan_type in sorted({row["scan"] for row in rows}):
        scan_ranked = sorted(
            [row for row in rows if row["scan"] == scan_type],
            key=lambda row: row["composite"],
            reverse=True,
        )
        if scan_ranked:
            row = scan_ranked[0]
            print(
                f"Best {scan_type} row: subset={row['band_subset']}, "
                f"mu_s_eff_500={row['effective_mu_s_500']:.6g}, "
                f"b={row['power_b']:.6g}, K={row['calibration_k']:.6g}, "
                f"score={row['composite']:.6g}"
            )

    if ranked:
        best = ranked[0]
        print("\nBest per-sample medians (µM, solver-native scale):")
        print("sample, hb_median, hb_truth, bili_median, bili_truth")
        for sample_name, (hb_truth, bili_truth) in GROUND_TRUTH_UM.items():
            print(
                f"{sample_name}, {best.get(sample_name + '_hb_uM', float('nan')):.6g}, "
                f"{hb_truth:.6g}, {best.get(sample_name + '_bili_uM', float('nan')):.6g}, "
                f"{bili_truth:.6g}"
            )


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_fields = []
    for sample_name in GROUND_TRUTH_UM:
        sample_fields.extend([f"{sample_name}_hb_uM", f"{sample_name}_bili_uM"])
    fieldnames = [
        "scan",
        "band_subset",
        "effective_mu_s_500",
        "power_b",
        "calibration_k",
        "hb_cov",
        "hb_present",
        "bili_mono",
        "bili_range",
        "bili_log2_slope",
        "bili_positive_a1",
        "bili_positive_count",
        "mean_rmse",
        "composite",
        *sample_fields,
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    ctx = load_context(args.root, args.data_dir)
    wavelengths = ctx["info"]["wavelengths"]
    subset_indices = {
        "2band_blue": np.asarray([wavelengths.index(450), wavelengths.index(517)]),
        "4band_vis": np.asarray([wavelengths.index(wl) for wl in (450, 517, 671, 775)]),
        "8band_full": np.arange(len(wavelengths)),
    }

    print("KM Sensitivity Scan — DNG A1-A6 Phantom Series")
    print("================================================")
    print(f"Root: {args.root}")
    print(f"Wavelengths: {wavelengths}")
    print("Chromophores: " + ", ".join(ctx["chrom_names"]))
    print("Ground truth: Hb = 100 µM constant; bilirubin = 270 µM halving A1→A6")

    ratios = reflectance_ratio_sanity(ctx)
    ratio_values = [value for _name, value in ratios]
    ratio_monotonic = all(left <= right for left, right in zip(ratio_values[:-1], ratio_values[1:]))
    print("\nReflectance ratio sanity check R450/R517:")
    print("  " + "  ".join(f"{name}: {value:.6g}" for name, value in ratios))
    print(f"  monotonic increasing A1→A6: {ratio_monotonic}")

    all_rows: list[dict] = []
    for subset_label, band_indices in subset_indices.items():
        print(f"\nScanning scattering grid for subset {subset_label}...")
        all_rows.extend(scan_scattering_grid(ctx, args.quick, subset_label, band_indices))
        if not args.skip_calibration:
            print(f"Scanning calibration factors for subset {subset_label}...")
            all_rows.extend(scan_calibration_grid(ctx, args.quick, subset_label, band_indices))

    print_top_rows(all_rows, args.top)
    write_csv(args.output, all_rows)
    print(f"\nFull scan saved to: {args.output}")

    valid = [
        row
        for row in all_rows
        if row["hb_present"] and row["bili_positive_count"] >= 4 and row["bili_mono"] >= 4 and row["hb_cov"] < 0.20
    ]
    print("\nRecommendation:")
    if valid:
        best = sorted(valid, key=lambda row: row["composite"], reverse=True)[0]
        print(
            "  Found at least one directionally plausible regime: "
            f"scan={best['scan']}, subset={best['band_subset']}, "
            f"effective_mu_s_500={best['effective_mu_s_500']:.6g}, "
            f"b={best['power_b']:.6g}, K={best['calibration_k']:.6g}."
        )
        a1_bili = best.get("A1_bili_uM", 0.0)
        if a1_bili > 0:
            print(f"  A1 bilirubin scale-to-truth factor ≈ {270.0 / a1_bili:.6g}.")
    else:
        print(
            "  No scanned regime produced at least four positive bilirubin samples with "
            "near-monotonic bilirubin and Hb_CoV < 20%. This suggests a structural "
            "wavelength/spectral-identifiability limitation rather than a simple "
            "scattering scale issue."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
