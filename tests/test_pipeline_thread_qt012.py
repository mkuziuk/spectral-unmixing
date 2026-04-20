"""QT-012: Pipeline thread and progress/status signal tests.

Covers:
  - Button state transitions (start → success / failure)
  - Progress & status updates via emitted signals
  - No crash on worker failure
  - Worker signal contract (progress_updated, results_ready, run_failed)
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """Shared QApplication for the session."""
    pytest.importorskip("PySide6", reason="PySide6 not installed")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv or ["pytest-qt012"])
    return app


@pytest.fixture
def main_window(qapp):
    """Create and show a main window; close after each test."""
    from app.gui_qt.main_window import SpectralUnmixingMainWindow

    window = SpectralUnmixingMainWindow()
    window._impl.show()
    qapp.processEvents()
    yield window
    window._impl.close()
    qapp.processEvents()


def _pump(qapp, ms: int = 50) -> None:
    """Process events and yield briefly so queued signals are delivered."""
    from PySide6.QtTest import QTest

    QTest.qWait(ms)
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Helper: stub pipeline functions
# ---------------------------------------------------------------------------

def _stub_success() -> Dict[str, Any]:
    """A pipeline that returns non-empty results."""
    return {"concentrations": [[1.0]], "rmse": 0.01}


def _stub_empty_success() -> Dict[str, Any]:
    """A pipeline that returns an empty dict (still success)."""
    return {}


def _stub_failure() -> Dict[str, Any]:
    """A pipeline that raises an exception."""
    raise RuntimeError("simulated pipeline error")


def _stub_with_progress() -> Dict[str, Any]:
    """A pipeline that emits intermediate progress via a sleep."""
    time.sleep(0.05)
    return {"data": True}


# ---------------------------------------------------------------------------
# Worker unit tests (no QApplication needed for signal wiring)
# ---------------------------------------------------------------------------

class TestPipelineWorkerSignals:
    """Verify the worker emits the correct signals."""

    def test_worker_emits_results_ready_on_success(self, qapp):
        from app.gui_qt.worker import PipelineWorker

        captured: list = []
        worker = PipelineWorker(_stub_success)
        worker.results_ready.connect(lambda r: captured.append(r))
        worker.run()

        assert len(captured) == 1
        assert captured[0] == {"concentrations": [[1.0]], "rmse": 0.01}

    def test_worker_emits_run_failed_on_exception(self, qapp):
        from app.gui_qt.worker import PipelineWorker

        captured: list = []
        worker = PipelineWorker(_stub_failure)
        worker.run_failed.connect(lambda e: captured.append(e))
        worker.run()

        assert len(captured) == 1
        assert "simulated pipeline error" in captured[0]

    def test_worker_emits_progress_at_start_and_end(self, qapp):
        from app.gui_qt.worker import PipelineWorker

        progress_events: list = []
        worker = PipelineWorker(_stub_with_progress)
        worker.progress_updated.connect(lambda p, m: progress_events.append((p, m)))
        worker.run()

        # Should have at least start (0%) and end (100%)
        percents = [p for p, _ in progress_events]
        assert 0 in percents
        assert 100 in percents

    def test_progress_updated_signal_signature(self, qapp):
        from app.gui_qt.worker import PipelineWorker

        received: list = []
        worker = PipelineWorker(_stub_success)
        worker.progress_updated.connect(lambda pct, msg: received.append((pct, msg)))
        worker.run()

        # First emission should be (0, "Starting pipeline…")
        assert received[0][0] == 0
        assert "Starting" in received[0][1]

        # Last emission should be (100, "Pipeline complete.")
        assert received[-1][0] == 100
        assert "complete" in received[-1][1]


# ---------------------------------------------------------------------------
# Integration tests: main window state transitions
# ---------------------------------------------------------------------------

class TestButtonStateTransitions:
    """Verify Run/Save button enabled states through the pipeline lifecycle."""

    def test_initial_state_run_and_save_disabled(self, main_window, qapp):
        """At startup both Run and Save are disabled."""
        from PySide6.QtWidgets import QPushButton

        run_btn = main_window._impl.findChild(QPushButton, "run_btn")
        save_btn = main_window._impl.findChild(QPushButton, "save_btn")

        assert not run_btn.isEnabled()
        assert not save_btn.isEnabled()

    def test_run_enabled_after_pipeline_fn_set(self, main_window, qapp):
        """Registering a pipeline function enables the Run button."""
        from PySide6.QtWidgets import QPushButton

        main_window.set_pipeline_fn(_stub_success)
        qapp.processEvents()

        run_btn = main_window._impl.findChild(QPushButton, "run_btn")
        assert run_btn.isEnabled()

    def test_run_disabled_after_pipeline_fn_cleared(self, main_window, qapp):
        """Clearing the pipeline function disables the Run button."""
        from PySide6.QtWidgets import QPushButton

        main_window.set_pipeline_fn(_stub_success)
        qapp.processEvents()
        main_window.set_pipeline_fn(None)
        qapp.processEvents()

        run_btn = main_window._impl.findChild(QPushButton, "run_btn")
        assert not run_btn.isEnabled()

    def test_buttons_during_and_after_success_run(self, main_window, qapp):
        """Run disabled during execution; re-enabled after success;
        Save enabled only when results are non-empty."""
        from PySide6.QtWidgets import QPushButton

        # Use a slow pipeline so we can observe the "during run" state
        main_window.set_pipeline_fn(_stub_with_progress)
        qapp.processEvents()

        # Click Run
        run_btn = main_window._impl.findChild(QPushButton, "run_btn")
        save_btn = main_window._impl.findChild(QPushButton, "save_btn")
        assert run_btn.isEnabled()
        run_btn.click()
        qapp.processEvents()

        # During run: both disabled (give the thread a moment to start)
        _pump(qapp, 10)
        assert not run_btn.isEnabled()
        assert not save_btn.isEnabled()

        # Wait for thread to finish
        if main_window._thread is not None:
            main_window._thread.wait(5000)
        _pump(qapp, 200)

        # After success: Run re-enabled, Save enabled (non-empty results)
        assert run_btn.isEnabled()
        assert save_btn.isEnabled()

    def test_save_not_enabled_on_empty_results(self, main_window, qapp):
        """Save remains disabled when pipeline succeeds but returns empty dict."""
        from PySide6.QtWidgets import QPushButton

        main_window.set_pipeline_fn(_stub_empty_success)
        qapp.processEvents()

        run_btn = main_window._impl.findChild(QPushButton, "run_btn")
        save_btn = main_window._impl.findChild(QPushButton, "save_btn")
        run_btn.click()
        qapp.processEvents()

        if main_window._thread is not None:
            main_window._thread.wait(5000)
        _pump(qapp, 200)

        assert run_btn.isEnabled()
        assert not save_btn.isEnabled()

    def test_buttons_after_failure_run(self, main_window, qapp):
        """After failure: Run re-enabled, Save stays disabled."""
        from PySide6.QtWidgets import QPushButton

        main_window.set_pipeline_fn(_stub_failure)
        qapp.processEvents()

        run_btn = main_window._impl.findChild(QPushButton, "run_btn")
        save_btn = main_window._impl.findChild(QPushButton, "save_btn")
        run_btn.click()
        qapp.processEvents()

        if main_window._thread is not None:
            main_window._thread.wait(5000)
        _pump(qapp, 200)

        assert run_btn.isEnabled()
        assert not save_btn.isEnabled()

    def test_double_click_ignored_while_running(self, main_window, qapp):
        """Clicking Run while already running does not start a second thread."""
        from PySide6.QtWidgets import QPushButton

        # Use a slow pipeline so we have time to double-click
        main_window.set_pipeline_fn(_stub_with_progress)
        qapp.processEvents()

        run_btn = main_window._impl.findChild(QPushButton, "run_btn")
        run_btn.click()
        qapp.processEvents()

        first_thread = main_window._thread
        assert first_thread is not None

        # Second click while running should be a no-op
        run_btn.click()
        qapp.processEvents()

        # _thread should still point to the first thread
        assert main_window._thread is first_thread

        first_thread.wait(5000)
        _pump(qapp, 200)


class TestProgressAndStatusUpdates:
    """Verify progress bar and status label are updated via signals."""

    def test_progress_bar_updated_on_completion(self, main_window, qapp):
        """Progress bar reaches 100 after successful run."""
        from PySide6.QtWidgets import QProgressBar, QPushButton

        main_window.set_pipeline_fn(_stub_success)
        qapp.processEvents()

        run_btn = main_window._impl.findChild(QPushButton, "run_btn")
        run_btn.click()
        qapp.processEvents()

        if main_window._thread is not None:
            main_window._thread.wait(5000)
        _pump(qapp, 200)

        bar = main_window._impl.findChild(QProgressBar, "progress_bar")
        assert bar.value() == 100

    def test_status_label_shows_completion_message(self, main_window, qapp):
        """Status label shows 'Pipeline complete.' after success."""
        from PySide6.QtWidgets import QLabel, QPushButton

        main_window.set_pipeline_fn(_stub_success)
        qapp.processEvents()

        run_btn = main_window._impl.findChild(QPushButton, "run_btn")
        run_btn.click()
        qapp.processEvents()

        if main_window._thread is not None:
            main_window._thread.wait(5000)
        _pump(qapp, 200)

        label = main_window._impl.findChild(QLabel, "status_label")
        assert label.text() == "Pipeline complete."

    def test_status_label_shows_error_on_failure(self, main_window, qapp):
        """Status label contains error text after failure."""
        from PySide6.QtWidgets import QLabel, QPushButton

        main_window.set_pipeline_fn(_stub_failure)
        qapp.processEvents()

        run_btn = main_window._impl.findChild(QPushButton, "run_btn")
        run_btn.click()
        qapp.processEvents()

        if main_window._thread is not None:
            main_window._thread.wait(5000)
        _pump(qapp, 200)

        label = main_window._impl.findChild(QLabel, "status_label")
        text = label.text()
        assert "Pipeline failed" in text
        assert "simulated pipeline error" in text

    def test_progress_reset_to_zero_on_failure(self, main_window, qapp):
        """Progress bar resets to 0 after a failed run."""
        from PySide6.QtWidgets import QProgressBar, QPushButton

        main_window.set_pipeline_fn(_stub_failure)
        qapp.processEvents()

        run_btn = main_window._impl.findChild(QPushButton, "run_btn")
        run_btn.click()
        qapp.processEvents()

        if main_window._thread is not None:
            main_window._thread.wait(5000)
        _pump(qapp, 200)

        bar = main_window._impl.findChild(QProgressBar, "progress_bar")
        assert bar.value() == 0


class TestNoCrashOnWorkerFailure:
    """Verify the application does not crash when the worker raises."""

    def test_worker_exception_does_not_crash_main_window(self, main_window, qapp):
        """Running a failing pipeline should not raise any unhandled exception."""
        main_window.set_pipeline_fn(_stub_failure)
        qapp.processEvents()

        run_btn = main_window._impl.findChild(object, "run_btn")
        # This should not raise
        run_btn.click()
        qapp.processEvents()

        if main_window._thread is not None:
            main_window._thread.wait(5000)
        _pump(qapp, 200)

        # Window should still be alive and visible (fixture closes it in teardown)
        assert main_window._impl is not None
        assert main_window._impl.isVisible()

    def test_multiple_failure_runs_do_not_crash(self, main_window, qapp):
        """Sequential failure runs should each complete cleanly."""
        main_window.set_pipeline_fn(_stub_failure)
        qapp.processEvents()

        run_btn = main_window._impl.findChild(object, "run_btn")

        for _ in range(3):
            run_btn.click()
            qapp.processEvents()
            if main_window._thread is not None:
                main_window._thread.wait(5000)
            _pump(qapp, 200)
            assert run_btn.isEnabled()  # should be re-enabled each time

    def test_results_stored_on_success_accessible(self, main_window, qapp):
        """After success, _last_results holds the returned dict."""
        main_window.set_pipeline_fn(_stub_success)
        qapp.processEvents()

        run_btn = main_window._impl.findChild(object, "run_btn")
        run_btn.click()
        qapp.processEvents()

        if main_window._thread is not None:
            main_window._thread.wait(5000)
        _pump(qapp, 200)

        assert main_window._last_results is not None
        assert "concentrations" in main_window._last_results
        assert main_window._last_results["rmse"] == 0.01

    def test_results_cleared_on_failure(self, main_window, qapp):
        """After failure, _last_results is None."""
        # First, run a success
        main_window.set_pipeline_fn(_stub_success)
        qapp.processEvents()
        run_btn = main_window._impl.findChild(object, "run_btn")
        run_btn.click()
        qapp.processEvents()
        if main_window._thread is not None:
            main_window._thread.wait(5000)
        _pump(qapp, 200)
        assert main_window._last_results is not None

        # Now run a failure
        main_window.set_pipeline_fn(_stub_failure)
        qapp.processEvents()
        run_btn.click()
        qapp.processEvents()
        if main_window._thread is not None:
            main_window._thread.wait(5000)
        _pump(qapp, 200)

        assert main_window._last_results is None
