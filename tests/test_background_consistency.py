#!/usr/bin/env python3
import os
import sys
import unittest
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core import processing
from app.core import io


class TestBackgroundConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_data_dir = Path(__file__).parent.parent / 'liquid_phantoms_for_unmixing_cropped'
        cls.data_dir = Path(__file__).parent.parent / 'data'
        
        if not cls.sample_data_dir.exists():
            raise FileNotFoundError('Sample data directory not found: ' + str(cls.sample_data_dir))
        
        cls.info = io.detect_folders(str(cls.sample_data_dir))
        cls.ref_cube = io.load_image_cube(cls.info['ref_dir'], cls.info['wavelengths'])
        cls.dark_cube = io.load_image_cube(cls.info['dark_ref_dir'], cls.info['wavelengths'])
        cls.chrom_spectra = io.load_chromophore_spectra(str(cls.data_dir))
        cls.led_wl, cls.led_em = io.load_led_emission(str(cls.data_dir), cls.info['wavelengths'])
        cls.pen_wl, cls.pen_depth = io.load_penetration_depth(str(cls.data_dir))
        cls.sample_dir = cls.info['samples'][0]
        cls.sample_name = cls.info['sample_names'][0]
        cls.sample_cube = io.load_image_cube(cls.sample_dir, cls.info['wavelengths'])
        cls.base_reflectance = processing.compute_reflectance(cls.sample_cube, cls.ref_cube, cls.dark_cube)
        cls.base_od = processing.compute_optical_density(cls.base_reflectance)
        cls.selected_chroms = ['HbO2', 'Hb']
        
        print()
        print('='*60)
        print('Test Class Setup Complete')
        print('Sample: ' + cls.sample_name)
        print('Wavelengths: ' + str(cls.info['wavelengths']))
        print('Chromophores: ' + str(list(cls.chrom_spectra.keys())))
        print('='*60)
    
    def _build_overlap_matrix(self, background_value, include_background=True):
        return processing.build_overlap_matrix(
            self.led_wl, self.led_em, self.chrom_spectra, 
            self.pen_wl, self.pen_depth, self.info['wavelengths'],
            chromophore_names=self.selected_chroms,
            include_background=include_background,
            background_value=background_value,
        )
    
    def _run_unmixing(self, od_cube, A, method='ls'):
        concentrations, rmse_map, fitted_od = processing.solve_unmixing(od_cube, A, method=method)
        derived = processing.compute_derived_maps(concentrations, ['HbO2', 'Hb'])
        return {
            'concentrations': concentrations,
            'rmse_map': rmse_map,
            'fitted_od': fitted_od,
            'derived': derived,
            'mean_thb': np.nanmean(derived['THb']),
            'median_thb': np.nanmedian(derived['THb']),
            'mean_sto2': np.nanmean(derived['StO2']),
            'median_sto2': np.nanmedian(derived['StO2']),
        }
    
    def test_background_value_affects_unmixing(self):
        print()
        print('--- Test: Background Value Affects Unmixing ---')
        A_2500, _ = self._build_overlap_matrix(background_value=2500.0)
        result_2500 = self._run_unmixing(self.base_od, A_2500)
        A_100, _ = self._build_overlap_matrix(background_value=100.0)
        result_100 = self._run_unmixing(self.base_od, A_100)
        A_0, _ = self._build_overlap_matrix(background_value=0.0)
        result_0 = self._run_unmixing(self.base_od, A_0)

        # Background values 2500 and 100 both produce a constant column in A,
        # so the chromophore coefficients are identical (only bg coefficient scales).
        # Only bg=0 (no background column) changes the chromophore maps.
        self.assertTrue(np.allclose(result_2500['mean_thb'], result_100['mean_thb']))
        self.assertFalse(np.allclose(result_2500['mean_thb'], result_0['mean_thb']))

        print('  Mean THb (bg=2500): ' + str(round(result_2500['mean_thb'], 4)))
        print('  Mean THb (bg=100):  ' + str(round(result_100['mean_thb'], 4)))
        print('  Mean THb (bg=0):    ' + str(round(result_0['mean_thb'], 4)))
        print('  OK: bg=0 differs; bg=2500 and bg=100 produce identical chromophore maps')
    
    def test_reverting_background_value_preserves_results(self):
        print()
        print('--- Test: Reverting Background Value Preserves Results ---')
        A_2500_1, _ = self._build_overlap_matrix(background_value=2500.0)
        result_2500_1 = self._run_unmixing(self.base_od, A_2500_1)
        A_100, _ = self._build_overlap_matrix(background_value=100.0)
        result_100 = self._run_unmixing(self.base_od, A_100)
        A_2500_2, _ = self._build_overlap_matrix(background_value=2500.0)
        result_2500_2 = self._run_unmixing(self.base_od, A_2500_2)
        
        self.assertTrue(np.allclose(result_2500_1['mean_thb'], result_2500_2['mean_thb']))
        self.assertTrue(np.allclose(result_2500_1['median_thb'], result_2500_2['median_thb']))
        self.assertTrue(np.allclose(result_2500_1['concentrations'], result_2500_2['concentrations']))
        self.assertTrue(np.allclose(result_2500_1['rmse_map'], result_2500_2['rmse_map']))
        self.assertTrue(np.allclose(result_2500_1['fitted_od'], result_2500_2['fitted_od']))
        
        print('  Mean THb (first):  ' + str(round(result_2500_1['mean_thb'], 6)))
        print('  Mean THb (reverted): ' + str(round(result_2500_2['mean_thb'], 6)))
        diff = np.max(np.abs(result_2500_1['derived']['THb'] - result_2500_2['derived']['THb']))
        print('  Max diff: ' + str(diff))
        print('  OK: Results preserved when reverting background value')


if __name__ == '__main__':
    unittest.main(verbosity=2)
