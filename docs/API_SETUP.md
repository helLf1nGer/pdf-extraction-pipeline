# API Key Setup Guide

This guide will help you obtain and configure the necessary API keys for the PDF extraction pipeline.

## Required API Keys

### 1. LlamaParse API Key (REQUIRED)
- **Purpose**: Convert PDFs to structured markdown
- **Cost**: Free tier available, paid plans for higher volume
- **How to get**:
  1. Visit [LlamaIndex/LlamaParse](https://cloud.llamaindex.ai/)
  2. Sign up for an account
  3. Go to API Keys section
  4. Generate a new API key
  5. Copy the key (starts with `llx-...`)

### 2. Google AI API Key (REQUIRED for Gemini)
- **Purpose**: Gemini 2.5 Pro for medium complexity PDF extraction
- **Cost**: Free tier available with generous limits
- **How to get**:
  1. Visit [Google AI Studio](https://aistudio.google.com/)
  2. Sign in with Google account
  3. Click "Get API key" in the top menu
  4. Create new API key
  5. Copy the key (starts with `AIza...`)

### 3. Anthropic API Key (REQUIRED for Claude)
- **Purpose**: Claude 3.5 Sonnet for complex PDF extraction
- **Cost**: Pay-per-use, $20 minimum credit
- **How to get**:
  1. Visit [Anthropic Console](https://console.anthropic.com/)
  2. Sign up for an account
  3. Add billing information
  4. Go to API Keys section
  5. Create new key
  6. Copy the key (starts with `sk-ant-...`)

### 4. OpenAI API Key (OPTIONAL)
- **Purpose**: Backup model or additional processing
- **Cost**: Pay-per-use
- **How to get**:
  1. Visit [OpenAI Platform](https://platform.openai.com/)
  2. Sign up and verify account
  3. Add billing information
  4. Go to API Keys section
  5. Create new secret key
  6. Copy the key (starts with `sk-...`)

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy the template
cp .env.template .env

# Edit .env with your actual API keys
nano .env  # or use your preferred editor
```

### 3. Environment File Configuration

Edit your `.env` file with the actual API keys:

```env
# API Keys - Replace with your actual keys
LLAMA_PARSE_API_KEY=llx-your-llamaparse-key-here
GOOGLE_API_KEY=AIza-your-google-key-here
GEMINI_API_KEY=AIza-your-google-key-here  # Same as GOOGLE_API_KEY
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
OPENAI_API_KEY=sk-your-openai-key-here  # Optional

# Model Configuration
DEFAULT_MODEL=gemini-2.5-pro
BACKUP_MODEL=claude-3.5-sonnet

# Processing Settings
MAX_PAGES_PER_PDF=50
BATCH_SIZE=5
PARALLEL_PROCESSING=true

# Output Configuration
OUTPUT_FORMAT=json
SAVE_IMAGES=true
IMAGE_QUALITY=high

# Logging
LOG_LEVEL=INFO
LOG_FILE=extraction.log

# Development Settings
DEBUG_MODE=false
VERBOSE_OUTPUT=false
```

### 4. Test API Keys

Run the validation script to test your API keys:

```bash
python src/extractors/test_api_keys.py
```

## Cost Estimates

### Development/Testing (5 PDFs)
- **LlamaParse**: ~$2-5 (depending on PDF complexity)
- **Gemini 2.5 Pro**: ~$1-3 (very generous free tier)
- **Claude 3.5 Sonnet**: ~$3-8 (complex documents)
- **Total**: ~$6-16 for initial testing

### Production Usage (per 100 PDFs)
- **LlamaParse**: ~$40-100
- **Gemini**: ~$10-30
- **Claude**: ~$30-80
- **Total**: ~$80-210 per 100 PDFs

## API Rate Limits

- **LlamaParse**: 10 concurrent requests (free tier)
- **Gemini**: 60 requests/minute (free tier)
- **Claude**: 1000 requests/minute (paid tier)
- **OpenAI**: Varies by tier

## Troubleshooting

### Common Issues

1. **"Invalid API Key" Error**
   - Double-check key format and spelling
   - Ensure no extra spaces or quotes
   - Verify account has billing set up (for paid APIs)

2. **"Rate Limit Exceeded"**
   - Wait a few minutes and retry
   - Reduce batch size in configuration
   - Upgrade to higher tier if needed

3. **"Insufficient Credits"**
   - Add more credits to your account
   - Check billing information

### Mock Mode for Development

If you don't have all API keys yet, you can run in mock mode:

```bash
export MOCK_MODE=true
python src/extractors/pipeline.py --mock
```

This will use sample data for testing the pipeline structure without API calls.

## Security Best Practices

1. **Never commit `.env` file** (it's already in `.gitignore`)
2. **Use environment variables** in production
3. **Rotate keys regularly**
4. **Monitor usage** to detect unusual activity
5. **Set up billing alerts**

## Support

- **LlamaParse**: [Discord](https://discord.gg/llamaindex) or email support
- **Google AI**: [Support Center](https://support.google.com/)
- **Anthropic**: [Help Center](https://support.anthropic.com/)
- **OpenAI**: [Help Center](https://help.openai.com/)