#!/usr/bin/env python3
"""
Test script to verify chromophore maps update correctly during repeated unmixing runs.

This script simulates the behavior of the visualization panel when running the unmixing
pipeline multiple times with different configurations to check if the chromophore maps
are properly updated.
"""

import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import matplotlib
import numpy as np

matplotlib.use("Agg")  # Non-interactive backend
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure


class MockVizPanel:
    """Mock visualization panel to test chromophore map updating behavior."""

    def __init__(self):
        self.fig = Figure(figsize=(12, 7), dpi=100)
        self.canvas = FigureCanvasAgg(self.fig)
        self._current_res = None
        self._chrom_scales = None

    def show_results(self, res, chrom_scales=None):
        """Simulate showing results for a sample."""
        self._current_res = res
        self._chrom_scales = chrom_scales
        self._redraw()

    def _redraw(self):
        """Redraw the current view."""
        if self._current_res is None:
            return

        self.fig.clear()
        self._draw_chromophore_maps(self._current_res)
        self.fig.tight_layout()
        self.canvas.draw()

    def _draw_chromophore_maps(self, res):
        """Draw chromophore maps - this is the method we're testing."""
        conc = res["concentrations"]
        names = res["chromophore_names"].copy()
        if res.get("include_background", True):
            names.append("background")
        n = len(names)
        cols = 3
        rows = (n + cols - 1) // cols

        for i, name in enumerate(names):
            ax = self.fig.add_subplot(rows, cols, i + 1)
            data = conc[:, :, i]
            vmin, vmax = (
                self._chrom_scales.get(name, (None, None))
                if self._chrom_scales
                else (None, None)
            )
            im = ax.imshow(data, cmap="viridis", aspect="equal", vmin=vmin, vmax=vmax)

            finite = data[np.isfinite(data)]
            if finite.size > 0:
                mean_val = finite.mean()
                median_val = np.median(finite)
                title = f"{name}\nμ={mean_val:.3e}, med={median_val:.3e}"
            else:
                title = name

            ax.set_title(title, fontsize=10)
            ax.set_xticks([])
            ax.set_yticks([])
            self.fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    def get_chromophore_names(self):
        """Get the names of chromophores currently displayed."""
        names = []
        for ax in self.fig.axes:
            title = ax.get_title()
            if title:
                # Extract just the chromophore name (first line of title)
                chrom_name = title.split("\n")[0]
                names.append(chrom_name)
        return names

    def get_chromophore_data_stats(self):
        """Get statistics for each chromophore's displayed data."""
        stats = []
        for ax in self.fig.axes:
            title = ax.get_title()
            if title:
                chrom_name = title.split("\n")[0]
                # Find the image in this axes
                for child in ax.get_children():
                    if hasattr(child, "get_array"):
                        arr = child.get_array()
                        if arr is not None and arr.size > 0:
                            stats.append(
                                {
                                    "name": chrom_name,
                                    "min": float(np.nanmin(arr)),
                                    "max": float(np.nanmax(arr)),
                                    "mean": float(np.nanmean(arr)),
                                    "shape": arr.shape,
                                }
                            )
                            break
        return stats

    def get_subplot_count(self):
        """Get the number of main subplots (chromophores displayed)."""
        count = 0
        for ax in self.fig.axes:
            if ax.get_title():
                count += 1
        return count


def create_mock_results(chromophore_names, include_background=True, data_seed=42):
    """Create mock unmixing results for testing."""
    np.random.seed(data_seed)

    n_components = len(chromophore_names) + (1 if include_background else 0)
    shape = (64, 64, n_components)

    # Create concentration data with distinctive values per component
    concentrations = np.zeros(shape)
    for i in range(n_components):
        concentrations[:, :, i] = np.random.rand(64, 64) * 100 + i * 10

    return {
        "concentrations": concentrations,
        "chromophore_names": chromophore_names,
        "include_background": include_background,
    }


