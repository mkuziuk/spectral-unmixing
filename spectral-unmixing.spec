# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Spectral Unmixing App (Windows).

Generated for Windows build via GitHub Actions.
"""

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'app.core.io',
        'app.core.processing',
        'app.core.export',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'app.gui_qt.main_window',
        'app.gui_qt.worker',
        'app.gui_qt.widgets.chromophore_menu',
        'app.gui_qt.mpl.canvas',
        'app.gui_qt.panels.chromophore_barcharts_panel',
        'app.gui_qt.panels.diagnostics_panel',
        'app.gui_qt.panels.inspector_panel',
        'app.gui_qt.panels.maps_panel',
        'app.gui_qt.panels.stats_panel',
        'matplotlib.backends.backend_qtagg',
        'scipy.optimize',
        'scipy.interpolate',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'tkinter.test',
        'matplotlib.tests',
        'numpy.tests',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='spectral-unmixing',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
