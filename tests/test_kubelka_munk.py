import unittest

import numpy as np

from app.core import processing


class TestKubelkaMunkSolver(unittest.TestCase):
    def test_reflectance_to_mu_a_km_known_value(self):
        reflectance = np.array([0.5])
        mus_prime = np.array([10.0])

        mu_a, valid = processing._reflectance_to_mu_a_km(reflectance, mus_prime)

        self.assertTrue(bool(valid[0]))
        self.assertTrue(np.allclose(mu_a, np.array([1.25])))

    def test_reflectance_to_mu_a_km_rejects_nonphysical_reflectance(self):
        reflectance = np.array([-1.0, 0.0, 0.5, 1.0, 2.0])
        mus_prime = np.full(5, 10.0)

        mu_a, valid = processing._reflectance_to_mu_a_km(reflectance, mus_prime)

        self.assertEqual(valid.tolist(), [False, False, True, False, False])
        self.assertTrue(np.all(np.isfinite(mu_a)))
        self.assertTrue(np.all(mu_a >= 0.0))
        self.assertEqual(float(mu_a[0]), 0.0)
        self.assertEqual(float(mu_a[1]), 0.0)
        self.assertEqual(float(mu_a[3]), 0.0)
        self.assertEqual(float(mu_a[4]), 0.0)

    def test_mu_a_to_reflectance_km_round_trips(self):
        mu_a = np.array([[0.1, 0.5, 1.0]])
        mus_prime = np.array([[10.0, 11.0, 12.0]])

        reflectance = processing._mu_a_to_reflectance_km(mu_a, mus_prime)
        recovered, valid = processing._reflectance_to_mu_a_km(reflectance, mus_prime)

        self.assertTrue(np.all(valid))
        self.assertTrue(np.allclose(recovered, mu_a, atol=1e-12))

    def test_km_solver_recovers_known_concentrations(self):
        absorption_matrix = np.array([
            [1.5, 0.4],
            [0.8, 1.2],
            [1.1, 0.9],
        ])
        mus_prime = np.array([10.0, 11.0, 12.0])
        true_concentrations = np.array([0.12, 0.08])

        mu_a = absorption_matrix @ true_concentrations
        reflectance = processing._mu_a_to_reflectance_km(
            mu_a[np.newaxis, :],
            mus_prime[np.newaxis, :],
        ).reshape(1, 1, -1)

        concentrations, rmse_map, fitted_od = processing.solve_unmixing_km(
            reflectance,
            absorption_matrix,
            mus_prime,
        )

        self.assertTrue(
            np.allclose(concentrations[0, 0, :], true_concentrations, atol=1e-10)
        )
        self.assertLess(float(rmse_map[0, 0]), 1e-10)
        self.assertEqual(fitted_od.shape, reflectance.shape)

    def test_km_solver_enforces_nonnegative_concentrations(self):
        absorption_matrix = np.array([
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
        ])
        mus_prime = np.array([10.0, 10.0, 10.0])
        target_mu_a = np.array([0.3, 0.0, 0.0])
        reflectance = processing._mu_a_to_reflectance_km(
            target_mu_a[np.newaxis, :],
            mus_prime[np.newaxis, :],
        ).reshape(1, 1, -1)

        concentrations, _rmse_map, _fitted_od = processing.solve_unmixing_km(
            reflectance,
            absorption_matrix,
            mus_prime,
        )

        self.assertGreaterEqual(float(concentrations[0, 0, 0]), 0.0)
        self.assertGreaterEqual(float(concentrations[0, 0, 1]), 0.0)

    def test_compute_bilirubin_index_returns_od_difference(self):
        reflectance = np.array([[[0.25, 0.5, 0.8]]], dtype=float)

        result = processing.compute_bilirubin_index(reflectance)

        expected = -np.log10(0.25) + np.log10(0.5)
        self.assertTrue(np.allclose(result["bi_raw"], np.array([[expected]])))
        self.assertTrue(np.allclose(result["bi_corrected"], result["bi_raw"]))
        self.assertIsNone(result["od_ref"])

    def test_compute_bilirubin_index_applies_optional_hb_correction(self):
        reflectance = np.array([[[0.25, 0.5, 0.8]]], dtype=float)

        result = processing.compute_bilirubin_index(
            reflectance,
            wavelength_index_ref=2,
            k_hb_correction=0.1,
        )

        raw = -np.log10(0.25) + np.log10(0.5)
        od_ref = -np.log10(0.8)
        self.assertTrue(np.allclose(result["od_ref"], np.array([[od_ref]])))
        self.assertTrue(np.allclose(result["bi_corrected"], np.array([[raw - 0.1 * od_ref]])))

    def test_km_solver_clips_negative_absorption_basis_entries(self):
        absorption_matrix = np.array([
            [1.0, -10.0],
            [0.0, 1.0],
        ])
        mus_prime = np.array([10.0, 10.0])
        true_concentrations = np.array([0.1, 0.2])
        clipped_matrix = np.clip(absorption_matrix, 0.0, None)
        mu_a = clipped_matrix @ true_concentrations
        reflectance = processing._mu_a_to_reflectance_km(
            mu_a[np.newaxis, :],
            mus_prime[np.newaxis, :],
        ).reshape(1, 1, -1)

        concentrations, _rmse_map, _fitted_od = processing.solve_unmixing_km(
            reflectance,
            absorption_matrix,
            mus_prime,
        )

        self.assertTrue(
            np.allclose(concentrations[0, 0, :], true_concentrations, atol=1e-10)
        )

    def test_build_absorption_matrix_can_clip_negative_extrapolated_extinction(self):
        led_wl = np.array([500.0, 600.0, 700.0])
        led_emission = {600: np.array([0.0, 1.0, 0.0])}
        chromophore_spectra = {
            "short_range": (
                np.array([400.0, 500.0]),
                np.array([10.0, 0.0]),
            )
        }

        unclipped, _ = processing.build_absorption_matrix(
            led_wl,
            led_emission,
            chromophore_spectra,
            led_wavelengths=[600],
            chromophore_names=["short_range"],
        )
        clipped, _ = processing.build_absorption_matrix(
            led_wl,
            led_emission,
            chromophore_spectra,
            led_wavelengths=[600],
            chromophore_names=["short_range"],
            clip_negative_extinction=True,
        )

        self.assertLess(float(unclipped[0, 0]), 0.0)
        self.assertGreaterEqual(float(clipped[0, 0]), 0.0)

    def test_km_solver_requires_scattering_profile(self):
        reflectance = np.ones((1, 1, 2)) * 0.5
        absorption_matrix = np.eye(2)

        with self.assertRaises(ValueError):
            processing.solve_unmixing_km(reflectance, absorption_matrix, None)

    def test_solve_unmixing_dispatches_km_when_reflectance_is_provided(self):
        absorption_matrix = np.eye(2)
        mus_prime = np.array([10.0, 10.0])
        true_concentrations = np.array([0.1, 0.2])
        mu_a = absorption_matrix @ true_concentrations
        reflectance = processing._mu_a_to_reflectance_km(
            mu_a[np.newaxis, :],
            mus_prime[np.newaxis, :],
        ).reshape(1, 1, -1)
        od_placeholder = np.zeros_like(reflectance)

        concentrations, _rmse_map, _fitted_od = processing.solve_unmixing(
            od_placeholder,
            absorption_matrix,
            method="km",
            mus_prime=mus_prime,
            reflectance=reflectance,
        )

        self.assertTrue(
            np.allclose(concentrations[0, 0, :], true_concentrations, atol=1e-10)
        )


if __name__ == "__main__":
    unittest.main()
