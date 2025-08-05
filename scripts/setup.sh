#!/bin/bash

echo "========================================"
echo "PDF Extraction Pipeline Setup (Linux/WSL)"
echo "========================================"

echo
echo "[1/4] Creating virtual environment..."
python3 -m venv venv || python -m venv venv

echo
echo "[2/4] Activating virtual environment..."
source venv/bin/activate

echo
echo "[3/4] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo
echo "[4/4] Setting up environment file..."
if [ ! -f .env ]; then
    cp .env.template .env
    echo "Created .env file from template"
else
    echo ".env file already exists"
fi

echo
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo
echo "Next steps:"
echo "1. Edit .env file with your API keys"
echo "2. Run: source venv/bin/activate"
echo "3. Test: python extract_cli.py --help"
echo