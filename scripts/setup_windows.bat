@echo off
echo ========================================
echo PDF Extraction Pipeline Setup (Windows)
echo ========================================

echo.
echo [1/4] Creating virtual environment...
python -m venv venv

echo.
echo [2/4] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [3/4] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [4/4] Copying environment template...
if not exist .env (
    copy .env.template .env
    echo Created .env file from template
) else (
    echo .env file already exists
)

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit .env file with your API keys
echo 2. Run: venv\Scripts\activate.bat
echo 3. Test: python extract_cli.py --help
echo.
pause