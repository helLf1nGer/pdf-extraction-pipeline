# Installation Guide - PDF Extraction Pipeline

## Prerequisites
- Python 3.8 or higher
- pip package manager
- Windows, Linux, or WSL environment

## Quick Setup

### Windows Users
```batch
# Run the setup script
setup_windows.bat

# Activate the virtual environment
venv\Scripts\activate.bat

# Add your API keys
notepad .env
```

### Linux/WSL Users
```bash
# Run the setup script
./setup.sh

# Activate the virtual environment
source venv/bin/activate

# Add your API keys
nano .env
```

## Manual Setup

### 1. Create Virtual Environment
```bash
# Windows
python -m venv venv

# Linux/WSL
python3 -m venv venv
```

### 2. Activate Virtual Environment
```bash
# Windows
venv\Scripts\activate.bat

# Linux/WSL
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
# Copy template
cp .env.template .env

# Edit with your API keys
# See API_SETUP.md for detailed instructions
```

## Verify Installation

### Test API Keys
```bash
python src/extractors/test_api_keys.py
```

### Test Pipeline (Mock Mode)
```bash
python extract_cli.py single data/1.pdf --mock --verbose
```

## Troubleshooting

### "pip: command not found"
- Make sure virtual environment is activated
- Try: `python -m pip install -r requirements.txt`

### "Module not found" errors
- Ensure you're in the virtual environment
- Reinstall: `pip install -r requirements.txt --force-reinstall`

### Permission errors on Windows
- Run Command Prompt as Administrator
- Or use: `python -m pip install --user -r requirements.txt`

## Next Steps
1. Get API keys (see API_SETUP.md)
2. Configure .env file
3. Run test extraction
4. Check outputs/ folder for results