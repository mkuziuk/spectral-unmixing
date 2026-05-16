"""Tests for scripts/bilirubin_index_report.py CLI calibration integration."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest


PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
REPORT_SCRIPT = SCRIPTS_DIR / "bilirubin_index_report.py"


def _run_report(extra_args: list[str] | None = None, cwd: str | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(REPORT_SCRIPT)]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=cwd or str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture(scope="session")
def default_root() -> Path:
    root = PROJECT_ROOT / "liquid_phantoms_for_unmixing_dng_cropped"
    if not root.is_dir():
        pytest.skip("DNG phantom root not found")
    return root


# -------------------------------------------------------------------
# Basic behaviour (existing CSV output preserved)
# -------------------------------------------------------------------

def test_runs_without_calibration_flags(default_root):
    """Basic invocation produces CSV and prints expected summary lines."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.csv"
        proc = _run_report(
            ["--root", str(default_root), "--output", str(out)],
        )
        assert proc.returncode == 0, proc.stderr
        stdout = proc.stdout
        assert "Two-band bilirubin index report" in stdout
        assert "BI raw monotonic" in stdout
        assert "Raw in-sample fit" in stdout
        assert "Corrected in-sample fit" in stdout
        assert "CSV saved to:" in stdout
        assert out.exists()

        # CSV must contain the expected base columns.
        with out.open() as fh:
            header = fh.readline().strip().split(",")
        for col in ["sample", "bili_truth_uM", "r450_over_r517",
                    "bi_raw_median", "bi_raw_fit_uM", "bi_raw_loo_uM"]:
            assert col in header, f"column {col!r} missing"


def test_k_hb_correction_flag(default_root):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report_k.csv"
        proc = _run_report(
            ["--root", str(default_root), "--output", str(out),
             "--k-hb-correction", "0.02"],
        )
    assert proc.returncode == 0, proc.stderr
    assert "k_hb_correction: 0.02" in proc.stdout


# -------------------------------------------------------------------
# --save-calibration
# -------------------------------------------------------------------

def test_save_calibration_writes_valid_json(default_root):
    with tempfile.TemporaryDirectory() as tmp:
        out_csv = Path(tmp) / "report.csv"
        cal_path = Path(tmp) / "cal.json"
        proc = _run_report(
            ["--root", str(default_root),
             "--output", str(out_csv),
             "--save-calibration", str(cal_path)],
        )
        assert proc.returncode == 0, proc.stderr
        assert cal_path.exists()
        data = json.loads(cal_path.read_text())
        assert data["schema_version"] == 1
        assert data["fit_type"] == "log_linear"
        assert "slope" in data["coefficients"]
        assert "intercept" in data["coefficients"]
        assert "Calibration JSON saved to:" in proc.stdout


def test_save_calibration_creates_parent_dirs(tmp_path):
    out_csv = tmp_path / "out" / "report.csv"
    cal_path = tmp_path / "deep" / "nested" / "cal.json"
    root = PROJECT_ROOT / "liquid_phantoms_for_unmixing_dng_cropped"
    if not root.is_dir():
        pytest.skip("DNG root not found")
    proc = _run_report(
        ["--root", str(root),
         "--output", str(out_csv),
         "--save-calibration", str(cal_path)],
    )
    assert proc.returncode == 0, proc.stderr
    assert cal_path.exists()


# -------------------------------------------------------------------
# --load-calibration
# -------------------------------------------------------------------

def test_load_calibration_adds_estimate_column(default_root):
    """Loading an existing calibration adds the est_uM (loaded) column."""
    with tempfile.TemporaryDirectory() as tmp:
        out_csv_1 = Path(tmp) / "report1.csv"
        cal_path = Path(tmp) / "cal.json"
        proc1 = _run_report(
            ["--root", str(default_root),
             "--output", str(out_csv_1),
             "--save-calibration", str(cal_path)],
        )
        assert proc1.returncode == 0, proc1.stderr
        assert cal_path.exists()

        # Now load it and check CSV.
        out_csv_2 = Path(tmp) / "report2.csv"
        proc2 = _run_report(
            ["--root", str(default_root),
             "--output", str(out_csv_2),
             "--load-calibration", str(cal_path)],
        )
        assert proc2.returncode == 0, proc2.stderr
        assert out_csv_2.exists()

        with out_csv_2.open() as fh:
            header = fh.readline().strip().split(",")
        assert "bi_loaded_calibrated_est_uM" in header
        assert "Loaded calibration:" in proc2.stdout
        assert "est_uM (loaded)" in proc2.stdout