def test_chromophore_map_updates():
    """Test that chromophore maps update correctly during repeated runs."""

    print("=" * 70)
    print("Testing Chromophore Map Updates During Repeated Unmixing")
    print("=" * 70)

    panel = MockVizPanel()
    tests_passed = 0
    tests_failed = 0

    # Test 1: Basic update - same configuration, different data
    print("\n[Test 1] Basic update with same configuration...")
    try:
        res1 = create_mock_results(
            ["HbO2", "Hb", "Melanin"], include_background=True, data_seed=1
        )
        panel.show_results(res1)

        chromophores_1 = panel.get_chromophore_names()
        stats_1 = panel.get_chromophore_data_stats()

        # Run again with different data but same config
        res2 = create_mock_results(
            ["HbO2", "Hb", "Melanin"], include_background=True, data_seed=2
        )
        panel.show_results(res2)

        chromophores_2 = panel.get_chromophore_names()
        stats_2 = panel.get_chromophore_data_stats()

        expected_chromophores = ["HbO2", "Hb", "Melanin", "background"]
        assert chromophores_2 == expected_chromophores, (
            f"Expected {expected_chromophores}, got {chromophores_2}"
        )

        # Verify data changed between runs
        data_changed = any(s1["mean"] != s2["mean"] for s1, s2 in zip(stats_1, stats_2))
        assert data_changed, "Data should change between runs with different seeds"

        print(f"  ✓ Chromophores: {chromophores_2}")
        print(f"  ✓ Data updated correctly")
        tests_passed += 1
    except AssertionError as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1

    # Test 2: Adding more chromophores
    print("\n[Test 2] Adding more chromophores...")
    try:
        res3 = create_mock_results(["HbO2", "Hb"], include_background=True, data_seed=3)
        panel.show_results(res3)
        count_3 = panel.get_subplot_count()

        res4 = create_mock_results(
            ["HbO2", "Hb", "Melanin", "Water", "Bilirubin"],
            include_background=True,
            data_seed=4,
        )
        panel.show_results(res4)
        count_4 = panel.get_subplot_count()

        expected_count = 6  # 5 chromophores + background
        assert count_4 == expected_count, (
            f"Expected {expected_count} subplots, got {count_4}"
        )

        chromophores = panel.get_chromophore_names()
        expected_chromophores = [
            "HbO2",
            "Hb",
            "Melanin",
            "Water",
            "Bilirubin",
            "background",
        ]
        assert chromophores == expected_chromophores, (
            f"Expected {expected_chromophores}, got {chromophores}"
        )

        print(
            f"  ✓ Subplots increased: {count_3} → {count_4} (expected {expected_count})"
        )
        print(f"  ✓ Chromophores: {chromophores}")
        tests_passed += 1
    except AssertionError as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1

    # Test 3: Removing chromophores
    print("\n[Test 3] Removing chromophores...")
    try:
        res5 = create_mock_results(
            ["HbO2", "Hb", "Melanin", "Water"], include_background=True, data_seed=5
        )
        panel.show_results(res5)
        count_5 = panel.get_subplot_count()

        res6 = create_mock_results(["HbO2", "Hb"], include_background=True, data_seed=6)
        panel.show_results(res6)
        count_6 = panel.get_subplot_count()

        expected_count = 3  # 2 chromophores + background
        assert count_6 == expected_count, (
            f"Expected {expected_count} subplots, got {count_6}"
        )

        chromophores = panel.get_chromophore_names()
        expected_chromophores = ["HbO2", "Hb", "background"]
        assert chromophores == expected_chromophores, (
            f"Expected {expected_chromophores}, got {chromophores}"
        )

        print(
            f"  ✓ Subplots decreased: {count_5} → {count_6} (expected {expected_count})"
        )
        print(f"  ✓ Chromophores: {chromophores}")
        tests_passed += 1
    except AssertionError as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1

    # Test 4: Toggle background on/off
    print("\n[Test 4] Toggling background component...")
    try:
        res7 = create_mock_results(
            ["HbO2", "Hb", "Melanin"], include_background=True, data_seed=7
        )
        panel.show_results(res7)
        chromophores_with_bg = panel.get_chromophore_names()

        res8 = create_mock_results(
            ["HbO2", "Hb", "Melanin"], include_background=False, data_seed=8
        )
        panel.show_results(res8)
        chromophores_without_bg = panel.get_chromophore_names()

        assert "background" in chromophores_with_bg, (
            "Background should be in chromophores when included"
        )
        assert "background" not in chromophores_without_bg, (
            "Background should not be in chromophores when excluded"
        )

        print(f"  ✓ With background: {chromophores_with_bg}")
        print(f"  ✓ Without background: {chromophores_without_bg}")
        tests_passed += 1
    except AssertionError as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1

    # Test 5: Verify image data shapes are correct
    print("\n[Test 5] Verify image data shapes are correct...")
    try:
        res = create_mock_results(
            ["HbO2", "Hb", "Melanin"], include_background=True, data_seed=80
        )
        panel.show_results(res)

        stats = panel.get_chromophore_data_stats()

        expected_chromophores = 4  # HbO2, Hb, Melanin, background
        assert len(stats) == expected_chromophores, (
            f"Expected {expected_chromophores} chromophores, got {len(stats)}"
        )

        for stat in stats:
            assert stat["shape"] == (64, 64), (
                f"Expected shape (64, 64), got {stat['shape']} for {stat['name']}"
            )

        print(f"  ✓ All {len(stats)} images have correct shape (64, 64)")
        tests_passed += 1
    except AssertionError as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1

    # Test 6: Multiple rapid updates (stress test)
    print("\n[Test 6] Multiple rapid updates (stress test)...")
    try:
        configs = [
            (["HbO2"], True),
            (["HbO2", "Hb"], True),
            (["HbO2", "Hb", "Melanin"], True),
            (["HbO2", "Hb", "Melanin", "Water"], False),
            (["HbO2"], False),
            (["HbO2", "Hb", "Melanin", "Water", "Bilirubin"], True),
        ]

        for i, (chroms, bg) in enumerate(configs):
            res = create_mock_results(chroms, include_background=bg, data_seed=i)
            panel.show_results(res)
            expected = len(chroms) + (1 if bg else 0)
            actual = panel.get_subplot_count()
            assert actual == expected, (
                f"Config {i}: Expected {expected} subplots, got {actual}"
            )

        print(f"  ✓ All {len(configs)} rapid updates completed successfully")
        tests_passed += 1
    except AssertionError as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1

    # Test 7: Verify figure is properly cleared between runs
    print("\n[Test 7] Verify figure is properly cleared between runs...")
    try:
        # Start with many subplots
        res_big = create_mock_results(
            ["HbO2", "Hb", "Melanin", "Water", "Bilirubin"],
            include_background=True,
            data_seed=100,
        )
        panel.show_results(res_big)

        initial_count = panel.get_subplot_count()
        initial_chromophores = panel.get_chromophore_names()

        # Now switch to minimal
        res_small = create_mock_results(
            ["HbO2"], include_background=False, data_seed=101
        )
        panel.show_results(res_small)

        final_count = panel.get_subplot_count()
        final_chromophores = panel.get_chromophore_names()

        expected_final_count = 1  # Only HbO2, no background
        assert final_count == expected_final_count, (
            f"Expected {expected_final_count} subplots after clear, got {final_count}"
        )
        assert final_chromophores == ["HbO2"], (
            f"Expected ['HbO2'], got {final_chromophores}"
        )

        print(f"  ✓ Subplots after clear: {initial_count} → {final_count}")
        print(f"  ✓ Chromophores: {initial_chromophores} → {final_chromophores}")
        tests_passed += 1
    except AssertionError as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1

    # Summary
    print("\n" + "=" * 70)
    print(f"TEST SUMMARY: {tests_passed} passed, {tests_failed} failed")
    print("=" * 70)

    if tests_failed > 0:
        print(
            "\n⚠️  Some tests failed. There may be issues with chromophore map updates."
        )
        print("   Consider checking if fig.clear() properly removes all axes.")
        return False
    else:
        print("\n✓ All tests passed. Chromophore maps appear to update correctly.")
        return True


