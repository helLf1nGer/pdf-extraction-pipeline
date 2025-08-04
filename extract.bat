@echo off
REM Windows batch script to run extraction with proper encoding
SET PYTHONIOENCODING=utf-8
SET PYTHONLEGACYWINDOWSSTDIO=utf-8
venv\Scripts\python.exe extract_cli.py %*