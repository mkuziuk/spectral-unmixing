#!/usr/bin/env python3
"""
Tests for data directory validation and penetration depth file selection.

Covers:
  - validate_data_directory success case
  - missing leds_emission.csv
  - missing chromophores/ directory
  - empty chromophores/ directory
  - penetration depth file selection priority:
      a) prefer penetration_depth_digitized.csv
      b) otherwise choose lexicographically first penetration_depth*.csv
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core import io


class TestValidateDataDirectory(unittest.TestCase):
    """Tests for io.validate_data_directory."""

    def setUp(self):
        """Create a minimal valid data directory for each test."""
        self.tmpdir = tempfile.mkdtemp()
        # Create required files for a valid directory
        Path(self.tmpdir, "leds_emission.csv").touch()
        Path(self.tmpdir, "penetration_depth_digitized.csv").touch()
        chrom_dir = Path(self.tmpdir, "chromophores")
        chrom_dir.mkdir()
        Path(chrom_dir, "HbO2.csv").touch()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_valid_data_directory(self):
        """validate_data_directory should not raise on a valid directory."""
        io.validate_data_directory(self.tmpdir)  # should not raise

    def test_missing_leds_emission_csv(self):
        """Should raise FileNotFoundError when leds_emission.csv is missing."""
        os.remove(Path(self.tmpdir, "leds_emission.csv"))
        with self.assertRaises(FileNotFoundError) as ctx:
            io.validate_data_directory(self.tmpdir)
        self.assertIn("leds_emission.csv", str(ctx.exception))

    def test_missing_chromophores_directory(self):
        """Should raise FileNotFoundError when chromophores/ is missing."""
        shutil.rmtree(Path(self.tmpdir, "chromophores"))
        with self.assertRaises(FileNotFoundError) as ctx:
            io.validate_data_directory(self.tmpdir)
        self.assertIn("chromophores", str(ctx.exception))

    def test_empty_chromophores_directory(self):
        """Should raise ValueError when chromophores/ has no .csv files."""
        chrom_dir = Path(self.tmpdir, "chromophores")
        # Remove the existing CSV
        os.remove(chrom_dir / "HbO2.csv")
        with self.assertRaises(ValueError) as ctx:
            io.validate_data_directory(self.tmpdir)
        self.assertIn("no .csv files", str(ctx.exception))


class TestPenetrationDepthFileSelection(unittest.TestCase):
    """Tests for io._find_penetration_depth_file priority logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_file(self, name: str):
        Path(self.tmpdir, name).touch()

    def test_prefer_digitized_when_present(self):
        """Should select penetration_depth_digitized.csv when it exists."""
        self._create_file("penetration_depth_digitized.csv")
        self._create_file("penetration_depth_original.csv")
        self._create_file("penetration_depth_2024.csv")

        result = io._find_penetration_depth_file(self.tmpdir)
        self.assertEqual(result, os.path.join(self.tmpdir, "penetration_depth_digitized.csv"))

    def test_fallback_to_lexicographically_first(self):
        """Should select lexicographically first penetration_depth*.csv when digitized is absent."""
        self._create_file("penetration_depth_original.csv")
        self._create_file("penetration_depth_2024.csv")
        self._create_file("penetration_depth_alternative.csv")

        result = io._find_penetration_depth_file(self.tmpdir)
        expected = os.path.join(self.tmpdir, "penetration_depth_2024.csv")
        self.assertEqual(result, expected)

    def test_single_penetration_file(self):
        """Should work correctly when only one penetration_depth*.csv exists."""
        self._create_file("penetration_depth.csv")

        result = io._find_penetration_depth_file(self.tmpdir)
        self.assertEqual(result, os.path.join(self.tmpdir, "penetration_depth.csv"))

    def test_digitized_only(self):
        """Should select digitized even when it is the only file."""
        self._create_file("penetration_depth_digitized.csv")

        result = io._find_penetration_depth_file(self.tmpdir)
        self.assertEqual(result, os.path.join(self.tmpdir, "penetration_depth_digitized.csv"))


if __name__ == '__main__':
    unittest.main(verbosity=2)
