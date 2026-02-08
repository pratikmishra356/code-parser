# Running the Code Parser Service

## Quick Start

### Option 1: Using the run script (Recommended)

```bash
./run.sh
```

This script will:
- Load environment variables from `.env`
- Get API key from `toastApiKeyHelper` automatically
- Activate virtual environment if needed
- Start the service with uvicorn

### Option 2: Manual uvicorn command

Set environment variables and run:

```bash
# Export environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/code_parser"
export AI_PROVIDER="claude"
export CLAUDE_API_KEY=$(/opt/homebrew/bin/toastApiKeyHelper 2>&1)
export LOG_LEVEL="INFO"

# Run with uvicorn
uvicorn code_parser.api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

### Option 3: Using Python module

```bash
# Set environment variables (same as Option 2)
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/code_parser"
export AI_PROVIDER="claude"
export CLAUDE_API_KEY=$(/opt/homebrew/bin/toastApiKeyHelper 2>&1)

# Run using Python module
python -m code_parser.main
```

## Environment Variables

The service reads from `.env` file or environment variables:

- `DATABASE_URL` - PostgreSQL connection string (default: `postgresql+asyncpg://postgres:postgres@localhost:5432/code_parser`)
- `AI_PROVIDER` - AI provider: `claude` or `openai` (default: `claude`)
- `CLAUDE_API_KEY` - Claude API key (auto-fetched from `toastApiKeyHelper` if not set)
- `CLAUDE_API_KEY_HELPER_PATH` - Path to toastApiKeyHelper (default: `/opt/homebrew/bin/toastApiKeyHelper`)
- `LOG_LEVEL` - Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`)
- `DEBUG` - Enable debug mode (default: `false`)
- `WORKER_COUNT` - Number of background workers (default: `4`)

## Notes

- The service will automatically get the API key from `toastApiKeyHelper` if `CLAUDE_API_KEY` is not set
- Make sure PostgreSQL is running and accessible at the configured `DATABASE_URL`
- The service runs on `http://localhost:8000` by default
- API docs available at `http://localhost:8000/docs`
