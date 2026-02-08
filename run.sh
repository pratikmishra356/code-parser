#!/bin/bash
# Run script for code-parser service with uvicorn

set -e

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Get API key from toastApiKeyHelper if not already set
if [ -z "$CLAUDE_API_KEY" ] && [ -f "/opt/homebrew/bin/toastApiKeyHelper" ]; then
    echo "Getting API key from toastApiKeyHelper..."
    export CLAUDE_API_KEY=$(/opt/homebrew/bin/toastApiKeyHelper 2>&1)
    if [ -z "$CLAUDE_API_KEY" ]; then
        echo "Warning: Failed to get API key from toastApiKeyHelper"
    fi
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Warning: Virtual environment not activated. Activating..."
    if [ -d "venv" ]; then
        source venv/bin/activate
    elif [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        echo "Error: No virtual environment found. Please create one first:"
        echo "  python3 -m venv venv"
        echo "  source venv/bin/activate"
        echo "  pip install -e ."
        exit 1
    fi
fi

# Run with uvicorn
echo "Starting code-parser service..."
echo "Database URL: $DATABASE_URL"
echo "AI Provider: $AI_PROVIDER"
echo "Log Level: $LOG_LEVEL"
echo ""

python -m uvicorn code_parser.api.app:create_app \
    --factory \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level "${LOG_LEVEL,,}" \
    "$@"
