#!/bin/bash
# Convenience script for running Python commands in WSL using Windows venv

PYTHON_EXE="./venv/Scripts/python.exe"

if [ ! -f "$PYTHON_EXE" ]; then
    echo "Error: Virtual environment not found!"
    echo "Please run setup_windows.bat from Windows first."
    exit 1
fi

# Pass all arguments to Python
$PYTHON_EXE "$@"