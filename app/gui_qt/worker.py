"""Background pipeline worker for the Qt GUI.

Provides a ``QObject``-based worker that runs the spectral-unmixing pipeline
on a ``QThread`` and emits typed signals for progress, results, and failure.

Design contract
---------------
* **No widget mutation** inside this module — all UI updates happen via
  signals/slots on the main (GUI) thread.
* The worker is deliberately decoupled from ``SpectralUnmixingMainWindow`` so
  that it can be unit-tested in isolation (no QApplication required for the
  signal-emission logic).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import QObject, Signal


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

class PipelineWorkerSignals(QObject):
    """Signal container so that ``PipelineWorker`` can be a plain callable."""

    progress_updated = Signal(int, str)   # (percent, message)
    results_ready = Signal(dict)           # results payload
    run_failed = Signal(str)               # error text


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class PipelineWorker(QObject):
    """Runs the unmixing pipeline on a background thread.

    Parameters
    ----------
    pipeline_fn : callable
        A zero-argument callable that performs the pipeline and returns a
        ``dict`` of results.  May be a stub during early development.
    progress_callback : callable, optional
        If provided, called with ``(percent: int, message: str)`` during
        execution.  The worker *also* emits ``progress_updated`` internally,
        but this hook lets the caller inject intermediate steps from the
        pipeline itself.
    """

    def __init__(
        self,
        pipeline_fn: Callable[[], Dict[str, Any]],
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        super().__init__()
        self._signals = PipelineWorkerSignals()
        self._pipeline_fn = pipeline_fn
        self._progress_callback = progress_callback

    # -- public signal accessors (read-only) --------------------------------

    @property
    def progress_updated(self):  # -> Signal
        """Proxy to ``progress_updated(percent, message)``."""
        return self._signals.progress_updated

    @property
    def results_ready(self):  # -> Signal
        """Proxy to ``results_ready(results_dict)``."""
        return self._signals.results_ready

    @property
    def run_failed(self):  # -> Signal
        """Proxy to ``run_failed(error_text)``."""
        return self._signals.run_failed

    # -- internal helpers ---------------------------------------------------

    def _emit_progress(self, percent: int, message: str) -> None:
        """Emit progress and optionally call the injected callback."""
        self._signals.progress_updated.emit(percent, message)
        if self._progress_callback is not None:
            self._progress_callback(percent, message)

    # -- public API ---------------------------------------------------------

    def run(self) -> None:
        """Execute the pipeline on the calling thread.

        This method is intended to be invoked via ``QMetaObject.invokeMethod``
        or ``functools.partial`` from a ``QThread.started`` connection.  All
        signal emissions happen on the thread that calls ``run()``; Qt's
        queued-connection mechanism routes them to the GUI thread
        automatically.
        """
        try:
            self._emit_progress(0, "Starting pipeline…")

            results = self._pipeline_fn()

            self._emit_progress(100, "Pipeline complete.")
            self._signals.results_ready.emit(results)

        except Exception as exc:  # pragma: no cover — exercised in tests
            error_text = f"Pipeline failed: {exc}"
            self._signals.run_failed.emit(error_text)
