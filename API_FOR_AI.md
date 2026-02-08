# Code Parser API - Guide for AI Agents

This service provides a multi-tenant code parsing and exploration API designed for AI agents to discover and analyze codebases. It extracts symbols, entry points, call graphs, and flow documentation from parsed repositories.

## Base URL

```
http://localhost:8000/api/v1
```

## Multi-Tenancy Model

All resources are organized under **organizations**:
- Each organization (`org`) contains multiple repositories
- All repository operations are scoped to an organization
- Use organization IDs to access repositories and their contents

## Core Concepts

- **Organization**: Top-level tenant container
- **Repository**: A parsed codebase (Python, Java, Kotlin, JavaScript, Rust)
- **Entry Point**: External triggers (HTTP endpoints, event handlers, schedulers) detected via AI
- **Flow**: Documentation of execution flow for an entry point
- **File**: Parsed source file with content and metadata
- **Symbol**: Functions, classes, methods extracted from code

## Quick Start Workflow

1. **List organizations** → Get `org_id`
2. **List repositories** for org → Get `repo_id`
3. **List entry points** for repo → Discover HTTP endpoints, event handlers, schedulers
4. **Get flows** for entry points → Understand execution paths
5. **List/search files** → Find specific code files
6. **Get file details** → Read file content

## Explore APIs (Recommended for AI Agents)

All explore endpoints are under `/orgs/{org_id}/repos` and support regex search.

### 1. List Repositories

```
GET /orgs/{org_id}/repos?search=<regex>&limit=100&offset=0
```

**Response**: List of repositories with `id`, `name`, `description`, `status`, `languages`, `total_files`

**Search**: Regex pattern matching repo `name` or `description` (case-insensitive)

**Example**:
```bash
# Find payment-related repos
GET /orgs/01JKDEFAULTORG000000000000/repos?search=payment

# Find repos with "api" in name
GET /orgs/01JKDEFAULTORG000000000000/repos?search=^api-
```

### 2. List Entry Points

```
GET /orgs/{org_id}/repos/{repo_id}/entry-points?search=<regex>&limit=100&offset=0
```

**Response**: List of entry points with:
- `id`, `name`, `description`
- `entry_point_type`: `HTTP`, `EVENT`, or `SCHEDULER`
- `framework`: `spring-boot`, `flask`, `kafka`, etc.
- `metadata`: Path, HTTP method, topic, schedule (if applicable)
- `ai_confidence`: 0.0-1.0 confidence score

**Search**: Regex pattern matching entry point `name` or `description`

**Example**:
```bash
# Find payment-related endpoints
GET /orgs/{org_id}/repos/{repo_id}/entry-points?search=payment

# Find GET or POST endpoints
GET /orgs/{org_id}/repos/{repo_id}/entry-points?search=GET|POST

# Find Kafka consumers
GET /orgs/{org_id}/repos/{repo_id}/entry-points?search=kafka.*consumer
```

### 3. Get Flows for Entry Points

```
POST /orgs/{org_id}/repos/{repo_id}/flows
Body: { "entry_point_ids": ["ep1", "ep2", ...] }
```

**Response**: List of flow documentation with:
- `flow_name`: Human-readable flow name
- `technical_summary`: High-level description
- `file_paths`: All files involved in the flow
- `steps`: Detailed step-by-step execution with:
  - `step_number`, `title`, `description`
  - `important_code_snippets`: Code blocks with file paths and line ranges
  - `important_log_lines`: Relevant log statements

**Use Case**: Understand how an entry point executes, what code it calls, and what files are involved.

**Example**:
```bash
POST /orgs/{org_id}/repos/{repo_id}/flows
{
  "entry_point_ids": ["01ABC...", "01DEF..."]
}
```

### 4. List Files

```
GET /orgs/{org_id}/repos/{repo_id}/files?search=<regex>&limit=100&offset=0
```

**Response**: List of files with `id`, `relative_path`, `language`, `content_hash`

**Search**: Regex pattern matching file `relative_path`

**Example**:
```bash
# Find all Python files
GET /orgs/{org_id}/repos/{repo_id}/files?search=\.py$

# Find controller files
GET /orgs/{org_id}/repos/{repo_id}/files?search=controller|handler

# Find service files in src/main
GET /orgs/{org_id}/repos/{repo_id}/files?search=src/main/.*Service
```

### 5. Get File Detail

```
GET /orgs/{org_id}/repos/{repo_id}/files/{file_id}
```

