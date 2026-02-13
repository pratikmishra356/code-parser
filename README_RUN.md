# Running the Code Parser Service

## Quick Start

### Option 1: Using the run script (Recommended)

```bash
./run.sh
```

This script will:
- Load environment variables from `.env`
- Activate virtual environment if needed
- Start the service with uvicorn

### Option 2: Manual uvicorn command

Set environment variables and run:

```bash
# Export environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/code_parser"
export CLAUDE_API_KEY="your-api-key"
export CLAUDE_BEDROCK_URL="https://your-bedrock-proxy.example.com"
export CLAUDE_MODEL_ID="anthropic.claude-sonnet-4-20250514-v1:0"
export LOG_LEVEL="INFO"

# Run with uvicorn
uvicorn code_parser.api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

### Option 3: Using Python module

```bash
# Set environment variables (same as Option 2)
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/code_parser"
export CLAUDE_API_KEY="your-api-key"

# Run using Python module
python -m code_parser.main
```

## Environment Variables

The service reads from `.env` file or environment variables:

- `DATABASE_URL` - PostgreSQL connection string (default: `postgresql+asyncpg://postgres:postgres@localhost:5432/code_parser`)
- `CLAUDE_API_KEY` - Claude API key (set via env var or CodeCircle AI Settings)
- `CLAUDE_BEDROCK_URL` - Bedrock proxy URL (set via env var or CodeCircle AI Settings)
- `CLAUDE_MODEL_ID` - Claude model ID (set via env var or CodeCircle AI Settings)
- `LOG_LEVEL` - Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`)
- `DEBUG` - Enable debug mode (default: `false`)
- `WORKER_COUNT` - Number of background workers (default: `4`)

## Notes

- AI configuration can be managed centrally via CodeCircle AI Settings, which pushes config to connected organizations
- Make sure PostgreSQL is running and accessible at the configured `DATABASE_URL`
- The service runs on `http://localhost:8000` by default
- API docs available at `http://localhost:8000/docs`
