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


class TestLoadTwoColumnCsv(unittest.TestCase):
    """Tests for io._load_two_column_csv validation hardening."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_csv(self, name: str, lines: list):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write("\n".join(lines))
        return path

    def test_valid_csv(self):
        """Should parse a well-formed two-column CSV."""
        path = self._write_csv("valid.csv", ["wavelength,value", "450,0.5", "460,0.6"])
        wls, vals = io._load_two_column_csv(path)
        self.assertEqual(wls, [450.0, 460.0])
        self.assertEqual(vals, [0.5, 0.6])

    def test_non_numeric_first_column(self):
        """Should raise ValueError with details for non-numeric first column."""
        path = self._write_csv("bad.csv", ["wavelength,value", "abc,0.5"])
        with self.assertRaises(ValueError) as ctx:
            io._load_two_column_csv(path)
        self.assertIn("Non-numeric data", str(ctx.exception))
        self.assertIn(path, str(ctx.exception))
        self.assertIn("abc", str(ctx.exception))

    def test_non_numeric_second_column(self):
        """Should raise ValueError with details for non-numeric second column."""
        path = self._write_csv("bad2.csv", ["wavelength,value", "450,xyz"])
        with self.assertRaises(ValueError) as ctx:
            io._load_two_column_csv(path)
        self.assertIn("Non-numeric data", str(ctx.exception))
        self.assertIn("xyz", str(ctx.exception))

    def test_skips_short_rows(self):
        """Should silently skip rows with fewer than 2 columns."""
        path = self._write_csv("short.csv", ["wavelength,value", "450", "460,0.6"])
        wls, vals = io._load_two_column_csv(path)
        self.assertEqual(wls, [460.0])
        self.assertEqual(vals, [0.6])

    def test_empty_data_returns_empty_lists(self):
        """Should return empty lists when CSV has only a header."""
        path = self._write_csv("empty.csv", ["wavelength,value"])
        wls, vals = io._load_two_column_csv(path)
        self.assertEqual(wls, [])
        self.assertEqual(vals, [])


class TestLoadLedEmission(unittest.TestCase):
    """Tests for io.load_led_emission validation hardening."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_led_csv(self, lines: list):
        path = os.path.join(self.tmpdir, "leds_emission.csv")
        with open(path, "w") as f:
            f.write("\n".join(lines))
        return path

    def test_valid_led_csv(self):
        """Should parse a well-formed LED emission CSV."""
        self._write_led_csv([
            "wavelength,450,517",
            "400,0.1,0.2",
            "401,0.3,0.4",
        ])
        wls, emission = io.load_led_emission(self.tmpdir, [450, 517])
        self.assertEqual(len(wls), 2)
        self.assertIn(450, emission)
        self.assertIn(517, emission)

    def test_ragged_row_missing_column(self):
        """Should raise ValueError for a row with too few columns."""
        self._write_led_csv([
            "wavelength,450,517",
            "400,0.1",
            "401,0.3,0.4",
        ])
        with self.assertRaises(ValueError) as ctx:
            io.load_led_emission(self.tmpdir, [450, 517])
        self.assertIn("Ragged row", str(ctx.exception))

    def test_non_numeric_led_data(self):
        """Should raise ValueError for non-numeric LED data."""
        self._write_led_csv([
            "wavelength,450,517",
            "400,abc,0.2",
        ])
        with self.assertRaises(ValueError) as ctx:
            io.load_led_emission(self.tmpdir, [450, 517])
        self.assertIn("Non-numeric data", str(ctx.exception))

    def test_missing_led_column_in_header(self):
        """Should raise ValueError when requested LED is not in header."""
        self._write_led_csv([
            "wavelength,450,517",
            "400,0.1,0.2",
        ])
        with self.assertRaises(ValueError) as ctx:
            io.load_led_emission(self.tmpdir, [450, 999])
        self.assertIn("999", str(ctx.exception))


class TestWavelengthParsing(unittest.TestCase):
    """Tests for io._parse_wavelengths_from_folder and io._find_image_for_wavelength."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _touch(self, name: str):
        Path(self.tmpdir, name).touch()

    def test_parse_with_underscore(self):
        """Should parse filenames like 450nm_image.jpg."""
        self._touch("450nm_image.jpg")
        self._touch("517nm_another.jpg")
        result = io._parse_wavelengths_from_folder(self.tmpdir)
        self.assertEqual(result, [450, 517])

    def test_parse_with_dot_extension(self):
        """Should parse filenames like 450nm.DNG."""
        self._touch("450nm.DNG")
        self._touch("517nm.dng")
        result = io._parse_wavelengths_from_folder(self.tmpdir)
        self.assertEqual(result, [450, 517])

    def test_parse_with_dash(self):
        """Should parse filenames like 450nm-something.jpg (relaxed regex)."""
        self._touch("450nm-test.jpg")
        result = io._parse_wavelengths_from_folder(self.tmpdir)
        self.assertEqual(result, [450])

    def test_parse_ignores_non_matching(self):
        """Should ignore files that don't start with digits + nm."""
        self._touch("450nm_good.jpg")
        self._touch("readme.txt")
        self._touch("x450nm_bad.jpg")  # doesn't start with digits
        result = io._parse_wavelengths_from_folder(self.tmpdir)
        self.assertEqual(result, [450])

    def test_find_image_deterministic(self):
        """Should pick the same file when duplicates exist (sorted order)."""
        self._touch("450nm_a.jpg")
        self._touch("450nm_b.jpg")
        result = io._find_image_for_wavelength(self.tmpdir, 450)
        # Sorted order: "450nm_a.jpg" < "450nm_b.jpg"
        self.assertEqual(result, os.path.join(self.tmpdir, "450nm_a.jpg"))

    def test_find_image_not_found(self):
        """Should raise FileNotFoundError when no matching file exists."""
        with self.assertRaises(FileNotFoundError):
            io._find_image_for_wavelength(self.tmpdir, 999)


if __name__ == '__main__':
    unittest.main(verbosity=2)
