"""Panels package for the PySide6 GUI.

Import-safe: sub-modules are only imported on demand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from app.gui_qt.panels.chromophore_barcharts_panel import ChromophoreBarChartsPanel
    from app.gui_qt.panels.maps_panel import MapsPanel
    from app.gui_qt.panels.inspector_panel import InspectorPanel
    from app.gui_qt.panels.diagnostics_panel import DiagnosticsPanel
    from app.gui_qt.panels.stats_panel import StatsPanel

__all__: list[str] = [
    "ChromophoreBarChartsPanel",
    "MapsPanel",
    "InspectorPanel",
    "DiagnosticsPanel",
    "StatsPanel",
]


def __getattr__(name: str) -> type:
    """Lazy-import panel classes on first access."""
    _map = {
        "ChromophoreBarChartsPanel": "chromophore_barcharts_panel",
        "MapsPanel": "maps_panel",
        "InspectorPanel": "inspector_panel",
        "DiagnosticsPanel": "diagnostics_panel",
        "StatsPanel": "stats_panel",
    }
    mod_name = _map.get(name)
    if mod_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    mod = importlib.import_module(f".{mod_name}", __name__)
    cls = getattr(mod, name)
    globals()[name] = cls
    return cls
