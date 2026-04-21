"""QT-019: End-to-end interaction tests for key GUI flows.

Covers four critical interaction flows using mocks/fakes:
  1. Sample selection updates all panels (maps, inspector, diagnostics, stats, bar charts).
  2. View toggles and band toggles trigger maps-panel redraw path.
  3. Run / Save button state transitions through worker success and failure.
  4. Save export path is invoked only after results are available.

All tests:
  - Use pytest (pytest-qt when available).
  - Skip gracefully if PySide6 is unavailable.
  - Avoid external datasets by mocking app.core io/processing/export.
  - Are deterministic and fast.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Session-scared QApplication
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """Shared QApplication — skip if PySide6 is not installed."""
    pytest.importorskip("PySide6", reason="PySide6 is not installed; skipping Qt tests")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv or ["pytest-qt019"])
    return app


# ---------------------------------------------------------------------------
# Helper: pump event loop
# ---------------------------------------------------------------------------

def _pump(qapp, ms: int = 50) -> None:
    """Process events and yield briefly so queued signals are delivered."""
    from PySide6.QtTest import QTest

    QTest.qWait(ms)
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Helper: find toolbar buttons by objectName
# ---------------------------------------------------------------------------

def _find_button(window, object_name: str):
    from PySide6.QtWidgets import QPushButton

    return window._impl.findChild(QPushButton, object_name)


def _find_combo(window, object_name: str):
    from PySide6.QtWidgets import QComboBox

    return window._impl.findChild(QComboBox, object_name)


def _find_label(window, object_name: str):
    from PySide6.QtWidgets import QLabel

    return window._impl.findChild(QLabel, object_name)


def _find_progress(window):
    from PySide6.QtWidgets import QProgressBar

    return window._impl.findChild(QProgressBar, "progress_bar")


# ---------------------------------------------------------------------------
# Window fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def window(qapp, monkeypatch):
    """Create and show a main window; close after each test."""
    from app.gui_qt.main_window import SpectralUnmixingMainWindow

    w = SpectralUnmixingMainWindow()
    w._impl.show()
    qapp.processEvents()
    yield w
    w._impl.close()
    qapp.processEvents()


# ===========================================================================
# Flow 1 — Sample selection updates all panels
# ===========================================================================

class TestSampleSelectionUpdatesPanels:
    """Verify that selecting a sample from the sidebar combo dispatches data
    to every right-hand panel."""

    def _make_sample_result(self, name: str, value: float = 1.0) -> dict:
        return {
            "concentrations": np.full((4, 4, 2), value),
            "chromophore_names": ["HbO2", "Hb"],
            "derived": {"THb": np.full((4, 4), value * 2)},
            "derived_maps": {"THb": np.full((4, 4), value * 2)},
            "rmse_map": np.full((4, 4), value * 0.01),
            "diagnostics": {
                "global_rmse": value * 0.01,
                "condition_number": 10.0,
                "n_nan_pixels": 0,
                "n_negative_reflectance": 0,
                "warnings": [],
            },
            "wavelengths": [500.0, 550.0],
            "reflectance": np.full((4, 4, 2), value * 0.5),
            "od_cube": np.full((4, 4, 2), value * 0.3),
        }

    def test_selecting_sample_dispatches_to_all_five_panels(self, window, qapp):
        """Choosing a sample from the combo calls show_results / set_data on
        maps, inspector, diagnostics, stats, and bar-chart panels."""
        sample_a = self._make_sample_result("A", value=1.0)
        sample_b = self._make_sample_result("B", value=2.0)

        window._results = {"A": sample_a, "B": sample_b}
        window.set_samples(["A", "B"])
        qapp.processEvents()

        # Clear any initial callbacks from set_samples
        for panel in [
            window._maps_panel,
            window._inspector_panel,
            window._diagnostics_panel,
            window._stats_panel,
            window._barcharts_panel,
        ]:
            panel.show_results = MagicMock()
            panel.set_data = MagicMock()

        # Now select sample B
        window.select_sample("B")
        qapp.processEvents()

        # Maps panel receives show_results with sample_b data
        window._maps_panel.show_results.assert_called_once()
        maps_arg = window._maps_panel.show_results.call_args[0][0]
        assert maps_arg is sample_b

        # Inspector panel receives set_data with sample_b
        window._inspector_panel.set_data.assert_called_once()
        inspector_arg = window._inspector_panel.set_data.call_args[0][0]
        assert inspector_arg is sample_b

        # Diagnostics panel receives set_data with diagnostics + rmse_map
        window._diagnostics_panel.set_data.assert_called_once()
        diag_arg = window._diagnostics_panel.set_data.call_args[0][0]
        assert diag_arg["diagnostics"] == sample_b["diagnostics"]
        np.testing.assert_array_equal(diag_arg["rmse_map"], sample_b["rmse_map"])

        # Stats panel receives set_data with sample_b
        window._stats_panel.set_data.assert_called_once()
        stats_arg = window._stats_panel.set_data.call_args[0][0]
        assert stats_arg is sample_b

        # Bar-chart panel receives the full sample mapping for cross-sample comparison
        window._barcharts_panel.set_data.assert_called_once()
        barcharts_arg = window._barcharts_panel.set_data.call_args[0][0]
        assert barcharts_arg is window._results

    def test_selecting_different_sample_updates_panels_with_new_data(self, window, qapp):
        """Switching from sample A to sample B sends B's data to all panels."""
        sample_a = self._make_sample_result("A", value=1.0)
        sample_b = self._make_sample_result("B", value=2.0)

        window._results = {"A": sample_a, "B": sample_b}
        window.set_samples(["A", "B"])
        qapp.processEvents()

        # Spy on panels
        for panel in [
            window._maps_panel,
            window._inspector_panel,
            window._diagnostics_panel,
            window._stats_panel,
            window._barcharts_panel,
        ]:
            panel.show_results = MagicMock()
            panel.set_data = MagicMock()

        # set_samples auto-selects "A" (index 0), so select "B" to trigger signal
        window.select_sample("B")
        qapp.processEvents()
        window._maps_panel.show_results.assert_called()
        maps_call_b = window._maps_panel.show_results.call_args[0][0]
        assert maps_call_b is sample_b

        # Clear mocks and select A
        for panel in [
            window._maps_panel,
            window._inspector_panel,
            window._diagnostics_panel,
            window._stats_panel,
            window._barcharts_panel,
        ]:
            panel.show_results.reset_mock()
            panel.set_data.reset_mock()

        window.select_sample("A")
        qapp.processEvents()

        maps_call_a = window._maps_panel.show_results.call_args[0][0]
        assert maps_call_a is sample_a
        assert maps_call_a is not sample_b

    def test_selecting_sample_updates_status_label(self, window, qapp):
        """Status label reflects the currently selected sample name."""
        sample = self._make_sample_result("my_sample")
        window._results = {"my_sample": sample}
        window.set_samples(["my_sample"])
        qapp.processEvents()

        window.select_sample("my_sample")
        qapp.processEvents()

        status = _find_label(window, "status_label")
        assert status is not None
        assert "my_sample" in status.text()

    def test_selecting_unknown_sample_shows_warning(self, window, qapp):
        """Selecting a sample not in _results shows a warning in sidebar."""
        from PySide6.QtWidgets import QTextEdit
        from app.gui_qt.main_window import WARNINGS_TEXT_OBJECT_NAME

        window._results = {"existing": self._make_sample_result("existing")}
        window.set_samples(["existing", "ghost"])
        qapp.processEvents()

        window.select_sample("ghost")
        qapp.processEvents()

        warnings_text = window._impl.findChild(QTextEdit, WARNINGS_TEXT_OBJECT_NAME)
        assert warnings_text is not None
        assert "No processed data" in warnings_text.toPlainText()

    def test_selecting_sample_with_warnings_propagates_to_sidebar(self, window, qapp):
        """Warnings from diagnostics appear in the sidebar warnings text."""
        from PySide6.QtWidgets import QTextEdit
        from app.gui_qt.main_window import WARNINGS_TEXT_OBJECT_NAME

        sample = self._make_sample_result("warn_sample")
        sample["diagnostics"]["warnings"] = ["High RMSE detected", "Low SNR"]
        window._results = {"warn_sample": sample}
        window.set_samples(["warn_sample"])
        qapp.processEvents()

        window.select_sample("warn_sample")
        qapp.processEvents()

        warnings_text = window._impl.findChild(QTextEdit, WARNINGS_TEXT_OBJECT_NAME)
        text = warnings_text.toPlainText()
        assert "High RMSE detected" in text
        assert "Low SNR" in text


