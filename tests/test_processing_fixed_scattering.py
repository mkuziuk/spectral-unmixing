#!/usr/bin/env python3
"""Tests for the fixed-scattering mu_a solver path."""

from __future__ import annotations

import sys
import unittest
import warnings
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

    def test_build_background_profile_exponential_decreases_by_wavelength(self):
        profile = processing.build_background_profile(
            [500, 600, 700],
            model="exponential",
            exp_start=1.0,
            exp_end=0.1,
        )

        self.assertTrue(np.allclose(profile[[0, -1]], [1.0, 0.1]))
        self.assertGreater(profile[0], profile[1])
        self.assertGreater(profile[1], profile[2])

    def test_build_background_profile_shape_and_offset_apply_baseline(self):
        profile = processing.build_background_profile(
            [500, 600, 700],
            model="exponential",
            exp_start=1.0,
            exp_end=0.1,
            exp_shape=2.0,
            exp_offset=0.05,
        )

        self.assertTrue(np.allclose(profile[[0, -1]], [1.05, 0.15]))
        self.assertGreater(profile[1], 0.15)
        self.assertLess(profile[1], 1.05)

    def test_build_background_profile_allows_zero_exponential_end(self):
        profile = processing.build_background_profile(
            [500, 600, 700],
            model="exponential",
            exp_start=1.0,
            exp_end=0.0,
        )

        self.assertTrue(np.all(np.isfinite(profile)))
        self.assertEqual(float(profile[0]), 1.0)
        self.assertEqual(float(profile[-1]), 0.0)

    def test_validate_background_parameters_rejects_invalid_exponential_values(self):
        params = processing.get_default_background_parameters()
        params.update({"model": "exponential", "exp_end": 0.0})

        validated = processing.validate_background_parameters(params)
        self.assertEqual(validated["exp_end"], 0.0)

        params = processing.get_default_background_parameters()
        params.update({"model": "exponential", "exp_end": -0.1})

        with self.assertRaises(ValueError):
            processing.validate_background_parameters(params)

        params = processing.get_default_background_parameters()
        params.update({"model": "exponential", "exp_shape": 0.0})

        with self.assertRaises(ValueError):
            processing.validate_background_parameters(params)

        params = processing.get_default_background_parameters()
        params.update({"model": "exponential", "exp_offset": 0.5})

        validated = processing.validate_background_parameters(params)
        self.assertEqual(validated["exp_offset"], 0.5)

    def test_build_overlap_matrix_uses_exponential_background_column(self):
        common_wl = np.array([500.0, 600.0, 700.0])
        led_emission = {
            500: np.array([1.0, 0.0, 0.0]),
            600: np.array([0.0, 1.0, 0.0]),
            700: np.array([0.0, 0.0, 1.0]),
        }

        A, chrom_names = processing.build_overlap_matrix(
            common_wl,
            led_emission,
            {},
            common_wl,
            np.ones_like(common_wl),
            led_wavelengths=[500, 600, 700],
            chromophore_names=[],
            include_background=True,
            background_model="exponential",
            background_exp_start=1.0,
            background_exp_end=0.1,
        )

        expected = processing.build_background_profile(
            [500, 600, 700],
            model="exponential",
            exp_start=1.0,
            exp_end=0.1,
        )
        self.assertEqual(chrom_names, [])
        self.assertTrue(np.allclose(A[:, 0], expected))

    def test_validate_iterative_solver_parameters_coerces_valid_values(self):
        params = processing.get_default_iterative_solver_parameters()
        params.update({
            "max_iter": "40",
            "tol_rel": "1e-5",
            "tol_rmse": "1e-7",
            "damping": "0.75",
            "initial_concentration": "2e-4",
        })

        validated = processing.validate_iterative_solver_parameters(params)

        self.assertEqual(
            validated,
            {
                "max_iter": 40,
                "tol_rel": 1e-5,
                "tol_rmse": 1e-7,
                "damping": 0.75,
                "initial_concentration": 2e-4,
            },
        )

    def test_validate_iterative_solver_parameters_rejects_invalid_values(self):
        params = processing.get_default_iterative_solver_parameters()

        invalid_cases = [
            ("max_iter", "0"),
            ("tol_rel", "0"),
            ("tol_rmse", "-1e-6"),
            ("damping", "0"),
            ("initial_concentration", "-1e-4"),
        ]
        for key, value in invalid_cases:
            with self.subTest(key=key):
                candidate = dict(params)
                candidate[key] = value
                with self.assertRaises(ValueError):
                    processing.validate_iterative_solver_parameters(candidate)

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

    def test_build_fixed_scattering_spectrum_matches_band_profile(self):
        led_emission_wl = np.array([500.0, 600.0])
        led_emission = {
            500: np.array([1.0, 0.0]),
            600: np.array([0.0, 1.0]),
        }
        params = processing.get_default_scattering_parameters()

        mu_s_prime_wl = processing.build_fixed_scattering_spectrum(
            led_emission_wl,
            **params,
        )
        mu_s_prime_band = processing.build_fixed_scattering_profile(
            led_emission_wl,
            led_emission,
            led_wavelengths=[500, 600],
            **params,
        )

        self.assertTrue(np.allclose(mu_s_prime_wl, mu_s_prime_band))

    def test_build_overlap_matrix_handles_duplicate_penetration_wavelengths(self):
        led_emission_wl = np.array([500.0, 600.0])
        led_emission = {
            500: np.array([1.0, 0.0]),
            600: np.array([0.0, 1.0]),
        }
        chromophore_spectra = {
            "HbO2": (np.array([500.0, 600.0]), np.array([2.0, 4.0])),
        }
        penetration_wl = np.array([500.0, 550.0, 550.0, 600.0])
        penetration_depth = np.array([1.0, 2.0, 4.0, 3.0])

        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            overlap_matrix, chrom_names = processing.build_overlap_matrix(
                led_emission_wl,
                led_emission,
                chromophore_spectra,
                penetration_wl,
                penetration_depth,
                led_wavelengths=[500, 600],
                chromophore_names=["HbO2"],
                include_background=False,
            )

        self.assertEqual(chrom_names, ["HbO2"])
        self.assertTrue(np.all(np.isfinite(overlap_matrix)))

    def test_estimate_effective_pathlength_handles_duplicate_chromophore_wavelengths(self):
        concentrations = np.array([[[0.2]]])
        chromophore_spectra = {
            "HbO2": (
                np.array([500.0, 550.0, 550.0, 600.0]),
                np.array([1.0, 2.0, 4.0, 3.0]),
            ),
        }

        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            pathlength = processing.estimate_effective_pathlength(
                concentrations,
                ["HbO2"],
                chromophore_spectra,
                np.array([500.0, 550.0, 600.0]),
            )

        self.assertTrue(np.all(np.isfinite(pathlength)))

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

    def test_iterative_solver_recovers_self_consistent_concentrations(self):
        common_wl = np.array([500.0, 600.0, 700.0])
        led_emission = {
            500: np.array([1.0, 0.0, 0.0]),
            600: np.array([0.0, 1.0, 0.0]),
            700: np.array([0.0, 0.0, 1.0]),
        }
        chromophore_spectra = {
            "HbO2": (common_wl, np.array([1.5, 0.7, 0.5])),
            "Hb": (common_wl, np.array([0.4, 1.1, 0.9])),
        }
        chrom_names = ["HbO2", "Hb"]
        params = processing.get_default_scattering_parameters()
        true_concentrations = np.array([0.12, 0.08])

        pathlength = processing.estimate_effective_pathlength(
            true_concentrations.reshape(1, 1, -1),
            chrom_names,
            chromophore_spectra,
            common_wl,
            **params,
        )
        A_true, _ = processing.build_overlap_matrix(
            common_wl,
            led_emission,
            chromophore_spectra,
            common_wl,
            pathlength,
            led_wavelengths=[500, 600, 700],
            chromophore_names=chrom_names,
            include_background=False,
        )
        od = A_true @ true_concentrations
        od_cube = od.reshape(1, 1, -1)

        static_A, _ = processing.build_overlap_matrix(
            common_wl,
            led_emission,
            chromophore_spectra,
            common_wl,
            np.ones_like(common_wl),
            led_wavelengths=[500, 600, 700],
            chromophore_names=chrom_names,
            include_background=False,
        )

        concentrations, rmse_map, fitted_od, solver_info = processing.solve_unmixing_iterative(
            od_cube,
            static_A,
            common_wl,
            led_emission,
            chromophore_spectra,
            led_wavelengths=[500, 600, 700],
            chromophore_names=chrom_names,
            include_background=False,
            scattering_parameters=params,
            max_iter=50,
            tol_rel=1e-8,
            tol_rmse=1e-12,
        )

        self.assertTrue(
            np.allclose(concentrations[0, 0, :], true_concentrations, atol=1e-5)
        )
        self.assertTrue(np.allclose(fitted_od[0, 0, :], od, atol=1e-8))
        self.assertLess(float(rmse_map[0, 0]), 1e-8)
        self.assertEqual(solver_info["scattering_parameters"], params)
        self.assertEqual(solver_info["iterative_parameters"]["max_iter"], 50)
        self.assertEqual(solver_info["iterative_parameters"]["tol_rel"], 1e-8)
        self.assertEqual(solver_info["iterative_parameters"]["tol_rmse"], 1e-12)

    def test_iterative_solver_accepts_background_channel(self):
        common_wl = np.array([500.0, 600.0, 700.0])
        led_emission = {
            500: np.array([1.0, 0.0, 0.0]),
            600: np.array([0.0, 1.0, 0.0]),
            700: np.array([0.0, 0.0, 1.0]),
        }
        chromophore_spectra = {
            "HbO2": (common_wl, np.array([1.5, 0.7, 0.5])),
        }
        static_A, chrom_names = processing.build_overlap_matrix(
            common_wl,
            led_emission,
            chromophore_spectra,
            common_wl,
            np.ones_like(common_wl),
            led_wavelengths=[500, 600, 700],
            chromophore_names=["HbO2"],
            include_background=True,
            background_model="exponential",
            background_exp_start=1.0,
            background_exp_end=0.1,
        )
        od_cube = np.array([[[0.1, 0.08, 0.04]]])

        concentrations, _rmse_map, _fitted_od, solver_info = processing.solve_unmixing_iterative(
            od_cube,
            static_A,
            common_wl,
            led_emission,
            chromophore_spectra,
            led_wavelengths=[500, 600, 700],
            chromophore_names=chrom_names,
            include_background=True,
            background_model="exponential",
            background_exp_start=1.0,
            background_exp_end=0.1,
            max_iter=2,
        )

        self.assertEqual(concentrations.shape[-1], 2)
        self.assertEqual(solver_info["A_used"].shape[1], 2)
        self.assertTrue(solver_info["include_background"])
        self.assertEqual(solver_info["background_parameters"]["model"], "exponential")


if __name__ == "__main__":
    unittest.main(verbosity=2)
