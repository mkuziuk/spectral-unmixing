#!/usr/bin/env python3
"""Tests for the fixed-scattering mu_a solver path."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core import processing


class TestFixedScatteringSolver(unittest.TestCase):
    """Unit tests for the OD→mu_a inversion solver."""

    def test_validate_scattering_parameters_rejects_invalid_g(self):
        params = processing.get_default_scattering_parameters()
        params["anisotropy_g"] = 1.0

        with self.assertRaises(ValueError):
            processing.validate_scattering_parameters(params)

    def test_build_absorption_matrix_band_averages_chromophore_spectra(self):
        led_emission_wl = np.array([500.0, 600.0])
        led_emission = {
            500: np.array([1.0, 0.0]),
            600: np.array([0.0, 2.0]),
        }
        chromophore_spectra = {
            "HbO2": (np.array([500.0, 600.0]), np.array([2.0, 4.0])),
            "Hb": (np.array([500.0, 600.0]), np.array([1.0, 3.0])),
        }

        E, chrom_names = processing.build_absorption_matrix(
            led_emission_wl,
            led_emission,
            chromophore_spectra,
            led_wavelengths=[500, 600],
            chromophore_names=["HbO2", "Hb"],
        )

        expected = np.array([
            [2.0, 1.0],
            [4.0, 3.0],
        ])
        self.assertEqual(chrom_names, ["HbO2", "Hb"])
        self.assertTrue(np.allclose(E, expected))

    def test_mu_a_solver_recovers_known_concentrations(self):
        absorption_matrix = np.array([
            [1.5, 0.4],
            [0.8, 1.2],
            [1.1, 0.9],
        ])
        mus_prime = np.array([4.0, 5.0, 6.0])
        true_concentrations = np.array([0.12, 0.08])

        mu_a = absorption_matrix @ true_concentrations
        od = np.sqrt(mu_a / (3.0 * (mu_a + mus_prime)))
        od_cube = od.reshape(1, 1, -1)

        concentrations, rmse_map, fitted_od = processing.solve_unmixing(
            od_cube,
            absorption_matrix,
            method="mu_a",
            mus_prime=mus_prime,
        )

        self.assertTrue(
            np.allclose(concentrations[0, 0, :], true_concentrations, atol=1e-10)
        )
        self.assertTrue(np.allclose(fitted_od[0, 0, :], od, atol=1e-10))
        self.assertLess(float(rmse_map[0, 0]), 1e-12)

    def test_mu_a_solver_enforces_nonnegative_concentrations(self):
        absorption_matrix = np.array([
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
        ])
        mus_prime = np.array([4.0, 4.0, 4.0])

        target_mu_a = np.array([0.3, 0.0, 0.0])
        od = np.sqrt(target_mu_a / (3.0 * (target_mu_a + mus_prime)))
        od_cube = od.reshape(1, 1, -1)

        concentrations, _rmse_map, _fitted_od = processing.solve_unmixing(
            od_cube,
            absorption_matrix,
            method="mu_a",
            mus_prime=mus_prime,
        )

        self.assertGreaterEqual(float(concentrations[0, 0, 0]), 0.0)
        self.assertGreaterEqual(float(concentrations[0, 0, 1]), 0.0)

    def test_mu_a_solver_requires_scattering_profile(self):
        od_cube = np.zeros((1, 1, 2))
        absorption_matrix = np.eye(2)

        with self.assertRaises(ValueError):
            processing.solve_unmixing(od_cube, absorption_matrix, method="mu_a")


if __name__ == "__main__":
    unittest.main(verbosity=2)