# ===========================================================================
# Flow 2 — View toggles and band toggles trigger maps redraw
# ===========================================================================

class TestViewAndBandTogglesTriggerRedraw:
    """Verify that changing the view combo or band combo on the maps panel
    triggers the internal _redraw() method."""

    def _load_data_into_maps_panel(self, window):
        """Helper: populate the maps panel with enough data for all view modes."""
        window._results = {
            "sample_1": {
                "concentrations": np.random.rand(4, 4, 2),
                "chromophore_names": ["HbO2", "Hb"],
                "derived_maps": {"THb": np.random.rand(4, 4), "StO2": np.random.rand(4, 4)},
                "reflectance": np.random.rand(4, 4, 3),
                "od_cube": np.random.rand(4, 4, 3),
                "wavelengths": [500.0, 550.0, 600.0],
            }
        }
        window.set_samples(["sample_1"])

    def test_view_combo_change_triggers_redraw(self, window, qapp):
        """Switching the view combo on the maps panel calls _redraw."""
        self._load_data_into_maps_panel(window)
        qapp.processEvents()

        maps_panel = window._maps_panel
        redraw_spy = MagicMock(side_effect=maps_panel._redraw)
        maps_panel._redraw = redraw_spy

        view_combo = _find_combo(window, "view_combo")
        assert view_combo is not None

        # Change from default "Chromophore Maps" to "Derived Maps"
        view_combo.setCurrentText("Derived Maps")
        qapp.processEvents()

        redraw_spy.assert_called()

    def test_band_combo_change_triggers_redraw(self, window, qapp):
        """Switching the band combo on the maps panel calls _redraw."""
        self._load_data_into_maps_panel(window)
        qapp.processEvents()

        maps_panel = window._maps_panel
        redraw_spy = MagicMock(side_effect=maps_panel._redraw)
        maps_panel._redraw = redraw_spy

        band_combo = _find_combo(window, "band_combo")
        assert band_combo is not None

        # Switch to Raw view so the band combo is enabled (only relevant there)
        view_combo = _find_combo(window, "view_combo")
        view_combo.setCurrentText("Raw / Reflectance / OD")
        qapp.processEvents()

        # Change band index
        band_combo.setCurrentIndex(1)
        qapp.processEvents()

        redraw_spy.assert_called()

    def test_redraw_dispatches_to_correct_view_mode(self, window, qapp):
        """Each view mode draws a different method on the maps panel."""
        self._load_data_into_maps_panel(window)
        qapp.processEvents()

        maps_panel = window._maps_panel
        view_combo = _find_combo(window, "view_combo")
        band_combo = _find_combo(window, "band_combo")

        # Spy on the three draw methods
        draw_chromo = MagicMock()
        draw_derived = MagicMock()
        draw_raw = MagicMock()
        maps_panel._draw_chromophore_map = draw_chromo
        maps_panel._draw_derived_map = draw_derived
        maps_panel._draw_raw_band = draw_raw

        # Start from Derived view (index 1) to ensure signal fires
        view_combo.setCurrentIndex(1)
        qapp.processEvents()
        draw_derived.assert_called()

        # Reset
        draw_chromo.reset_mock()
        draw_derived.reset_mock()
        draw_raw.reset_mock()

        # Switch to Chromophore view (index 0)
        view_combo.setCurrentIndex(0)
        qapp.processEvents()
        draw_chromo.assert_called()

        # Reset
        draw_chromo.reset_mock()
        draw_derived.reset_mock()
        draw_raw.reset_mock()

        # Switch to Raw view (index 2)
        view_combo.setCurrentIndex(2)
        qapp.processEvents()
        draw_raw.assert_called()

    def test_rapid_toggle_does_not_accumulate_artists(self, window, qapp):
        """Toggling view modes repeatedly keeps figure axes bounded."""
        self._load_data_into_maps_panel(window)
        qapp.processEvents()

        view_combo = _find_combo(window, "view_combo")
        band_combo = _find_combo(window, "band_combo")
        fig = window._maps_panel._canvas.figure

        # Record the number of axes after a single full cycle through all views.
        # This establishes the baseline (max axes any single view produces).
        view_combo.setCurrentIndex(0)  # Chromophore Maps
        qapp.processEvents()
        baseline = len(fig.get_axes())

        view_combo.setCurrentIndex(1)  # Derived Maps
        qapp.processEvents()
        baseline = max(baseline, len(fig.get_axes()))

        view_combo.setCurrentIndex(2)  # Raw / Reflectance / OD
        qapp.processEvents()
        baseline = max(baseline, len(fig.get_axes()))

        # Now rapid-toggle 10 times — axes count should never exceed baseline.
        for i in range(10):
            view_combo.setCurrentIndex(i % 3)
            band_combo.setCurrentIndex(i % 3)
            qapp.processEvents()

        assert len(fig.get_axes()) <= baseline

    def test_band_toggle_with_no_data_does_not_crash(self, window, qapp):
        """Changing band combo when no data is loaded is safe."""
        # Band combo is initially disabled; enable it artificially to test
        band_combo = _find_combo(window, "band_combo")
        assert band_combo is not None
        band_combo.setEnabled(True)
        band_combo.addItem("500.0 nm")

        # _redraw should handle empty data gracefully
        window._maps_panel._redraw()
        qapp.processEvents()

        fig = window._maps_panel._canvas.figure
        # Should show placeholder
        assert len(fig.get_axes()) >= 1


