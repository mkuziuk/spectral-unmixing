"""Widgets package for the PySide6 GUI.

Import-safe: sub-modules are only imported on demand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from app.gui_qt.widgets.chromophore_menu import ChromophoreMenu

__all__: list[str] = ["ChromophoreMenu"]


def __getattr__(name: str) -> type:
    """Lazy-import widget classes on first access."""
    if name == "ChromophoreMenu":
        import importlib
        mod = importlib.import_module(".chromophore_menu", __name__)
        cls = getattr(mod, name)
        globals()[name] = cls
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
