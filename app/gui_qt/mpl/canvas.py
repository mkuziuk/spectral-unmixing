"""Reusable matplotlib Qt canvas and toolbar helpers.

Import-safe: neither PySide6 nor matplotlib is imported at module load
time.  ImportError is raised only when a class is instantiated and the
required dependency is unavailable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    # Type-level references only — never executed at runtime on import.
    from matplotlib.figure import Figure


# ---------------------------------------------------------------------------
# MplCanvas
# ---------------------------------------------------------------------------

OBJECT_NAME_CANVAS: str = "MplCanvas"


class MplCanvas:
    """Reusable matplotlib FigureCanvas for PySide6 applications.

    Wraps a matplotlib Figure and exposes a Qt widget via ``_impl``.
    """

    def __init__(self, parent: Any = None, **figure_kwargs: Any) -> None:
        factory = _make_canvas()
        self._impl = factory(parent, **figure_kwargs)
        self._impl.setObjectName(OBJECT_NAME_CANVAS)
        self._setup_ui()

    # -- public interface (stubs) -------------------------------------------

    @property
    def figure(self) -> Any:
        """Return the underlying matplotlib Figure."""
        return self._impl.figure

    def plot(self, *args: Any, **kwargs: Any) -> None:
        """Plot data on the canvas (convenience wrapper)."""
        ...

    def draw(self) -> None:
        """Trigger a redraw of the canvas."""
        ...

    # -- internal -----------------------------------------------------------

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        ...


# ---------------------------------------------------------------------------
# MplToolbar
# ---------------------------------------------------------------------------

OBJECT_NAME_TOOLBAR: str = "MplToolbar"


class MplToolbar:
    """Reusable matplotlib NavigationToolbar2 for PySide6 applications."""

    def __init__(self, canvas: MplCanvas, parent: Any = None) -> None:
        factory = _make_toolbar()
        self._impl = factory(canvas._impl, parent)
        self._impl.setObjectName(OBJECT_NAME_TOOLBAR)

    # -- internal -----------------------------------------------------------

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        ...


# ---------------------------------------------------------------------------
# Lazy factories
# ---------------------------------------------------------------------------

def _make_canvas() -> type:
    """Return a FigureCanvasQTAgg subclass."""
    try:
        from PySide6.QtWidgets import QWidget  # noqa: F401 — availability check
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PySide6 is required to instantiate MplCanvas"
        ) from exc
    try:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "matplotlib is required to instantiate MplCanvas"
        ) from exc

    class _Canvas(FigureCanvasQTAgg):
        def __init__(self, parent: Any = None, **figure_kwargs: Any) -> None:
            figure = Figure(**figure_kwargs)
            super().__init__(figure)
            self.setParent(parent)

    return _Canvas


def _make_toolbar() -> type:
    """Return a NavigationToolbar2QT class."""
    try:
        from PySide6.QtWidgets import QWidget  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PySide6 is required to instantiate MplToolbar"
        ) from exc
    try:
        from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "matplotlib is required to instantiate MplToolbar"
        ) from exc

    return NavigationToolbar2QT
