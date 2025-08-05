#!/bin/bash

echo "========================================"
echo "PDF Extraction Pipeline Setup (WSL)"
echo "========================================"

echo
echo "[1/3] Using existing Windows virtual environment..."
echo "Found venv at: venv/Scripts/"

echo
echo "[2/3] Installing dependencies using Windows Python..."
./venv/Scripts/python.exe -m pip install --upgrade pip
./venv/Scripts/python.exe -m pip install -r requirements.txt

echo
echo "[3/3] Setting up environment file..."
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
echo "To run commands from WSL, use:"
echo "  ./venv/Scripts/python.exe [command]"
echo
echo "Examples:"
echo "  ./venv/Scripts/python.exe src/extractors/test_api_keys.py"
echo "  ./venv/Scripts/python.exe extract_cli.py single data/1.pdf --verbose"
echo
echo "Next steps:"
echo "1. Edit .env file with your API keys: nano .env"
echo "2. Test: ./venv/Scripts/python.exe extract_cli.py --help"
echo