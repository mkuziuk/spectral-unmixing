#!/usr/bin/env python3
"""
Spectral Unmixing Application — entry point.

Usage:
    python -m app.main
    # or
    python app/main.py
"""

import sys
import os

# Ensure the project root is on the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.gui.app_window import SpectralUnmixingApp


def main():
    app = SpectralUnmixingApp()
    app.mainloop()


if __name__ == "__main__":
    main()
