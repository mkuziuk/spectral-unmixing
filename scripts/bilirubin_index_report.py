#!/usr/bin/env python3
"""Model-free two-band bilirubin index report for the DNG A1-A6 phantoms.

This diagnostic uses OD450 - OD517 and the known A1-A6 bilirubin halving
series. It intentionally reports an index/calibration fit, not a physical
multi-chromophore unmixing result.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import io, processing  # noqa: E402
from app.core.calibration import (  # noqa: E402
    apply_calibration,
    fit_calibration,
    load_calibration,
    save_calibration,
)


DEFAULT_ROOT = ROOT / "liquid_phantoms_for_unmixing_dng_cropped"
GROUND_TRUTH_BILI_UM = {
    "A1": 270.0,
    "A2": 135.0,
    "A3": 67.5,
    "A4": 33.75,
    "A5": 16.875,
    "A6": 8.4375,
}
GROUND_TRUTH_HB_UM = 100.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "research-reports" / "bilirubin_index_report.csv",
    )
    parser.add_argument("--k-hb-correction", type=float, default=None)
    parser.add_argument(
        "--save-calibration",
        type=Path,
        default=None,
        help="Write fitted corrected-index calibration JSON to this path.",
    )
    parser.add_argument(
        "--load-calibration",
        type=Path,
        default=None,
        help="Load an existing calibration JSON and apply it to corrected BI medians.",
    )
    args = parser.parse_args()
    if args.save_calibration and args.load_calibration:
        parser.error("--save-calibration and --load-calibration are mutually exclusive")
    return args


def sample_sort_key(name: str) -> int:
    return int(name[1:]) if name.startswith("A") and name[1:].isdigit() else 999


def linear_fit(x: np.ndarray, y: np.ndarray) -> dict:
    design = np.column_stack([x, np.ones_like(x)])
    slope, intercept = np.linalg.lstsq(design, y, rcond=None)[0]
    y_hat = slope * x + intercept
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": float(r2),
        "y_hat": y_hat,
    }


def loo_predictions(index_values: np.ndarray, truth_uM: np.ndarray) -> np.ndarray:
    preds = np.zeros_like(truth_uM, dtype=float)
    log_truth = np.log10(truth_uM)
    for i in range(len(truth_uM)):
        mask = np.ones(len(truth_uM), dtype=bool)
        mask[i] = False
        fit = linear_fit(log_truth[mask], index_values[mask])
        # index = slope * log10(bili) + intercept
        if abs(fit["slope"]) < 1e-12:
            preds[i] = np.nan
        else:
            preds[i] = 10 ** ((index_values[i] - fit["intercept"]) / fit["slope"])
    return preds


def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    if np.sum(mask) < 2:
        return float("nan")
    y_true = y_true[mask]
    y_pred = y_pred[mask]
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0


def main() -> int:
    args = parse_args()

    # -- validate / load calibration early (fail fast) ----------------------
    loaded_model = None
    if args.load_calibration:
        try:
            loaded_model = load_calibration(args.load_calibration)
        except FileNotFoundError:
            print(f"ERROR: Calibration file not found: {args.load_calibration}", file=sys.stderr)
            return 1
        except (ValueError, json.decoder.JSONDecodeError) as exc:
            print(f"ERROR: Invalid calibration file: {exc}", file=sys.stderr)
            return 1
    if args.save_calibration:
        args.save_calibration.parent.mkdir(parents=True, exist_ok=True)

    info = io.detect_folders(str(args.root))
    if 450 not in info["wavelengths"] or 517 not in info["wavelengths"]:
        raise ValueError("The bilirubin index requires 450 nm and 517 nm bands.")
    idx_450 = info["wavelengths"].index(450)
    idx_517 = info["wavelengths"].index(517)
    idx_ref = info["wavelengths"].index(671) if 671 in info["wavelengths"] else None

    sample_pairs = sorted(
        zip(info["samples"], info["sample_names"]),
        key=lambda item: sample_sort_key(item[1]),
    )
    ref_cube = io.load_image_cube(info["ref_dir"], info["wavelengths"])
    dark_cube = io.load_image_cube(info["dark_ref_dir"], info["wavelengths"])

    rows = []
    for sample_dir, sample_name in sample_pairs:
        if sample_name not in GROUND_TRUTH_BILI_UM:
            continue
        sample_cube = io.load_image_cube(sample_dir, info["wavelengths"])
        reflectance = processing.compute_reflectance(sample_cube, ref_cube, dark_cube)
        index = processing.compute_bilirubin_index(
            reflectance,
            wavelength_index_450=idx_450,
            wavelength_index_517=idx_517,
            wavelength_index_ref=idx_ref,
            k_hb_correction=args.k_hb_correction,
        )
        flat_reflectance = reflectance.reshape(-1, reflectance.shape[-1])
        r450_median = float(np.median(flat_reflectance[:, idx_450]))
        r517_median = float(np.median(flat_reflectance[:, idx_517]))
        r_ratio = r450_median / r517_median
        bi_raw = index["bi_raw"]
        bi_corrected = index["bi_corrected"]
        rows.append(
            {
                "sample": sample_name,
                "bili_truth_uM": GROUND_TRUTH_BILI_UM[sample_name],
                "hb_truth_uM": GROUND_TRUTH_HB_UM,
                "r450_median": r450_median,
                "r517_median": r517_median,
                "r450_over_r517": r_ratio,
                "bi_raw_median": float(np.median(bi_raw)),
                "bi_raw_iqr": float(np.percentile(bi_raw, 75) - np.percentile(bi_raw, 25)),
                "bi_corrected_median": float(np.median(bi_corrected)),
                "bi_corrected_iqr": float(
                    np.percentile(bi_corrected, 75) - np.percentile(bi_corrected, 25)
                ),
            }
        )

    truth = np.asarray([row["bili_truth_uM"] for row in rows], dtype=float)
    log_truth = np.log10(truth)
    raw_values = np.asarray([row["bi_raw_median"] for row in rows], dtype=float)
    corrected_values = np.asarray([row["bi_corrected_median"] for row in rows], dtype=float)

    raw_fit = linear_fit(log_truth, raw_values)
    corrected_fit = linear_fit(log_truth, corrected_values)
    raw_loo = loo_predictions(raw_values, truth)
    corrected_loo = loo_predictions(corrected_values, truth)
    raw_loo_r2 = r2_score(truth, raw_loo)
    corrected_loo_r2 = r2_score(truth, corrected_loo)

    if args.save_calibration:
        corrected_model = fit_calibration(
            corrected_values,
            truth,
            index_formula=(
                "OD450 - OD517"
                if args.k_hb_correction is None
                else f"OD450 - OD517 - {args.k_hb_correction:g}*OD671"
            ),
            k_hb_correction=args.k_hb_correction,
            calibration_domain={
                "bilirubin_uM_min": float(np.min(truth)),
                "bilirubin_uM_max": float(np.max(truth)),
                "hb_uM": GROUND_TRUTH_HB_UM,
                "dataset": str(args.root),
                "wavelengths": list(info["wavelengths"]),
                "phantoms": [row["sample"] for row in rows],
            },
        )
        save_calibration(corrected_model, args.save_calibration)

    # -- populate fit / loo / loaded-estimate columns -----------------------
    # Build a canonical fieldname list so CSV columns are uniform.
    _base_fieldnames = ["sample", "bili_truth_uM", "hb_truth_uM",
                        "r450_median", "r517_median", "r450_over_r517",
                        "bi_raw_median", "bi_raw_iqr",
                        "bi_corrected_median", "bi_corrected_iqr",
                        "bi_raw_fit_uM", "bi_corrected_fit_uM",
                        "bi_raw_loo_uM", "bi_corrected_loo_uM"]
    if loaded_model is not None:
        _base_fieldnames.append("bi_loaded_calibrated_est_uM")
    fieldnames = list(_base_fieldnames)

    for idx, row in enumerate(rows):
        row["bi_raw_fit_uM"] = float(10 ** ((raw_values[idx] - raw_fit["intercept"]) / (raw_fit["slope"] + 1e-300)))
        row["bi_corrected_fit_uM"] = float(
            10 ** ((corrected_values[idx] - corrected_fit["intercept"]) / (corrected_fit["slope"] + 1e-300))
        )
        row["bi_raw_loo_uM"] = float(raw_loo[idx])
        row["bi_corrected_loo_uM"] = float(corrected_loo[idx])
        if loaded_model is not None:
            row["bi_loaded_calibrated_est_uM"] = float(
                apply_calibration(np.asarray([corrected_values[idx]]), loaded_model)[0]
            )

    ratio_values = [row["r450_over_r517"] for row in rows]
    ratio_mono = all(left <= right for left, right in zip(ratio_values[:-1], ratio_values[1:]))
    bi_raw_mono = all(left >= right for left, right in zip(raw_values[:-1], raw_values[1:]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print("Two-band bilirubin index report")
    print("================================")
    print(f"Root: {args.root}")
    print(f"Bands: 450 index={idx_450}, 517 index={idx_517}, ref index={idx_ref}")
    print(f"k_hb_correction: {args.k_hb_correction}")
    print(f"R450/R517 monotonic increasing A1→A6: {ratio_mono}")
    print(f"BI raw monotonic decreasing A1→A6: {bi_raw_mono}")
    print(
        "Raw in-sample fit: BI = slope*log10(bili_uM)+intercept; "
        f"slope={raw_fit['slope']:.6g}, intercept={raw_fit['intercept']:.6g}, "
        f"R²={raw_fit['r2']:.6g}, LOO R²={raw_loo_r2:.6g}"
    )
    print(
        "Corrected in-sample fit: BI = slope*log10(bili_uM)+intercept; "
        f"slope={corrected_fit['slope']:.6g}, intercept={corrected_fit['intercept']:.6g}, "
        f"R²={corrected_fit['r2']:.6g}, LOO R²={corrected_loo_r2:.6g}"
    )
    if args.save_calibration:
        print(f"\nCalibration JSON saved to: {args.save_calibration}")
    if loaded_model is not None:
        print(
            "\nLoaded calibration:"
            f"\n  fit_type      = {loaded_model.fit_type}"
            f"\n  formula       = {loaded_model.index_formula}"
            f"\n  slope         = {loaded_model.slope:.6g}"
            f"\n  intercept     = {loaded_model.intercept:.6g}"
            f"\n  domain        = {loaded_model.calibration_domain.get('bilirubin_uM_min', '?')}"
            f" – {loaded_model.calibration_domain.get('bilirubin_uM_max', '?')} µM"
            f"\n  in-sample R²  = {loaded_model.fit_quality.get('in_sample_r2', '?'):.6g}"
            f"\n  LOO R²        = {loaded_model.fit_quality.get('loo_r2', '?')}"
            f"\n  n_samples     = {loaded_model.fit_quality.get('n_samples', '?')}"
            f"\n  validated     = {loaded_model.independently_validated}"
        )
        if not loaded_model.independently_validated:
            print(f"\n  {loaded_model.disclaimer}")

    # Print compact table.  Adapt header when a loaded model is present.
    header_cols = ["sample", "truth_uM", "R450/R517", "BI_raw"]
    if loaded_model is not None:
        header_cols.append("est_uM (loaded)")
    header_cols.extend(["fit_uM", "LOO_uM"])
    print("\n" + ", ".join(header_cols))
    for row in rows:
        line = (
            f"{row['sample']}, {row['bili_truth_uM']:.6g}, "
            f"{row['r450_over_r517']:.6g}, {row['bi_raw_median']:.6g}"
        )
        if loaded_model is not None:
            line += f", {row['bi_loaded_calibrated_est_uM']:.6g}"
        line += f", {row['bi_raw_fit_uM']:.6g}, {row['bi_raw_loo_uM']:.6g}"
        print(line)
    print(f"\nCSV saved to: {args.output}")
    if loaded_model is not None:
        print(
            "\nLoaded-estimate column '" + "est_uM (loaded)" + "': "
            "domain-calibrated estimate from the loaded calibration model. "
            "It should not be reported as an absolute physical bilirubin concentration "
            "outside the model's stated calibration domain."
        )
    print(
        "\nInterpretation: the bilirubin index is a calibrated diagnostic, "
        "not a physical bilirubin concentration. Interpret only within the "
        "calibration domain."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
