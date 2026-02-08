# Code Parser

Production-grade code parsing service with AST analysis and call graph generation.

## Features

- **Multi-language parsing**: Python, Java, JavaScript, Rust (using tree-sitter)
- **Symbol extraction**: Functions, classes, methods, imports, and more
- **Call graph generation**: Track upstream (callers) and downstream (callees) for any symbol
- **Incremental parsing**: Hash-based change detection to skip unchanged files
- **Parallel processing**: Multi-worker architecture for fast parsing of large codebases
- **PostgreSQL-backed job queue**: No Redis required, uses SKIP LOCKED for safe concurrency
- **REST API**: Full-featured API for querying symbols and call graphs

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Start the service
docker compose up -d

# Run migrations
docker compose run --rm migrate

# The API is now available at http://localhost:8000
```

### Manual Setup

1. **Install dependencies**:
```bash
pip install -e ".[dev]"
```

2. **Set up PostgreSQL** and configure the connection:
```bash
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/code_parser
```

3. **Run migrations**:
```bash
alembic upgrade head
```

4. **Start the service**:
```bash
python -m code_parser.main
```

## API Usage

### Submit a Repository for Parsing

```bash
curl -X POST http://localhost:8000/api/v1/repos \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/your/codebase"}'
```

### Check Parsing Status

```bash
curl http://localhost:8000/api/v1/repos/{repo_id}
```

### List Symbols

```bash
# All symbols
curl http://localhost:8000/api/v1/repos/{repo_id}/symbols

# Filter by kind
curl http://localhost:8000/api/v1/repos/{repo_id}/symbols?kind=function
```

### Search Symbols

```bash
curl http://localhost:8000/api/v1/repos/{repo_id}/symbols/search?q=process
```

### Get Call Graph

```bash
# What does this function call? (downstream)
curl http://localhost:8000/api/v1/repos/{repo_id}/symbols/{symbol_id}/downstream

# What calls this function? (upstream)
curl http://localhost:8000/api/v1/repos/{repo_id}/symbols/{symbol_id}/upstream

# Full context (both directions)
curl http://localhost:8000/api/v1/repos/{repo_id}/symbols/{symbol_id}/context
```

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql+asyncpg://postgres:postgres@localhost:5432/code_parser` |
| `DEBUG` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `WORKER_COUNT` | Number of background workers | `4` |
| `MAX_FILES_PER_BATCH` | Files to parse per batch | `100` |
| `MAX_FILE_SIZE_BYTES` | Skip files larger than this | `1000000` |

## Architecture

```
┌──────────┐      ┌─────────────────────────────────────┐
│  Client  │─────>│            FastAPI App              │
│          │      │  ┌─────────────┐  ┌──────────────┐  │
└──────────┘      │  │ API Routes  │  │ Worker Pool  │  │
                  │  │             │  │ (asyncio)    │  │
                  │  └──────┬──────┘  └───────┬──────┘  │
                  │         │                 │         │
                  └─────────┼─────────────────┼─────────┘
                            │                 │
                            ▼                 ▼
                  ┌─────────────────────────────────────┐
                  │           PostgreSQL                │
                  │  ┌────────────┐  ┌───────────────┐  │
                  │  │   Data     │  │  Jobs Queue   │  │
                  │  │  (repos,   │  │  (SKIP LOCKED)│  │
                  │  │  symbols)  │  │               │  │
                  │  └────────────┘  └───────────────┘  │
                  └─────────────────────────────────────┘
```

## Project Structure

```
code-parser/
├── src/code_parser/
│   ├── api/              # REST API (FastAPI)
│   ├── core/             # Domain models
│   ├── database/         # SQLAlchemy models & connection
│   ├── parsers/          # Language parsers (tree-sitter)
│   ├── repositories/     # Data access layer
│   ├── services/         # Business logic
│   └── workers/          # Background job processing
├── alembic/              # Database migrations
├── tests/                # Test suite
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
ruff format src/
```

## License

MIT

