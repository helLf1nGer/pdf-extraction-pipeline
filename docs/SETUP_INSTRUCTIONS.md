# Setup Instructions - PDF Extraction Pipeline

## 1. Activate Virtual Environment

### Windows (Command Prompt):
```cmd
venv\Scripts\activate
```

### Windows (PowerShell):
```powershell
venv\Scripts\Activate.ps1
```

### Windows (Git Bash):
```bash
source venv/Scripts/activate
```

### WSL/Linux:
```bash
source venv/bin/activate
```

## 2. Install Dependencies

```bash
# After activating venv, install all dependencies
pip install -r requirements.txt
```

## 3. Configure API Keys

```bash
# Copy template to .env
cp .env.template .env

# Edit .env with your API keys
# Use notepad, VS Code, or any text editor
```

Required API Keys:
- `LLAMA_PARSE_API_KEY` - Get from https://cloud.llamaindex.ai/
- `GOOGLE_API_KEY` - Get from https://aistudio.google.com/
- `ANTHROPIC_API_KEY` - Get from https://console.anthropic.com/

## 4. Test Your Setup

```bash
# Test API keys
python src/extractors/test_api_keys.py

# Run a test extraction
python extract_cli.py single data/1.pdf --verbose
```

## 5. Deactivate When Done

```bash
deactivate
```