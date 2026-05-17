#!/usr/bin/env python3
"""Tests for the fixed-scattering mu_a solver path."""

from __future__ import annotations

import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

import numpy as np


PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core import io as loader
from app.core import processing


class TestFixedScatteringSolver(unittest.TestCase):
    """Unit tests for the OD→mu_a inversion solver."""

    def test_validate_scattering_parameters_rejects_invalid_g(self):
        params = processing.get_default_scattering_parameters()
        params["anisotropy_g"] = 1.0

        with self.assertRaises(ValueError):
            processing.validate_scattering_parameters(params)

    def test_validate_scattering_parameters_spectrum_requires_path(self):
        params = processing.get_default_scattering_parameters()
        params["model"] = processing.SCATTERING_MODEL_SPECTRUM
        params["spectrum_path"] = ""

        with self.assertRaises(ValueError):
            processing.validate_scattering_parameters(params)

    def test_load_mu_s_prime_spectrum(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as handle:
            handle.write("wavelength_nm,mu_s_prime_cm-1\n")
            handle.write("450.0,10.5\n")
            handle.write("800.0,3.2\n")
            path = handle.name

        try:
            wl, values = loader.load_mu_s_prime_spectrum(path)
            self.assertTrue(np.allclose(wl, [450.0, 800.0]))
            self.assertTrue(np.allclose(values, [10.5, 3.2]))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_build_fixed_scattering_spectrum_from_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as handle:
            handle.write("wavelength_nm,mu_s_prime_cm-1\n")
            handle.write("500.0,40.0\n")
            handle.write("600.0,20.0\n")
            path = handle.name

        try:
            params = processing.validate_scattering_parameters({
                "model": processing.SCATTERING_MODEL_SPECTRUM,
                "spectrum_path": path,
                "lipofundin_fraction": 0.25,
                "anisotropy_g": 0.8,
            })
            common_wl = np.array([500.0, 550.0, 600.0])
            mu_s_prime = processing.build_fixed_scattering_spectrum(
                common_wl,
                scattering_parameters=params,
            )
            self.assertTrue(np.allclose(mu_s_prime, [10.0, 15.0, 5.0]))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_interpolate_mu_s_prime_spectrum_from_dense_wide_csv(self):
        """Dense nm-step spectra over a wide range are resampled onto the LED grid."""
        wl_dense = np.arange(400.0, 1001.0, 5.0)
        values_dense = 100.0 * (wl_dense / 500.0) ** (-1.0)
        target_wl = np.array([450.0, 517.0, 671.0, 939.0])

        mu_s_prime = processing.interpolate_mu_s_prime_spectrum(
            wl_dense,
            values_dense,
            target_wl,
        )

        expected = 100.0 * (target_wl / 500.0) ** (-1.0)
        self.assertTrue(np.allclose(mu_s_prime, expected, rtol=1e-5, atol=1e-6))

    def test_interpolate_mu_s_prime_spectrum_holds_edges_beyond_csv_range(self):
        """Wider LED axis than the CSV uses edge μs' values outside the tabulated range."""
        wl_dense = np.arange(351.0, 801.0, 5.0)
        values_dense = np.linspace(12.0, 6.0, wl_dense.size)
        target_wl = np.array([195.0, 450.0, 800.0, 1020.0])

        mu_s_prime = processing.interpolate_mu_s_prime_spectrum(
            wl_dense,
            values_dense,
            target_wl,
        )

        self.assertEqual(mu_s_prime[0], values_dense[0])
        self.assertEqual(mu_s_prime[-1], values_dense[-1])
        self.assertAlmostEqual(mu_s_prime[1], 12.594594594594595, places=5)
        self.assertEqual(mu_s_prime[2], values_dense[-1])

    def test_spectrum_matches_band_profile(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as handle:
            handle.write("wavelength_nm,mu_s_prime_cm-1\n")
            handle.write("500.0,8.0\n")
            handle.write("600.0,4.0\n")
            path = handle.name

        try:
            params = processing.validate_scattering_parameters({
                "model": processing.SCATTERING_MODEL_SPECTRUM,
                "spectrum_path": path,
                "lipofundin_fraction": 1.0,
                "anisotropy_g": 0.8,
            })
            led_emission_wl = np.array([500.0, 600.0])
            led_emission = {
                500: np.array([1.0, 0.0]),
                600: np.array([0.0, 1.0]),
            }
            mu_s_prime_wl = processing.build_fixed_scattering_spectrum(
                led_emission_wl,
                scattering_parameters=params,
            )
            mu_s_prime_band = processing.build_fixed_scattering_profile(
                led_emission_wl,
                led_emission,
                led_wavelengths=[500, 600],
                scattering_parameters=params,
            )
            self.assertTrue(np.allclose(mu_s_prime_wl, mu_s_prime_band))
        finally:
            Path(path).unlink(missing_ok=True)

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

    def test_build_background_profile_slope_interpolates_by_wavelength(self):
        profile = processing.build_background_profile(
            [500, 600, 700],
            model="slope",
            slope_start=1.0,
            slope_end=0.2,
        )

        self.assertTrue(np.allclose(profile, [1.0, 0.6, 0.2]))

    def test_build_background_profile_scattering_decreases_by_wavelength(self):
        profile = processing.build_background_profile(
            [450, 517, 671, 939],
            model="scattering",
            scattering_lambda0_nm=500.0,
            scattering_power_b=1.0,
        )

        self.assertTrue(np.all(np.isfinite(profile)))
        self.assertGreater(float(profile[0]), float(profile[-1]))

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

        concentrations_scaled, _rmse_map, _fitted_od = processing.solve_unmixing(
            od_cube,
            absorption_matrix * processing.LN10,
            method="mu_a",
            mus_prime=mus_prime,
        )
        self.assertTrue(
            np.allclose(concentrations_scaled[0, 0, :], true_concentrations / processing.LN10, atol=1e-10)
        )

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

    def test_diffusion_solver_recovers_known_concentrations(self):
        absorption_matrix = np.array([
            [1.5, 0.4],
            [0.8, 1.2],
            [1.1, 0.9],
        ])
        mus_prime = np.array([4.0, 5.0, 6.0])
        true_concentrations = np.array([0.12, 0.08])

        mu_a = absorption_matrix @ true_concentrations
        reflectance = processing._welch_reflectance(
            mu_a.reshape(1, 1, -1),
            mu_s_prime=mus_prime,
            anisotropy_g=processing.SCATTERING_ANISOTROPY_G,
            n_tissue=1.4,
            n_out=1.0,
        )
        od_cube = -np.log10(np.clip(reflectance, 1e-12, None))

        concentrations, rmse_map, fitted_od = processing.solve_unmixing(
            od_cube,
            absorption_matrix,
            method="diffusion",
            mus_prime=mus_prime,
        )

        self.assertTrue(
            np.allclose(concentrations[0, 0, :], true_concentrations, rtol=1e-2, atol=2e-3)
        )
        self.assertTrue(np.all(np.isfinite(fitted_od)))
        self.assertLess(float(rmse_map[0, 0]), 1e-3)

    def test_diffusion_solver_requires_scattering_profile(self):
        od_cube = np.zeros((1, 1, 2))
        absorption_matrix = np.eye(2)

        with self.assertRaises(ValueError):
            processing.solve_unmixing(od_cube, absorption_matrix, method="diffusion")

    def test_slab_solver_recovers_grid_point_coefficients(self):
        extinction_coefs = np.array([
            [1.2, 0.3],
            [0.7, 1.1],
            [0.4, 0.9],
        ])
        mus_prime = np.array([4.0, 5.0, 6.0])
        slab_params = processing.get_default_slab_parameters()
        slab_params.update({
            "mode": "diffuse",
            "c_steps": 10,
            "c_max": 9e-4,
            "anisotropy_g": 0.8,
            "n_tissue": 1.4,
            "thickness_mm": 10.0,
        })

        grid = np.linspace(0.0, float(slab_params["c_max"]), int(slab_params["c_steps"]))
        true_C = np.array([grid[2], grid[7]])
        mua_env = np.zeros(extinction_coefs.shape[0])

        sim_ref = processing._slab_get_intensities(
            mua_env=mua_env,
            mus=(mus_prime / (1.0 - float(slab_params["anisotropy_g"]))),
            g=float(slab_params["anisotropy_g"]),
            n=float(slab_params["n_tissue"]),
            d=float(slab_params["thickness_mm"]),
            mode=str(slab_params["mode"]),
            coefficients=true_C,
            extinction_coefs=extinction_coefs,
        )

        best_C, sim_ref2 = processing.solve_unmixing_slab(
            reflectance=sim_ref,
            extinction_coefs=extinction_coefs,
            mus_prime=mus_prime,
            slab_parameters=slab_params,
            mua_env=mua_env,
        )

        self.assertTrue(np.allclose(best_C, true_C))
        self.assertTrue(np.allclose(sim_ref2, sim_ref))

    def test_build_overlap_matrix_chromophore_scale(self):
        common_wl = np.array([500.0, 600.0])
        led_emission = {500: np.array([1.0, 0.0]), 600: np.array([0.0, 1.0])}
        chromophore_spectra = {"HbO2": (common_wl, np.array([2.0, 4.0]))}

        A_base, _ = processing.build_overlap_matrix(
            common_wl,
            led_emission,
            chromophore_spectra,
            common_wl,
            np.ones_like(common_wl),
            led_wavelengths=[500, 600],
            chromophore_names=["HbO2"],
            include_background=False,
        )
        A_scaled, _ = processing.build_overlap_matrix(
            common_wl,
            led_emission,
            chromophore_spectra,
            common_wl,
            np.ones_like(common_wl),
            led_wavelengths=[500, 600],
            chromophore_names=["HbO2"],
            include_background=False,
            chromophore_scale=processing.LN10,
        )
        self.assertTrue(np.allclose(A_scaled, A_base * processing.LN10))

    def test_iterative_ln10_scales_recovered_concentrations(self):
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
            scattering_parameters=params,
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

        concentrations, _rmse, _fitted, _info = processing.solve_unmixing_iterative(
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

        concentrations_ln10, _rmse2, _fitted2, info_ln10 = processing.solve_unmixing_iterative(
            od_cube,
            static_A * processing.LN10,
            common_wl,
            led_emission,
            chromophore_spectra,
            led_wavelengths=[500, 600, 700],
            chromophore_names=chrom_names,
            include_background=False,
            scattering_parameters=params,
            chromophore_scale=processing.LN10,
            max_iter=50,
            tol_rel=1e-8,
            tol_rmse=1e-12,
        )
        self.assertTrue(
            np.allclose(
                concentrations_ln10[0, 0, :],
                true_concentrations / processing.LN10,
                atol=1e-5,
            )
        )
        self.assertEqual(info_ln10["chromophore_scale"], processing.LN10)

    def test_iterative_with_spectrum_scattering(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as handle:
            handle.write("wavelength_nm,mu_s_prime_cm-1\n")
            handle.write("400.0,20.0\n")
            handle.write("500.0,16.0\n")
            handle.write("600.0,12.0\n")
            handle.write("700.0,8.0\n")
            handle.write("900.0,6.0\n")
            path = handle.name

        try:
            common_wl = np.array([500.0, 600.0, 700.0])
            led_emission = {
                500: np.array([1.0, 0.0, 0.0]),
                600: np.array([0.0, 1.0, 0.0]),
                700: np.array([0.0, 0.0, 1.0]),
            }
            chromophore_spectra = {
                "HbO2": (common_wl, np.array([1.5, 0.7, 0.5])),
            }
            scattering_params = processing.validate_scattering_parameters({
                "model": processing.SCATTERING_MODEL_SPECTRUM,
                "spectrum_path": path,
                "lipofundin_fraction": 0.5,
                "anisotropy_g": 0.8,
            })
            static_A, chrom_names = processing.build_overlap_matrix(
                common_wl,
                led_emission,
                chromophore_spectra,
                common_wl,
                np.ones_like(common_wl),
                led_wavelengths=[500, 600, 700],
                chromophore_names=["HbO2"],
                include_background=False,
            )
            od_cube = np.array([[[0.15, 0.12, 0.08]]])

            concentrations, rmse_map, fitted_od, solver_info = (
                processing.solve_unmixing_iterative(
                    od_cube,
                    static_A,
                    common_wl,
                    led_emission,
                    chromophore_spectra,
                    led_wavelengths=[500, 600, 700],
                    chromophore_names=chrom_names,
                    include_background=False,
                    scattering_parameters=scattering_params,
                    max_iter=15,
                )
            )

            self.assertEqual(solver_info["scattering_parameters"]["model"], "spectrum")
            self.assertTrue(np.all(np.isfinite(concentrations)))
            self.assertTrue(np.all(np.isfinite(rmse_map)))
            self.assertTrue(np.all(np.isfinite(fitted_od)))
            pathlength = solver_info["pathlength_spectrum"]
            self.assertTrue(np.all(np.isfinite(pathlength)))
            self.assertTrue(np.all(pathlength > 0))
        finally:
            Path(path).unlink(missing_ok=True)

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

    def test_iterative_solver_returns_best_rmse_iterate(self):
        od_cube = np.zeros((1, 1, 1), dtype=float)
        static_A = np.array([[1.0]], dtype=float)
        common_wl = np.array([500.0], dtype=float)
        led_emission = {500: np.array([1.0], dtype=float)}
        chromophore_spectra = {
            "bilirubin": (common_wl, np.array([1.0], dtype=float)),
        }
        concentrations_seq = [
            np.array([[[0.3]]], dtype=float),
            np.array([[[0.6]]], dtype=float),
            np.array([[[0.1]]], dtype=float),
        ]
        rmse_seq = [
            np.array([[0.2]], dtype=float),
            np.array([[0.05]], dtype=float),
            np.array([[0.4]], dtype=float),
        ]
        fitted_seq = [
            np.array([[[0.3]]], dtype=float),
            np.array([[[0.6]]], dtype=float),
            np.array([[[0.1]]], dtype=float),
        ]
        overlap_seq = [
            (np.array([[1.0]], dtype=float), ["bilirubin"]),
            (np.array([[2.0]], dtype=float), ["bilirubin"]),
            (np.array([[3.0]], dtype=float), ["bilirubin"]),
        ]
        pathlength_seq = [
            np.array([1.0], dtype=float),
            np.array([2.0], dtype=float),
            np.array([3.0], dtype=float),
            np.array([4.0], dtype=float),
        ]

        with (
            mock.patch.object(
                processing,
                "estimate_effective_pathlength",
                side_effect=pathlength_seq,
            ),
            mock.patch.object(
                processing,
                "build_overlap_matrix",
                side_effect=overlap_seq,
            ),
            mock.patch.object(
                processing,
                "_solve_unmixing_nnls",
                side_effect=list(zip(concentrations_seq, rmse_seq, fitted_seq)),
            ),
        ):
            concentrations, rmse_map, fitted_od, solver_info = (
                processing.solve_unmixing_iterative(
                    od_cube,
                    static_A,
                    common_wl,
                    led_emission,
                    chromophore_spectra,
                    led_wavelengths=[500],
                    chromophore_names=["bilirubin"],
                    include_background=False,
                    damping=1.0,
                    max_iter=3,
                )
            )

        self.assertTrue(np.allclose(concentrations, concentrations_seq[1]))
        self.assertTrue(np.allclose(rmse_map, rmse_seq[1]))
        self.assertTrue(np.allclose(fitted_od, fitted_seq[1]))
        self.assertTrue(np.allclose(solver_info["A_used"], overlap_seq[1][0]))
        self.assertTrue(np.allclose(solver_info["pathlength_spectrum"], pathlength_seq[1]))
        self.assertEqual(solver_info["stop_reason"], "max_iter")
        self.assertEqual(solver_info["n_iter"], 3)
        self.assertEqual(solver_info["best_iter"], 2)
        self.assertEqual(solver_info["returned_iter"], 2)
        self.assertAlmostEqual(solver_info["best_mean_rmse"], 0.05)
        self.assertAlmostEqual(solver_info["returned_mean_rmse"], 0.05)


if __name__ == "__main__":
    unittest.main(verbosity=2)