def test_load_calibration_prints_quality_info(default_root):
    with tempfile.TemporaryDirectory() as tmp:
        cal_path = Path(tmp) / "cal.json"
        proc1 = _run_report(
            ["--root", str(default_root),
             "--output", str(Path(tmp) / "r.csv"),
             "--save-calibration", str(cal_path)],
        )
        assert proc1.returncode == 0, proc1.stderr

        proc2 = _run_report(
            ["--root", str(default_root),
             "--output", str(Path(tmp) / "r2.csv"),
             "--load-calibration", str(cal_path)],
        )
        assert proc2.returncode == 0, proc2.stderr
        stdout2 = proc2.stdout
        assert "in-sample R" in stdout2  # R² may not render as ² in test env
        assert "LOO R" in stdout2
        assert "validated" in stdout2
        assert "DISCLAIMER" in stdout2


def test_load_calibration_missing_file():
    proc = _run_report(["--load-calibration", "/no/such/cal.json"])
    assert proc.returncode == 1, proc.stdout
    assert "ERROR" in proc.stderr


def test_load_calibration_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    proc = _run_report(["--load-calibration", str(bad)])
    assert proc.returncode == 1, proc.stdout
    assert "ERROR" in proc.stderr


def test_load_calibration_wrong_schema(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "schema_version": 99, "fit_type": "log_linear",
        "coefficients": {"slope": 1, "intercept": 0},
    }))
    proc = _run_report(["--load-calibration", str(bad)])
    assert proc.returncode == 1, proc.stdout
    assert "ERROR" in proc.stderr


def test_save_and_load_mutually_exclusive(default_root):
    proc = _run_report(
        ["--root", str(default_root),
         "--save-calibration", "/tmp/a.json",
         "--load-calibration", "/tmp/b.json"],
    )
    assert proc.returncode == 2, proc.stdout  # argparse exit
    assert "mutually exclusive" in proc.stderr.lower()


# -------------------------------------------------------------------
# CSV column consistency
# -------------------------------------------------------------------

def test_csv_columns_are_identical_across_rows(default_root):
    """Every row must have exactly the same set of keys."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.csv"
        proc = _run_report(["--root", str(default_root), "--output", str(out)])
        assert proc.returncode == 0, proc.stderr
        with out.open() as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
    assert len(rows) >= 6
    keys = set(rows[0].keys())
    for i, row in enumerate(rows):
        assert set(row.keys()) == keys, f"row {i} has different columns"


def test_csv_columns_identical_with_load_calibration(default_root):
    """With --load-calibration all rows still have identical columns."""
    with tempfile.TemporaryDirectory() as tmp:
        cal_path = Path(tmp) / "cal.json"
        proc1 = _run_report(
            ["--root", str(default_root),
             "--output", str(Path(tmp) / "r.csv"),
             "--save-calibration", str(cal_path)],
        )
        assert proc1.returncode == 0, proc1.stderr

        out2 = Path(tmp) / "report2.csv"
        proc2 = _run_report(
            ["--root", str(default_root),
             "--output", str(out2),
             "--load-calibration", str(cal_path)],
        )
        assert proc2.returncode == 0, proc2.stderr

        with out2.open() as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
    assert len(rows) >= 6
    keys = set(rows[0].keys())
    for i, row in enumerate(rows):
        assert set(row.keys()) == keys, f"row {i} has different columns"


# -------------------------------------------------------------------
# estimate values are finite / plausible
# -------------------------------------------------------------------

def test_loaded_estimates_are_finite_and_positive(default_root):
    with tempfile.TemporaryDirectory() as tmp:
        cal_path = Path(tmp) / "cal.json"
        proc1 = _run_report(
            ["--root", str(default_root),
             "--output", str(Path(tmp) / "r.csv"),
             "--save-calibration", str(cal_path)],
        )
        assert proc1.returncode == 0, proc1.stderr

        out2 = Path(tmp) / "report2.csv"
        proc2 = _run_report(
            ["--root", str(default_root),
             "--output", str(out2),
             "--load-calibration", str(cal_path)],
        )
        assert proc2.returncode == 0, proc2.stderr

        with out2.open() as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
    for row in rows:
        est = float(row["bi_loaded_calibrated_est_uM"])
        assert np.isfinite(est), f"non-finite estimate for {row['sample']}"
        assert est > 0, f"non-positive estimate for {row['sample']}"