def test_with_visual_verification():
    """Create visual output for manual verification of chromophore map updates."""
    print("\n" + "=" * 70)
    print("Creating Visual Verification Images")
    print("=" * 70)

    panel = MockVizPanel()

    # Create a sequence of runs with different configurations
    test_cases = [
        {
            "name": "Run_1_2_chromophores_plus_bg",
            "chroms": ["HbO2", "Hb"],
            "bg": True,
            "seed": 1,
        },
        {
            "name": "Run_2_4_chromophores_plus_bg",
            "chroms": ["HbO2", "Hb", "Melanin", "Water"],
            "bg": True,
            "seed": 2,
        },
        {
            "name": "Run_3_2_chromophores_no_bg",
            "chroms": ["HbO2", "Hb"],
            "bg": False,
            "seed": 3,
        },
        {
            "name": "Run_4_5_chromophores_plus_bg",
            "chroms": ["HbO2", "Hb", "Melanin", "Water", "Bilirubin"],
            "bg": True,
            "seed": 4,
        },
    ]

    output_dir = "test_outputs"
    os.makedirs(output_dir, exist_ok=True)

    for i, tc in enumerate(test_cases):
        res = create_mock_results(
            tc["chroms"], include_background=tc["bg"], data_seed=tc["seed"]
        )
        panel.show_results(res)

        # Save figure
        filename = os.path.join(
            output_dir, f"chromophore_update_test_{i + 1:02d}_{tc['name']}.png"
        )
        panel.fig.savefig(filename, dpi=100, bbox_inches="tight")

        subplot_count = panel.get_subplot_count()
        chromophores = panel.get_chromophore_names()
        stats = panel.get_chromophore_data_stats()

        print(f"\n[{tc['name']}]")
        print(f"  Saved: {filename}")
        print(f"  Subplots: {subplot_count}")
        print(f"  Chromophores: {chromophores}")
        print(f"  Data shapes: {[s['shape'] for s in stats]}")

    print(f"\n✓ Visual verification images saved to '{output_dir}/'")
    print("  Review these images to manually verify correct subplot arrangement.")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("CHROMOPHORE MAP UPDATE TEST SUITE")
    print("=" * 70)

    # Run automated tests
    all_passed = test_chromophore_map_updates()

    # Create visual verification images
    test_with_visual_verification()

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)
