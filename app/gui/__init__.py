# =============================================================================
# DEPRECATED: Legacy tkinter GUI package
# =============================================================================
# This package is retained ONLY for the ``--legacy-tk`` rollback path.
# It is NOT used by the default PySide6 UI (app.gui_qt).
#
# Scheduled for removal in a future release. Do not add new features here.
# All new GUI development should target app.gui_qt.
#
# Modules:
#   app_window.py   - Main tkinter application window
#   viz_panel.py    - Chromophore/derived/raw image visualization
#   inspector.py    - Per-pixel spectral inspection
#   diagnostics.py  - RMSE stats, residual histogram, quality mask
#   stats_panel.py  - Reflectance statistics (mean/median per wavelength)
# =============================================================================
import warnings

warnings.warn(
    "app.gui is deprecated and retained only for --legacy-tk rollback. "
    "Use app.gui_qt for the default PySide6 UI.",
    DeprecationWarning,
    stacklevel=2,
)
