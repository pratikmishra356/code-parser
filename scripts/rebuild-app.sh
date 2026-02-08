#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
docker-compose build --no-cache app migrate && \
docker-compose stop app && \
docker-compose rm -f app && \
CLAUDE_API_KEY=$(/opt/homebrew/bin/toastApiKeyHelper 2>&1) docker-compose up -d app