# ===========================================================================
# Flow 3 — Run / Save button state transitions through worker success/failure
# ===========================================================================

class TestRunSaveButtonStateTransitions:
    """Verify the full lifecycle of Run and Save buttons through pipeline
    execution — both success and failure paths."""

    def test_initial_state_both_buttons_disabled(self, window, qapp):
        """At startup, Run and Save are both disabled."""
        run_btn = _find_button(window, "run_btn")
        save_btn = _find_button(window, "save_btn")

        assert run_btn is not None
        assert save_btn is not None
        assert not run_btn.isEnabled()
        assert not save_btn.isEnabled()

    def test_run_enabled_after_pipeline_fn_registered(self, window, qapp):
        """Registering a pipeline function enables the Run button."""
        window.set_pipeline_fn(lambda: {"key": "value"})
        qapp.processEvents()

        run_btn = _find_button(window, "run_btn")
        assert run_btn.isEnabled()

    def test_run_disabled_during_execution(self, window, qapp):
        """Run button is disabled while the pipeline is running."""
        import time

        def slow_pipeline():
            time.sleep(0.1)
            return {"samples": {"s1": {"concentrations": np.ones((2, 2, 1)),
                                        "chromophore_names": ["Hb"],
                                        "derived": {}, "rmse_map": np.ones((2, 2)),
                                        "diagnostics": {"warnings": []}}},
                    "chrom_scales": {}, "derived_scales": {}}

        window.set_pipeline_fn(slow_pipeline)
        qapp.processEvents()

        run_btn = _find_button(window, "run_btn")
        save_btn = _find_button(window, "save_btn")
        run_btn.click()
        qapp.processEvents()

        # During execution both should be disabled
        _pump(qapp, 20)
        assert not run_btn.isEnabled()
        assert not save_btn.isEnabled()

        # Wait for completion
        if window._thread is not None:
            window._thread.wait(5000)
        _pump(qapp, 200)

        # After success: Run re-enabled, Save enabled (has data)
        assert run_btn.isEnabled()
        assert save_btn.isEnabled()

    def test_buttons_after_success_run(self, window, qapp):
        """After a successful run: Run re-enabled, Save enabled."""
        result_payload = {
            "samples": {
                "sample_1": {
                    "concentrations": np.ones((2, 2, 1)),
                    "chromophore_names": ["Hb"],
                    "derived": {},
                    "rmse_map": np.ones((2, 2)),
                    "diagnostics": {"warnings": []},
                }
            },
            "chrom_scales": {},
            "derived_scales": {},
        }

        window.set_pipeline_fn(lambda: result_payload)
        qapp.processEvents()

        run_btn = _find_button(window, "run_btn")
        save_btn = _find_button(window, "save_btn")
        run_btn.click()
        qapp.processEvents()

        if window._thread is not None:
            window._thread.wait(5000)
        _pump(qapp, 200)

        assert run_btn.isEnabled()
        assert save_btn.isEnabled()

    def test_buttons_after_failure_run(self, window, qapp):
        """After a failed run: Run re-enabled, Save stays disabled."""
        def failing_pipeline():
            raise RuntimeError("simulated pipeline failure")

        window.set_pipeline_fn(failing_pipeline)
        qapp.processEvents()

        run_btn = _find_button(window, "run_btn")
        save_btn = _find_button(window, "save_btn")
        run_btn.click()
        qapp.processEvents()

        if window._thread is not None:
            window._thread.wait(5000)
        _pump(qapp, 200)

        assert run_btn.isEnabled()
        assert not save_btn.isEnabled()

    def test_progress_bar_reaches_100_on_success(self, window, qapp):
        """Progress bar is set to 100 after a successful pipeline run."""
        window.set_pipeline_fn(lambda: {"data": True})
        qapp.processEvents()

        run_btn = _find_button(window, "run_btn")
        run_btn.click()
        qapp.processEvents()

        if window._thread is not None:
            window._thread.wait(5000)
        _pump(qapp, 200)

        progress = _find_progress(window)
        assert progress.value() == 100

    def test_progress_bar_reset_to_0_on_failure(self, window, qapp):
        """Progress bar resets to 0 after a failed pipeline run."""
        window.set_pipeline_fn(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        qapp.processEvents()

        run_btn = _find_button(window, "run_btn")
        run_btn.click()
        qapp.processEvents()

        if window._thread is not None:
            window._thread.wait(5000)
        _pump(qapp, 200)

        progress = _find_progress(window)
        assert progress.value() == 0

    def test_status_label_shows_completion_on_success(self, window, qapp):
        """Status label shows 'Pipeline complete.' after a successful run."""
        window.set_pipeline_fn(lambda: {"data": True})
        qapp.processEvents()

        run_btn = _find_button(window, "run_btn")
        run_btn.click()
        qapp.processEvents()

        if window._thread is not None:
            window._thread.wait(5000)
        _pump(qapp, 200)

        status = _find_label(window, "status_label")
        assert status is not None
        assert "Pipeline complete" in status.text()

    def test_status_label_shows_error_on_failure(self, window, qapp):
        """Status label contains error text after a failed run."""
        window.set_pipeline_fn(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        qapp.processEvents()

        run_btn = _find_button(window, "run_btn")
        run_btn.click()
        qapp.processEvents()

        if window._thread is not None:
            window._thread.wait(5000)
        _pump(qapp, 200)

        status = _find_label(window, "status_label")
        assert status is not None
        assert "Pipeline failed" in status.text()
        assert "boom" in status.text()

    def test_save_not_enabled_on_empty_results(self, window, qapp):
        """Save remains disabled when pipeline succeeds but returns empty dict."""
        window.set_pipeline_fn(lambda: {})
        qapp.processEvents()

        run_btn = _find_button(window, "run_btn")
        save_btn = _find_button(window, "save_btn")
        run_btn.click()
        qapp.processEvents()

        if window._thread is not None:
            window._thread.wait(5000)
        _pump(qapp, 200)

        assert run_btn.isEnabled()
        assert not save_btn.isEnabled()

    def test_double_click_ignored_while_running(self, window, qapp):
        """Clicking Run while already running does not start a second thread."""
        import time

        def slow_pipeline():
            time.sleep(0.15)
            return {"data": True}

        window.set_pipeline_fn(slow_pipeline)
        qapp.processEvents()

        run_btn = _find_button(window, "run_btn")
        run_btn.click()
        qapp.processEvents()

        first_thread = window._thread
        assert first_thread is not None

        # Second click should be a no-op
        run_btn.click()
        qapp.processEvents()
        assert window._thread is first_thread

        first_thread.wait(5000)
        _pump(qapp, 200)

    def test_on_results_ready_populates_results_dict(self, window, qapp):
        """After _on_results_ready with adapter payload, _results is populated."""
        payload = {
            "samples": {
                "alpha": {
                    "concentrations": np.ones((2, 2, 1)),
                    "chromophore_names": ["Hb"],
                    "derived": {},
                    "rmse_map": np.ones((2, 2)),
                    "diagnostics": {"warnings": []},
                }
            },
            "chrom_scales": {"Hb": (0.0, 1.0)},
            "derived_scales": {},
        }

        window._on_results_ready(payload)
        qapp.processEvents()

        assert "alpha" in window._results
        assert window._chrom_scales == {"Hb": (0.0, 1.0)}

    def test_on_run_failed_clears_results(self, window, qapp):
        """After _on_run_failed, _last_results is None and save is disabled."""
        # First set some results
        window._last_results = {"old": "data"}
        save_btn = _find_button(window, "save_btn")
        save_btn.setEnabled(True)

        window._on_run_failed("Pipeline failed: test error")
        qapp.processEvents()

        assert window._last_results is None
        assert not save_btn.isEnabled()


# ===========================================================================
# Flow 4 — Save export path invoked only after results
# ===========================================================================

class TestSaveExportOnlyAfterResults:
    """Verify that the export path (app.core.export.save_results) is only
    invoked when results are actually available."""

    def _make_sample_result(self) -> dict:
        return {
            "concentrations": np.ones((2, 2, 1)),
            "chromophore_names": ["Hb"],
            "derived": {"THb": np.ones((2, 2))},
            "rmse_map": np.ones((2, 2)),
            "diagnostics": {"warnings": []},
        }

    def test_save_button_disabled_when_no_results(self, window, qapp):
        """Save button is disabled when _results is empty."""
        save_btn = _find_button(window, "save_btn")
        assert save_btn is not None
        assert not save_btn.isEnabled()

    def test_save_enabled_after_results_loaded(self, window, qapp):
        """After _on_results_ready with valid samples, Save is enabled."""
        payload = {
            "samples": {"s1": self._make_sample_result()},
            "chrom_scales": {},
            "derived_scales": {},
        }
        window._on_results_ready(payload)
        qapp.processEvents()

        save_btn = _find_button(window, "save_btn")
        assert save_btn.isEnabled()

    def test_save_click_invokes_export_with_correct_args(self, window, qapp, monkeypatch):
        """Clicking Save calls export.save_results for each sample."""
        payload = {
            "samples": {
                "sample_x": self._make_sample_result(),
                "sample_y": self._make_sample_result(),
            },
            "chrom_scales": {},
            "derived_scales": {},
        }
        window._on_results_ready(payload)
        qapp.processEvents()

        exported_calls = []

        def fake_save(out_dir, sample_name, concentrations, chrom_names,
                      derived, rmse_map, diagnostics, **kwargs):
            exported_calls.append({
                "out_dir": out_dir,
                "sample_name": sample_name,
                "chrom_names": chrom_names,
            })

        monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                            lambda *_a, **_k: "/tmp/export_output")
        monkeypatch.setattr("app.core.export.save_results", fake_save)

        save_btn = _find_button(window, "save_btn")
        save_btn.click()
        qapp.processEvents()

        assert len(exported_calls) == 2
        names = {c["sample_name"] for c in exported_calls}
        assert names == {"sample_x", "sample_y"}
        for c in exported_calls:
            assert c["out_dir"] == "/tmp/export_output"
            assert c["chrom_names"] == ["Hb"]

    def test_save_not_invoked_when_results_empty(self, window, qapp, monkeypatch):
        """If _results is empty, clicking Save does not call export."""
        export_called = []

        def fake_save(*_a, **_k):
            export_called.append(True)

        monkeypatch.setattr("app.core.export.save_results", fake_save)
        monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                            lambda *_a, **_k: "/tmp/out")

        # _results is empty by default
        save_btn = _find_button(window, "save_btn")
        save_btn.click()
        qapp.processEvents()

        assert len(export_called) == 0

    def test_save_invoked_only_after_pipeline_success(self, window, qapp, monkeypatch):
        """Export is only callable after a successful pipeline run."""
        export_calls = []

        def fake_save(*_a, **_k):
            export_calls.append(True)

        monkeypatch.setattr("app.core.export.save_results", fake_save)
        monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                            lambda *_a, **_k: "/tmp/out")

        # Before any run, save should be disabled
        save_btn = _find_button(window, "save_btn")
        assert not save_btn.isEnabled()

        # Run a successful pipeline
        payload = {
            "samples": {"s1": self._make_sample_result()},
            "chrom_scales": {},
            "derived_scales": {},
        }
        window.set_pipeline_fn(lambda: payload)
        qapp.processEvents()

        run_btn = _find_button(window, "run_btn")
        run_btn.click()
        qapp.processEvents()

        if window._thread is not None:
            window._thread.wait(5000)
        _pump(qapp, 200)

        # Now save should be enabled and export should work
        assert save_btn.isEnabled()
        save_btn.click()
        qapp.processEvents()

        assert len(export_calls) == 1

    def test_save_not_invoked_after_pipeline_failure(self, window, qapp, monkeypatch):
        """After a failed pipeline, Save is disabled and export is not called."""
        export_calls = []

        def fake_save(*_a, **_k):
            export_calls.append(True)

        monkeypatch.setattr("app.core.export.save_results", fake_save)

        window.set_pipeline_fn(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        qapp.processEvents()

        run_btn = _find_button(window, "run_btn")
        save_btn = _find_button(window, "save_btn")
        run_btn.click()
        qapp.processEvents()

        if window._thread is not None:
            window._thread.wait(5000)
        _pump(qapp, 200)

        assert not save_btn.isEnabled()
        assert len(export_calls) == 0

    def test_save_cleared_after_new_root_selection(self, window, qapp, monkeypatch):
        """Selecting a new root folder clears results and disables Save."""
        # First, load results
        payload = {
            "samples": {"s1": self._make_sample_result()},
            "chrom_scales": {},
            "derived_scales": {},
        }
        window._on_results_ready(payload)
        qapp.processEvents()

        save_btn = _find_button(window, "save_btn")
        assert save_btn.isEnabled()

        # Simulate selecting a new root (which clears _results)
        fake_info = {
            "samples": ["/root/s1"],
            "sample_names": ["sample_1"],
            "ref_dir": "/root/ref",
            "dark_ref_dir": "/root/dark_ref",
            "wavelengths": [500],
        }

        monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                            lambda *_a, **_k: "/tmp/new_root")
        monkeypatch.setattr("app.core.io.detect_folders", lambda *_a, **_k: fake_info)
        monkeypatch.setattr("app.core.io.load_chromophore_spectra",
                            lambda *_a, **_k: {"Hb": (np.array([500.0]), np.array([1.0]))})

        select_root_btn = _find_button(window, "select_root_btn")
        select_root_btn.click()
        qapp.processEvents()

        # Save should be disabled after root selection clears results
        assert not save_btn.isEnabled()
        assert window._results == {}

    def test_save_dialog_cancel_does_not_export(self, window, qapp, monkeypatch):
        """If the user cancels the save dialog, export is not invoked."""
        payload = {
            "samples": {"s1": self._make_sample_result()},
            "chrom_scales": {},
            "derived_scales": {},
        }
        window._on_results_ready(payload)
        qapp.processEvents()

        export_calls = []
        monkeypatch.setattr("app.core.export.save_results",
                            lambda *_a, **_k: export_calls.append(True))
        # Return empty string to simulate dialog cancellation
        monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                            lambda *_a, **_k: "")

        save_btn = _find_button(window, "save_btn")
        save_btn.click()
        qapp.processEvents()

        assert len(export_calls) == 0