**Response**: Full file details including:
- `content`: Complete file source code
- `relative_path`, `language`, `content_hash`
- `folder_structure`: Directory tree structure

**Use Case**: Read actual source code of a file identified from flows or entry points.

## Organization Management APIs

### List Organizations
```
GET /orgs
```

### Get Organization
```
GET /orgs/{org_id}
```

### Create Organization
```
POST /orgs
Body: { "name": "my-org", "description": "..." }
```

## Entry Point Types

- **HTTP**: REST endpoints, GraphQL resolvers, web handlers
  - Frameworks: `spring-boot`, `flask`, `fastapi`, `django`, `ktor`, `jax-rs`
  - Metadata includes: `path`, `method` (GET, POST, etc.)

- **EVENT**: Message consumers, event handlers
  - Frameworks: `kafka`, `pulsar`, `apache-camel`, `rabbitmq`
  - Metadata includes: `topic`, `queue`, event source

- **SCHEDULER**: Cron jobs, periodic tasks
  - Frameworks: `scheduler`, `quartz`, `celery`
  - Metadata includes: `schedule`, cron expression

## Typical AI Agent Workflow

### Scenario: Understand a payment processing system

```python
# 1. Find the organization
orgs = GET /orgs
org_id = find_org_by_name(orgs, "payment-services")

# 2. Find payment-related repositories
repos = GET /orgs/{org_id}/repos?search=payment
repo_id = repos[0].id

# 3. Discover entry points
entry_points = GET /orgs/{org_id}/repos/{repo_id}/entry-points?search=payment
payment_endpoints = [ep for ep in entry_points if ep.entry_point_type == "HTTP"]

# 4. Understand execution flows
flow_ids = [ep.id for ep in payment_endpoints[:5]]  # Top 5
flows = POST /orgs/{org_id}/repos/{repo_id}/flows
         Body: {"entry_point_ids": flow_ids}

# 5. Read specific files mentioned in flows
for flow in flows:
    for file_path in flow.file_paths:
        # Find file by path
        files = GET /orgs/{org_id}/repos/{repo_id}/files?search={file_path}
        if files:
            file_detail = GET /orgs/{org_id}/repos/{repo_id}/files/{files[0].id}
            # Analyze file_detail.content
```

## Response Formats

All responses are JSON. Error responses:
```json
{
  "detail": "Error message"
}
```

## Regex Search Tips

- Case-insensitive matching by default
- Use `^` for start, `$` for end
- Use `|` for OR patterns: `payment|transaction`
- Escape special chars: `\.py$` for `.py` extension
- Use `.*` for wildcard: `.*Service` matches any Service class

## Rate Limits & Best Practices

- Use `limit` and `offset` for pagination (default limit: 100, max: 1000)
- Cache organization and repository IDs
- Use specific searches to reduce response sizes
- Request flows only for entry points you need to understand
- File content can be large; request only when needed

## Authentication

Currently no authentication required for local development. In production, add API keys or OAuth tokens to headers.

## Example: Complete Exploration

```bash
# 1. Get default organization
curl http://localhost:8000/api/v1/orgs | jq '.[0].id'
# → "01JKDEFAULTORG000000000000"

# 2. List repos
curl "http://localhost:8000/api/v1/orgs/01JKDEFAULTORG000000000000/repos" | jq '.[0]'

# 3. Get entry points
curl "http://localhost:8000/api/v1/orgs/01JKDEFAULTORG000000000000/repos/{repo_id}/entry-points" | jq

# 4. Get flows
curl -X POST "http://localhost:8000/api/v1/orgs/01JKDEFAULTORG000000000000/repos/{repo_id}/flows" \
  -H "Content-Type: application/json" \
  -d '{"entry_point_ids": ["ep1", "ep2"]}' | jq

# 5. Search files
curl "http://localhost:8000/api/v1/orgs/01JKDEFAULTORG000000000000/repos/{repo_id}/files?search=controller" | jq

# 6. Get file content
curl "http://localhost:8000/api/v1/orgs/01JKDEFAULTORG000000000000/repos/{repo_id}/files/{file_id}" | jq '.content'
```

## Summary

This API enables AI agents to:
- **Discover** repositories and entry points via regex search
- **Understand** execution flows for entry points
- **Navigate** codebases by searching and reading files
- **Analyze** multi-tenant codebases organized by organizations

All operations are scoped to organizations for multi-tenancy, and regex search enables flexible discovery patterns.
