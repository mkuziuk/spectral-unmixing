#!/bin/bash
# Simple launcher for the Spectral Unmixing Application
# This script ensures we use the correct virtual environment and working directory

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment (.venv) not found in $SCRIPT_DIR"
    exit 1
fi

echo "Starting Spectral Unmixing App..."
./.venv/bin/python app/main.py
