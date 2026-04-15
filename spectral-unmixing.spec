# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Spectral Unmixing App (Windows).

Generated for Windows build via GitHub Actions.
"""

import os
import sys

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'app.core.io',
        'app.core.processing',
        'app.core.export',
        'app.gui.app_window',
        'app.gui.viz_panel',
        'app.gui.inspector',
        'app.gui.diagnostics',
        'app.gui.stats_panel',
        'matplotlib.backends.backend_tkagg',
        'scipy.optimize',
        'scipy.interpolate',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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
