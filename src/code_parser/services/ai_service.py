"""AI service for confirming entry points using Claude Bedrock."""

import json
from typing import Any, Callable, Awaitable

import httpx

from code_parser.config import get_settings
from code_parser.core import ConfirmedEntryPoint, EntryPointCandidate, EntryPointType
from code_parser.logging import get_logger

logger = get_logger(__name__)


class AIService:
    """Service for AI-powered entry point confirmation."""

    def __init__(self, ai_config: dict | None = None) -> None:
        self._settings = get_settings()
        self._ai_config = ai_config or {}  # org-level overrides from DB
        self._min_confidence = 0.7  # Minimum confidence threshold

    async def confirm_entry_points(
        self,
        candidates: list[EntryPointCandidate],
        repo_context: dict[str, Any],
        symbol_contexts: dict[str, dict[str, Any]] | None = None,
        batch_size: int = 10,
        on_batch_confirmed: Callable[[list[ConfirmedEntryPoint], int], Awaitable[None]] | None = None,
    ) -> list[ConfirmedEntryPoint]:
        """
        Confirm entry points using AI in batches.
        
        Args:
            candidates: List of entry point candidates to confirm
            repo_context: Repository context (languages, frameworks, etc.)
            symbol_contexts: Pre-built symbol contexts
            batch_size: Number of candidates to process per batch (default: 10)
            on_batch_confirmed: Callback function called after each batch with (confirmed_list, batch_index)
            
        Returns:
            List of all confirmed entry points
        """
        if not candidates:
            return []

        # Batch candidates by type for better context
        candidates_by_type: dict[EntryPointType, list[EntryPointCandidate]] = {}
        for candidate in candidates:
            if candidate.entry_point_type not in candidates_by_type:
                candidates_by_type[candidate.entry_point_type] = []
            candidates_by_type[candidate.entry_point_type].append(candidate)

        all_confirmed: list[ConfirmedEntryPoint] = []

        # Build symbol contexts for all candidates
        symbol_contexts = symbol_contexts or {}

        # Process each type separately, then batch within each type
        for entry_point_type, type_candidates in candidates_by_type.items():
            try:
                # Process in batches of batch_size
                for batch_start in range(0, len(type_candidates), batch_size):
                    batch_candidates = type_candidates[batch_start:batch_start + batch_size]
                    batch_index = batch_start // batch_size
                    
                    logger.info(
                        "processing_ai_batch",
                        entry_point_type=entry_point_type.value,
                        batch_index=batch_index,
                        batch_size=len(batch_candidates),
                        total_candidates=len(type_candidates),
                    )
                    
                    # Filter symbol contexts for this batch
                    batch_contexts = {
                        c.symbol_id: symbol_contexts.get(c.symbol_id, {})
                        for c in batch_candidates
                    }
                    
                    batch_confirmed = await self._confirm_batch(
                        batch_candidates, entry_point_type, repo_context, batch_contexts
                    )
                    
                    all_confirmed.extend(batch_confirmed)
                    
                    # Call callback if provided (for storing after each batch)
                    if on_batch_confirmed and batch_confirmed:
                        await on_batch_confirmed(batch_confirmed, batch_index)
                    
                    logger.info(
                        "ai_batch_complete",
                        entry_point_type=entry_point_type.value,
                        batch_index=batch_index,
                        confirmed_count=len(batch_confirmed),
                        batch_size=len(batch_candidates),
                    )
                    
                    logger.debug(
                        "ai_batch_detailed",
                        entry_point_type=entry_point_type.value,
                        batch_index=batch_index,
                        confirmed_entry_points=[
                            {"name": ep.name, "type": ep.entry_point_type.value, "file_id": ep.file_id}
                            for ep in batch_confirmed
                        ],
                    )
            except Exception as e:
                logger.error(
                    "ai_confirmation_error",
                    entry_point_type=entry_point_type.value,
                    error=str(e),
                    candidate_count=len(type_candidates),
                )

        return all_confirmed

    async def _confirm_batch(
        self,
        candidates: list[EntryPointCandidate],
        entry_point_type: EntryPointType,
        repo_context: dict[str, Any],
        symbol_contexts: dict[str, dict[str, Any]] | None = None,
    ) -> list[ConfirmedEntryPoint]:
        """Confirm a batch of candidates of the same type."""
        # Build prompt with candidate information
        prompt = self._build_confirmation_prompt(
            candidates, entry_point_type, repo_context, symbol_contexts
        )

        # Call Claude Bedrock API
        response = await self._call_claude_bedrock(prompt)

        # Parse response
        confirmed = self._parse_ai_response(response, candidates, entry_point_type)

        # Filter by minimum confidence
        return [
            ep for ep in confirmed if ep.ai_confidence >= self._min_confidence
        ]

    def _build_confirmation_prompt(
        self,
        candidates: list[EntryPointCandidate],
        entry_point_type: EntryPointType,
        repo_context: dict[str, Any],
        symbol_contexts: dict[str, dict[str, Any]] | None = None,
    ) -> str:
        """Build the AI prompt for confirmation."""
        # Build candidate descriptions with full file content
        candidate_descriptions = []
        for i, candidate in enumerate(candidates):
            symbol_info = ""
            if symbol_contexts and candidate.symbol_id in symbol_contexts:
                ctx = symbol_contexts[candidate.symbol_id]
                file_path = ctx.get('file_path', 'unknown')
                file_content = ctx.get('file_content', '')
                symbol_code = ctx.get('source_code', '')
                language = ctx.get('language', 'python')
                
                symbol_info = f"""
- File Path: {file_path}
- Symbol Name: {ctx.get('name', 'unknown')}
- Qualified Name: {ctx.get('qualified_name', 'unknown')}
- Signature: {ctx.get('signature', 'N/A')}
- Symbol Source Code:
```{language}
{symbol_code}
```

- Full File Content:
```{language}
{file_content}
```
"""
            
            candidate_descriptions.append(
                f"""
Candidate {i}:
- Symbol ID: {candidate.symbol_id}
- Framework: {candidate.framework}
- Detection Pattern: {candidate.detection_pattern}
- Metadata: {json.dumps(candidate.metadata, indent=2)}
- Confidence Score: {candidate.confidence_score}
{symbol_info}
"""
            )

        # Build generic type guidance (completely framework-agnostic)
        type_descriptions = {
            "HTTP": "Code that accepts HTTP requests from external clients. Must have URL/route definition and request handling logic.",
            "EVENT": "Code that consumes messages/events from external systems (queues, streams). Must have consumer/subscriber configuration and message processing.",
            "SCHEDULER": "Code that runs on a schedule (cron, timer, periodic). Must have schedule definition and task execution logic."
        }
        
        type_description = type_descriptions.get(entry_point_type.value.upper(), "Code that can be invoked from outside the application")

        prompt = f"""You are analyzing code to identify real entry points - code that can be invoked from outside the application.

For each candidate below, analyze the FULL FILE CONTENT and determine:

1. Is this a real entry point? (true/false)
   Entry points are: {type_description}
   Entry points are NOT: internal functions, helper methods, test code, setup/configuration code, base/abstract classes, dependency injection setup, framework registration/setup code that registers classes but doesn't directly handle external triggers

2. What is a human-readable name for this entry point?
   Use the file path, class/function names, and code structure to create a descriptive name

3. Generate a 1-2 line description of what this entry point does
   Describe what triggers it and what it accomplishes

4. Confidence (0-1) - how confident are you this is a real entry point?

5. Reasoning - why you confirmed/rejected it
   Be specific about what in the code indicates it's an entry point or not

Entry Point Type: {entry_point_type.value.upper()}

Analysis Guidelines (apply to ALL languages and frameworks):
- Read the FULL FILE CONTENT to understand the complete context
- Check file path patterns:
  * Test files (*Test.*, *test.*, *spec.*, *Spec.*) → Usually NOT entry points
  * Setup/config files (*Module.*, *Config.*, *Setup.*) → Usually NOT entry points
  * Base/abstract classes (*Base.*, *Abstract.*) → Usually NOT entry points
- Look for actual external connections:
  * HTTP: Listeners, servers, route definitions with external URLs
  * EVENT: Consumer/subscriber configurations, message queue connections
  * SCHEDULER: Schedule definitions (cron, intervals, timers)
- Reject if:
  * It's a base/abstract class (no concrete implementation)
  * It's dependency injection setup (binding, configuration)
  * It's framework setup/registration code that registers classes but doesn't directly handle external triggers
  * It's a class that is registered but doesn't directly handle external requests/events/schedules - only individual methods/functions within classes that directly handle external triggers are entry points
  * It's internal routing only (no external connection)
  * It's test code
  * It has no actual external trigger mechanism
- Confirm if:
  * It's a method/function that directly handles external triggers (HTTP requests, events, schedules)
  * It has clear external trigger mechanism
  * It's a concrete implementation (not abstract/base)
  * It's in production code (not test/setup)
  * It's not just framework setup/registration code - it must directly respond to external triggers

Repository Context:
- Languages: {repo_context.get('languages', [])}
- Frameworks detected: {repo_context.get('frameworks', [])}

Candidates:
{''.join(candidate_descriptions)}

Return your response as JSON in this exact format:
{{
  "confirmed": [
    {{
      "candidate_index": 0,
      "is_entry_point": true,
      "name": "Payment Processing Endpoint",
      "description": "HTTP endpoint that processes payment requests",
      "confidence": 0.95,
      "reasoning": "This code defines an HTTP route with POST method and payment processing logic..."
    }}
  ],
  "rejected": [
    {{
      "candidate_index": 1,
      "is_entry_point": false,
      "reasoning": "This is a base class/abstract class, not an actual entry point implementation..."
    }}
  ]
}}

Only include candidates that are real entry points in the "confirmed" array. Analyze the actual code structure and file content, not just the detection pattern name.
"""

        return prompt

    async def _call_claude_bedrock(self, prompt: str, max_tokens: int = 4096) -> dict[str, Any]:
        """Call Claude Bedrock API via Toast's proxy."""
        # Get API key (org override > env var > helper)
        api_key = await self._get_api_key()

        # Use org-level overrides if available, fall back to settings
        bedrock_url = self._ai_config.get("claude_bedrock_url") or self._settings.claude_bedrock_url
        model_id = self._ai_config.get("claude_model_id") or self._settings.claude_model_id

        # Prepare request - using Toast's Bedrock proxy format
        url = f"{bedrock_url}/bedrock/model/{model_id}/invoke"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        # Make request
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                response = getattr(e, "response", None)
                status_code = getattr(response, "status_code", None) if response else None
                logger.error("claude_api_error", error=str(e), status_code=status_code)
                raise

    async def _get_api_key(self) -> str:
        """Get Claude API key from org config or environment variable."""
        # Priority 1: Org-level override (pushed from CodeCircle platform)
        org_key = self._ai_config.get("claude_api_key")
        if org_key and org_key.strip():
            logger.debug("api_key_source", source="org_ai_config")
            return org_key.strip()

        # Priority 2: Environment variable (CLAUDE_API_KEY)
        if self._settings.claude_api_key:
            api_key = self._settings.claude_api_key.strip()
            if api_key:
                logger.debug("api_key_source", source="environment_variable")
                return api_key

        raise ValueError(
            "Could not obtain Claude API key. Tried:\n"
            "1. Organization-level AI config (pushed from CodeCircle)\n"
            "2. CLAUDE_API_KEY environment variable\n\n"
            "Configure AI settings in the CodeCircle dashboard (Settings > AI Configuration) "
            "or set the CLAUDE_API_KEY environment variable."
        )

    def _parse_ai_response(
        self,
        response: dict[str, Any],
        candidates: list[EntryPointCandidate],
        entry_point_type: EntryPointType,
    ) -> list[ConfirmedEntryPoint]:
        """Parse AI response and build ConfirmedEntryPoint objects."""
        confirmed: list[ConfirmedEntryPoint] = []

        # Extract content from response (Bedrock format)
        content = ""
        if "content" in response:
            if isinstance(response["content"], list):
                # Bedrock returns array of content blocks
                for block in response["content"]:
                    if block.get("type") == "text":
                        content += block.get("text", "")
            else:
                content = str(response["content"])

        # Try to parse JSON from content
        try:
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()

            ai_data = json.loads(content)
            
            # Log AI response summary for debugging
            confirmed_count = len(ai_data.get("confirmed", []))
            rejected_count = len(ai_data.get("rejected", []))
            logger.info(
                "ai_response_parsed",
                entry_point_type=entry_point_type.value,
                confirmed_count=confirmed_count,
                rejected_count=rejected_count,
                total_candidates=len(candidates),
            )
        except json.JSONDecodeError as e:
            logger.error("ai_response_parse_error", error=str(e), content=content[:1000])
            return confirmed

        # Process confirmed entries
        for confirmed_item in ai_data.get("confirmed", []):
            candidate_index = confirmed_item.get("candidate_index")
            if candidate_index is None or candidate_index >= len(candidates):
                continue

            candidate = candidates[candidate_index]

            if not confirmed_item.get("is_entry_point", False):
                continue

            name = confirmed_item.get("name", "")
            description = confirmed_item.get("description", "")
            confidence = float(confirmed_item.get("confidence", 0.0))
            reasoning = confirmed_item.get("reasoning", "")

            # Validate required fields
            if not name or not description:
                logger.warning(
                    "ai_response_missing_fields",
                    candidate_index=candidate_index,
                    has_name=bool(name),
                    has_description=bool(description),
                )
                continue

            confirmed.append(
                ConfirmedEntryPoint(
                    symbol_id=candidate.symbol_id,
                    file_id=candidate.file_id,
                    entry_point_type=entry_point_type,
                    framework=candidate.framework,
                    name=name,
                    description=description,
                    metadata=candidate.metadata,
                    ai_confidence=confidence,
                    ai_reasoning=reasoning,
                )
            )

        return confirmed

    async def suggest_entry_point_file_paths(
        self, repo_tree: dict[str, Any], languages: list[str]
    ) -> list[str]:
        """
        STEP 2: Analyze repository structure and suggest potential entry point file paths.
        
        Args:
            repo_tree: Repository directory tree structure
            languages: List of languages in the repository
            
        Returns:
            List of file paths that might contain entry points
        """
        prompt = f"""Analyze the repository structure below and identify ALL file paths that could potentially contain entry points.

CRITICAL: Your goal is to find EVERY file that might contain entry points. It's better to include too many files than to miss any. Cast a wide net - we'll filter false positives later.

## What are Entry Points?

Entry points are code that can be invoked from OUTSIDE the application:

1. **HTTP Endpoints**: Code that accepts HTTP requests
   - Routes, controllers, handlers, endpoints
   - REST API endpoints, GraphQL resolvers
   - WebSocket handlers, gRPC services

2. **Event Handlers**: Code that consumes messages/events
   - Consumers, subscribers, listeners
   - Message queue handlers, event processors
   - Kafka consumers, RabbitMQ consumers, SQS handlers

3. **Scheduled Tasks**: Code that runs on a schedule
   - Cron jobs, timers, periodic tasks
   - Scheduled jobs, background workers
   - Quartz jobs, Spring @Scheduled methods

## Repository Context

Languages: {', '.join(languages) if languages else 'Unknown'}

## Comprehensive File Patterns to Look For

### HTTP Endpoints:
- **Python**: `*route*.py`, `*controller*.py`, `*handler*.py`, `*api*.py`, `*endpoint*.py`, `app.py`, `main.py`, `server.py`, `*service*.py` (if in API context)
- **Kotlin/Java**: `*Route*.kt`, `*Controller*.kt`, `*Handler*.kt`, `*Endpoint*.kt`, `*Api*.kt`, `*Resource*.kt`, `Application.kt`, `*Service*.kt` (if in API context)
- **JavaScript/TypeScript**: `*route*.js`, `*controller*.js`, `*handler*.js`, `*api*.js`, `*endpoint*.js`, `app.js`, `server.js`, `index.js` (if in API context)
- **Directories**: `routes/`, `controllers/`, `handlers/`, `api/`, `endpoints/`, `rest/`, `graphql/`

### Event Handlers:
- **Python**: `*consumer*.py`, `*listener*.py`, `*subscriber*.py`, `*handler*.py` (if in event context), `*worker*.py`
- **Kotlin/Java**: `*Consumer*.kt`, `*Listener*.kt`, `*Subscriber*.kt`, `*Handler*.kt` (if in event context), `*Worker*.kt`
- **JavaScript/TypeScript**: `*consumer*.js`, `*listener*.js`, `*subscriber*.js`, `*handler*.js` (if in event context)
- **Directories**: `consumers/`, `listeners/`, `subscribers/`, `handlers/`, `events/`, `workers/`

### Scheduled Tasks:
- **Python**: `*scheduler*.py`, `*cron*.py`, `*job*.py`, `*task*.py`, `*worker*.py`
- **Kotlin/Java**: `*Scheduler*.kt`, `*Cron*.kt`, `*Job*.kt`, `*Task*.kt`, `*Worker*.kt`
- **JavaScript/TypeScript**: `*scheduler*.js`, `*cron*.js`, `*job*.js`, `*task*.js`
- **Directories**: `schedulers/`, `jobs/`, `tasks/`, `cron/`

### Framework-Specific Patterns:

**Spring Boot (Java/Kotlin)**:
- Files with `@RestController`, `@Controller`, `@RequestMapping`
- Files in `controller/`, `rest/`, `api/` directories
- Files with `@Scheduled` methods
- Files with `@KafkaListener`, `@RabbitListener`

**Apache Camel (Java/Kotlin)**:
- Files extending `RouteBuilder` or implementing route configuration
- Files with `configure()` methods containing `from()` calls
- Files in `route/`, `routes/`, `camel/` directories

**Flask/FastAPI (Python)**:
- Files with `@app.route`, `@router.get/post/put/delete`
- Files in `routes/`, `api/`, `endpoints/` directories
- Files with `Blueprint` definitions

**Express/Koa (JavaScript)**:
- Files with `router.get/post/put/delete`, `app.get/post/put/delete`
- Files in `routes/`, `controllers/`, `api/` directories

**Ktor (Kotlin)**:
   - Files with routing DSL (routing {{ get {{ ... }} }})
- Files in `routes/`, `api/` directories

## Important Notes

1. **Multiple Entry Points Per File**: A single file can contain MULTIPLE entry points. For example:
   - A route file with 10 different HTTP endpoints = 10 entry points
   - A consumer file with multiple `from()` calls = multiple entry points
   - A scheduler file with multiple cron jobs = multiple entry points

2. **Don't Rely Only on Naming**: Some entry points may not follow obvious naming patterns. Look at:
   - Directory structure (files in `api/`, `routes/`, `handlers/` directories)
   - File location (files in root or main application directories)
   - Framework conventions (Spring controllers, Camel routes)

3. **Include Edge Cases**:
   - Main application files (`main.py`, `Application.kt`, `app.js`)
   - Configuration files that might define routes (`routes.py`, `urls.py`)
   - Test files that might have test endpoints (optional, but include if unsure)

Repository Structure:
```json
{json.dumps(repo_tree, indent=2)}
```

## Your Task

Go through the repository structure systematically and identify ALL files that could potentially contain entry points. Be thorough - include any file that might have:
- HTTP route definitions
- Event consumer logic
- Scheduled task definitions
- Framework-specific entry point patterns

Return your response as JSON in this exact format:
{{
  "suggested_file_paths": [
    "path/to/file1.py",
    "path/to/file2.kt",
    "path/to/file3.js",
    ...
  ],
  "reasoning": "Comprehensive explanation of why these paths were suggested, including patterns identified and any edge cases included"
}}

CRITICAL: Only include file paths that exist in the repository structure above. Return relative paths from the repository root. Be thorough - it's better to include 100 potential files than to miss 1 actual entry point file.
"""

        try:
            response = await self._call_claude_bedrock(prompt)
            
            # Extract content from response
            content = ""
            if "content" in response:
                if isinstance(response["content"], list):
                    for block in response["content"]:
                        if block.get("type") == "text":
                            content += block.get("text", "")
                else:
                    content = str(response["content"])
            
            # Parse JSON - extract from markdown code blocks if present
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end == -1:
                    # Unterminated code block, try to find end of content
                    content = content[start:].strip()
                else:
                    content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                if end == -1:
                    # Unterminated code block, try to find end of content
                    content = content[start:].strip()
                else:
                    content = content[start:end].strip()
            
            # Try to parse JSON with better error handling
            try:
                ai_data = json.loads(content)
            except json.JSONDecodeError as json_err:
                # Try to repair common JSON issues
                error_msg = str(json_err)
                error_pos = getattr(json_err, 'pos', None)
                
                # If unterminated string near end, try to close it
                if "Unterminated string" in error_msg and error_pos is not None:
                    if error_pos >= len(content) - 200:  # Near end of content
                        # Find the last unclosed quote and close it
                        repaired = content
                        # Count unclosed quotes from error position backwards
                        quote_count = 0
                        for i in range(error_pos - 1, max(0, error_pos - 1000), -1):
                            if repaired[i] == '"' and (i == 0 or repaired[i-1] != '\\'):
                                quote_count += 1
                                if quote_count == 1:
                                    # Found the opening quote, try to close structures
                                    # Close any open strings, braces, brackets
                                    repaired = repaired[:error_pos] + '"'
                                    # Try to close any open JSON structures
                                    open_braces = repaired.count('{') - repaired.count('}')
                                    open_brackets = repaired.count('[') - repaired.count(']')
                                    repaired += '}' * open_braces + ']' * open_brackets
                                    try:
                                        ai_data = json.loads(repaired)
                                        logger.warning("json_repaired", original_error=error_msg[:100])
                                    except json.JSONDecodeError:
                                        # Repair failed, log and return empty
                                        logger.error("json_repair_failed", error=error_msg, position=error_pos, content_preview=content[max(0, error_pos-100):error_pos+50])
                                        return []
                                break
                    else:
                        logger.error("json_parse_error", error=error_msg, position=error_pos, content_preview=content[max(0, error_pos-100):error_pos+50])
                        return []
                else:
                    logger.error("json_parse_error", error=error_msg, position=error_pos, content_preview=content[max(0, error_pos-100):error_pos+50] if error_pos else content[:200])
                    return []
            
            suggested_paths = ai_data.get("suggested_file_paths", [])
            
            logger.info(
                "ai_file_path_suggestions",
                suggested_count=len(suggested_paths),
                reasoning=ai_data.get("reasoning", "")[:200] if ai_data.get("reasoning") else "",
            )
            
            return suggested_paths
        except Exception as e:
            logger.error("ai_file_path_suggestion_error", error=str(e), error_type=type(e).__name__)
            return []

    async def confirm_entry_points_from_files(
        self,
        files: dict[str, Any],  # dict[str, FileModel] - FileModel imported in entry_point_service
        repo_context: dict[str, Any],
        symbol_contexts: dict[str, dict[str, Any]],
        batch_size: int = 10,
        on_batch_confirmed: Callable[[list[ConfirmedEntryPoint], int], Awaitable[None]] | None = None,
    ) -> list[ConfirmedEntryPoint]:
        """
        STEP 3: Analyze files in batches and confirm entry points.
        
        Args:
            files: Dictionary mapping file paths to FileModel objects
            repo_context: Repository context (languages, repo_tree)
            symbol_contexts: Symbol contexts for all symbols in the files
            batch_size: Number of files to process per batch
            on_batch_confirmed: Callback called after each batch
            
        Returns:
            List of all confirmed entry points
        """
        
        file_list = list(files.values())
        all_confirmed: list[ConfirmedEntryPoint] = []
        
        # Process files in batches
        for batch_start in range(0, len(file_list), batch_size):
            batch_files = file_list[batch_start:batch_start + batch_size]
            batch_index = batch_start // batch_size
            
            logger.info(
                "processing_file_batch",
                batch_index=batch_index,
                batch_size=len(batch_files),
                total_files=len(file_list),
            )
            
            try:
                batch_confirmed = await self._confirm_file_batch(
                    batch_files, repo_context, symbol_contexts
                )
                
                all_confirmed.extend(batch_confirmed)
                
                # Call callback if provided
                if on_batch_confirmed and batch_confirmed:
                    await on_batch_confirmed(batch_confirmed, batch_index)
                
                logger.info(
                    "file_batch_complete",
                    batch_index=batch_index,
                    confirmed_count=len(batch_confirmed),
                    batch_size=len(batch_files),
                )
            except Exception as e:
                logger.error(
                    "file_batch_error",
                    batch_index=batch_index,
                    error=str(e),
                )
        
        return all_confirmed

    async def _confirm_file_batch(
        self,
        files: list[Any],  # list[FileModel] - FileModel imported in entry_point_service
        repo_context: dict[str, Any],
        symbol_contexts: dict[str, dict[str, Any]],
    ) -> list[ConfirmedEntryPoint]:
        """Confirm entry points in a batch of files."""
        
        # Build prompt with file contents
        file_descriptions = []
        for i, file_model in enumerate(files):
            # Get all symbols in this file
            file_symbols = [
                ctx for symbol_id, ctx in symbol_contexts.items()
                if ctx.get('file_path') == file_model.relative_path
            ]
            
            file_descriptions.append(f"""
File {i}: {file_model.relative_path}
Language: {file_model.language}
Content Length: {len(file_model.content or '')} characters

Full File Content:
```{file_model.language}
{file_model.content or ''}
```

Symbols in this file:
{chr(10).join(f"- {s.get('name', 'unknown')} ({s.get('qualified_name', 'unknown')})" for s in file_symbols)}
""")
        
        prompt = f"""CRITICAL TASK: Analyze the following files and identify EVERY entry point - code that can be invoked from outside the application.

## Your Mission
Find ALL entry points in these files. Missing even one entry point is worse than including a false positive. Be thorough and systematic.

## Entry Point Types

1. **HTTP**: Code that accepts HTTP requests
   - Routes, controllers, endpoints, handlers
   - REST API endpoints, GraphQL resolvers
   - WebSocket handlers, gRPC services
   - Examples: `@GetMapping`, `@app.route`, `router.get()`, `from("netty-http:...")`
   - **CRITICAL PRINCIPLE**: Only individual methods/functions that directly handle HTTP requests are entry points. Framework setup code, class registrations, or configuration code that registers classes/routes are NOT entry points. Each method that handles a specific HTTP request is a separate entry point.

2. **EVENT**: Code that consumes messages/events
   - Consumers, subscribers, listeners
   - Message queue handlers, event processors
   - Examples: `from("kafka:...")`, `@KafkaListener`, `@RabbitListener`, `from("sqs:...")`

3. **SCHEDULER**: Code that runs on a schedule
   - Cron jobs, timers, periodic tasks
   - Examples: `from("quartz:...")`, `@Scheduled`, `@CronSchedule`, `timer(...)`

## Repository Context
- Languages: {repo_context.get('languages', [])}

## Files to Analyze (Batch of {len(files)} files)
{''.join(file_descriptions)}

## Critical Instructions

1. **Find EVERY Entry Point**: A single file can have MULTIPLE entry points. You MUST identify EACH one separately.

2. **Examples of Multiple Entry Points in One File**:
   
   **Example 1 - HTTP File with Multiple Endpoints**:
   ```python
   @app.route('/users', methods=['GET'])
   def get_users():  # Entry Point 1
       ...
   
   @app.route('/users', methods=['POST'])
   def create_user():  # Entry Point 2
       ...
   
   @app.route('/users/<id>', methods=['DELETE'])
   def delete_user(id):  # Entry Point 3
       ...
   ```
   This file has 3 HTTP entry points.

   **Example 2 - Camel Route with Multiple External Triggers**:
   ```kotlin
   override fun configure() {{
       from("netty-http:http://0.0.0.0:8080/health")  // Entry Point 1 - HTTP
           .routeId("health_check")
           ...
       
       from("quartz://cron?cron=0+0+12+*+*+?")  // Entry Point 2 - SCHEDULER
           .routeId("daily_job")
           ...
       
       from("kafka:payment-events")  // Entry Point 3 - EVENT
           .routeId("payment_consumer")
           ...
   }}
   ```
   This file has 3 entry points (1 HTTP, 1 SCHEDULER, 1 EVENT).

   **Example 3 - Spring Controller with Multiple Endpoints**:
   ```kotlin
   @RestController
   class PaymentController {{
       @GetMapping("/payments")  // Entry Point 1
       fun listPayments() {{ ... }}
       
       @PostMapping("/payments")  // Entry Point 2
       fun createPayment() {{ ... }}
       
       @GetMapping("/payments/{{id}}")  // Entry Point 3
       fun getPayment(id: String) {{ ... }}
   }}
   ```
   This file has 3 HTTP entry points.

   **Example 4 - Class with Multiple HTTP Endpoints**:
   ```kotlin
   @Path("/payments")
   class PaymentResource {{
       @GET
       @Path("/")
       fun listPayments(): List<Payment> {{ ... }}  // Entry Point 1 - GET /payments/
       
       @POST
       @Path("/")
       fun createPayment(payment: Payment): Payment {{ ... }}  // Entry Point 2 - POST /payments/
       
       @GET
       @Path("/{{id}}")
       fun getPayment(@PathParam("id") id: String): Payment {{ ... }}  // Entry Point 3 - GET /payments/{id}
   }}
   ```
   This file has 3 HTTP entry points. Each method that directly handles an HTTP request is a separate entry point. Framework setup code that registers this class is NOT an entry point - only the individual methods that handle HTTP requests are entry points.

3. **For EACH Entry Point Found**, provide:
   - **symbol_name**: The function/method/class name that contains the entry point
     - For route builders: usually "configure"
     - For controllers: the method name (e.g., "getUsers", "createPayment")
     - For consumers: the method name or "configure"
   - **qualified_name**: Full qualified name if available (e.g., "com.example.PaymentController.getPayment")
   - **type**: "HTTP", "EVENT", or "SCHEDULER"
   - **name**: Human-readable name for THIS specific entry point (must distinguish it from other entry points in the same file)
     - Examples: "Get Users Endpoint", "Create Payment Endpoint", "Daily Report Cron Job", "Payment Event Consumer"
   - **description**: 1-2 line description of what THIS specific entry point does
   - **confidence**: 0.0-1.0 (use 0.0 for internal routing, 0.9+ for clear external entry points)
   - **reasoning**: Brief explanation of why this is an entry point (mention the specific trigger: HTTP path, event source, schedule)

4. **What to Include**:
   - ALL HTTP endpoints (GET, POST, PUT, DELETE, PATCH, etc.)
   - ALL event consumers (Kafka, RabbitMQ, SQS, etc.)
   - ALL scheduled tasks (cron jobs, timers, periodic tasks)
   - Even if they seem similar or related - each external trigger is a separate entry point

5. **What to Exclude** (set confidence to 0.0):
   - Internal method calls (not externally triggered)
   - Internal routing between components
   - Helper functions that are called by entry points but aren't entry points themselves
   - Framework setup/registration code - code that registers classes, routes, or handlers but doesn't directly handle external triggers itself
   - Classes that are registered but don't directly handle external requests/events/schedules - only the individual methods/functions within those classes that directly handle external triggers are entry points
   - Configuration code that sets up routes or registers components but doesn't directly respond to external triggers
   - **CRITICAL PRINCIPLE**: Only methods/functions that directly handle external triggers (HTTP requests, events, schedules) are entry points. Framework setup, registration, or configuration code is NOT an entry point.

## Return Format

Return your response as JSON in this exact format:
{{
  "files": [
    {{
      "file_path": "path/to/file.py",
      "has_entry_points": true,
      "entry_points": [
        {{
          "symbol_name": "get_users",
          "qualified_name": "com.example.UserController.get_users",
          "type": "HTTP",
          "name": "Get Users Endpoint",
          "description": "HTTP GET endpoint that retrieves a list of users",
          "confidence": 0.95,
          "reasoning": "Function decorated with @app.route('/users', methods=['GET']) which creates an external HTTP endpoint"
        }},
        {{
          "symbol_name": "create_user",
          "qualified_name": "com.example.UserController.create_user",
          "type": "HTTP",
          "name": "Create User Endpoint",
          "description": "HTTP POST endpoint that creates a new user",
          "confidence": 0.95,
          "reasoning": "Function decorated with @app.route('/users', methods=['POST']) which creates an external HTTP endpoint"
        }}
      ]
    }}
  ]
}}

## Important Notes

- Include ALL files that have entry points
- For each file, list EVERY entry point separately
- Analyze the actual code structure, not just file names
- Look for framework-specific patterns (decorators, annotations, DSL calls)
- Be thorough - missing entry points is worse than false positives
- If unsure whether something is an entry point, include it with lower confidence (0.6-0.8)
"""

        try:
            response = await self._call_claude_bedrock(prompt)
            
            # Extract and parse JSON
            content = ""
            if "content" in response:
                if isinstance(response["content"], list):
                    for block in response["content"]:
                        if block.get("type") == "text":
                            content += block.get("text", "")
                else:
                    content = str(response["content"])
            
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            ai_data = json.loads(content)
            
            confirmed: list[ConfirmedEntryPoint] = []
            
            # Process each file's entry points
            for file_data in ai_data.get("files", []):
                file_path = file_data.get("file_path")
                if not file_path:
                    continue
                
                # Find the FileModel
                file_model = next((f for f in files if f.relative_path == file_path), None)
                if not file_model:
                    continue
                
                # Process each entry point
                for ep_data in file_data.get("entry_points", []):
                    symbol_name = ep_data.get("symbol_name")
                    qualified_name = ep_data.get("qualified_name", "")
                    
                    # Find symbol in contexts (symbol_contexts is keyed by symbol_id)
                    # Must match file_path AND (qualified_name OR name) to ensure correct symbol
                    found_symbol_id = None
                    
                    # Strategy 1: Match by file_path + qualified_name (most precise)
                    if qualified_name:
                        for symbol_id, ctx in symbol_contexts.items():
                            ctx_file_path = ctx.get('file_path')
                            ctx_qualified_name = ctx.get('qualified_name')
                            
                            if ctx_file_path == file_path and ctx_qualified_name == qualified_name:
                                found_symbol_id = symbol_id
                                break
                    
                    # Strategy 2: Match by file_path + name (if qualified_name didn't match)
                    if not found_symbol_id and symbol_name:
                        for symbol_id, ctx in symbol_contexts.items():
                            ctx_file_path = ctx.get('file_path')
                            ctx_name = ctx.get('name')
                            
                            if ctx_file_path == file_path and ctx_name == symbol_name:
                                found_symbol_id = symbol_id
                                break
                    
                    # Strategy 3: Fuzzy matching - partial qualified name match
                    if not found_symbol_id and qualified_name:
                        qualified_parts = qualified_name.split('.')
                        if len(qualified_parts) >= 2:
                            # Try matching last 2 parts (class.method)
                            partial_match = '.'.join(qualified_parts[-2:])
                            for symbol_id, ctx in symbol_contexts.items():
                                ctx_file_path = ctx.get('file_path')
                                ctx_qualified_name = ctx.get('qualified_name', '')
                                
                                if ctx_file_path == file_path and partial_match in ctx_qualified_name:
                                    found_symbol_id = symbol_id
                                    logger.debug(
                                        "symbol_matched_fuzzy",
                                        file_path=file_path,
                                        symbol_name=symbol_name,
                                        qualified_name=qualified_name,
                                        matched_qualified_name=ctx_qualified_name,
                                    )
                                    break
                    
                    # Strategy 4: Match by file_path only (last resort - use first symbol in file)
                    if not found_symbol_id:
                        for symbol_id, ctx in symbol_contexts.items():
                            if ctx.get('file_path') == file_path:
                                found_symbol_id = symbol_id
                                logger.warning(
                                    "symbol_matched_by_file_only",
                                    file_path=file_path,
                                    symbol_name=symbol_name,
                                    qualified_name=qualified_name,
                                    matched_symbol_name=ctx.get('name'),
                                    matched_qualified_name=ctx.get('qualified_name'),
                                )
                                break
                    
                    if not found_symbol_id:
                        logger.warning(
                            "symbol_not_found_for_entry_point",
                            file_path=file_path,
                            symbol_name=symbol_name,
                            qualified_name=qualified_name,
                            available_symbols_in_file=[
                                {"name": ctx.get('name'), "qualified_name": ctx.get('qualified_name')}
                                for ctx in symbol_contexts.values()
                                if ctx.get('file_path') == file_path
                            ],
                        )
                        continue
                    
                    # Determine entry point type
                    ep_type_str = ep_data.get("type", "HTTP").upper()
                    if ep_type_str == "HTTP":
                        entry_point_type = EntryPointType.HTTP
                    elif ep_type_str == "EVENT":
                        entry_point_type = EntryPointType.EVENT
                    elif ep_type_str == "SCHEDULER":
                        entry_point_type = EntryPointType.SCHEDULER
                    else:
                        entry_point_type = EntryPointType.HTTP
                    
                    # Skip entry points with confidence 0.0 (these are rejected/internal routing)
                    confidence = float(ep_data.get("confidence", 0.0))
                    if confidence <= 0.0:
                        continue
                    
                    # Infer framework from file path and type
                    framework = self._infer_framework_from_path(file_path, ep_type_str)
                    
                    confirmed.append(
                        ConfirmedEntryPoint(
                            symbol_id=found_symbol_id,
                            file_id=file_model.id,
                            entry_point_type=entry_point_type,
                            framework=framework,
                            name=ep_data.get("name", ""),
                            description=ep_data.get("description", ""),
                            metadata={},
                            ai_confidence=confidence,
                            ai_reasoning=ep_data.get("reasoning", ""),
                        )
                    )
            
            filtered_confirmed = [ep for ep in confirmed if ep.ai_confidence >= self._min_confidence]
            
            logger.info(
                "file_batch_confirmation_result",
                files_analyzed=len(files),
                entry_points_found=len(confirmed),
                entry_points_confirmed=len(filtered_confirmed),
                low_confidence_rejected=len(confirmed) - len(filtered_confirmed),
            )
            
            logger.debug(
                "file_batch_confirmation_detailed",
                files_analyzed=[f.relative_path for f in files],
                entry_points_by_file={
                    ep_data.get("file_path"): len(ep_data.get("entry_points", []))
                    for ep_data in ai_data.get("files", [])
                },
            )
            
            return filtered_confirmed
        except Exception as e:
            logger.error("file_batch_confirmation_error", error=str(e), files=[f.relative_path for f in files])
            return []

    def _infer_framework_from_path(self, file_path: str, entry_point_type: str) -> str:
        """Infer framework from file path and entry point type."""
        file_path_lower = file_path.lower()
        
        # HTTP frameworks
        if entry_point_type == "HTTP":
            if "flask" in file_path_lower:
                return "flask"
            elif "fastapi" in file_path_lower or "fast_api" in file_path_lower:
                return "fastapi"
            elif "django" in file_path_lower:
                return "django"
            elif "ktor" in file_path_lower:
                return "ktor"
            elif "spring" in file_path_lower:
                return "spring-boot"
            elif "express" in file_path_lower:
                return "express"
        
        # Event frameworks
        elif entry_point_type == "EVENT":
            if "camel" in file_path_lower:
                return "apache-camel"
            elif "kafka" in file_path_lower:
                return "kafka"
            elif "pulsar" in file_path_lower:
                return "pulsar"
            elif "celery" in file_path_lower:
                return "celery"
        
        # Scheduler frameworks
        elif entry_point_type == "SCHEDULER":
            if "quartz" in file_path_lower:
                return "quartz"
            elif "spring" in file_path_lower:
                return "spring-boot"
            elif "apscheduler" in file_path_lower:
                return "apscheduler"
        
        return "unknown"


    async def generate_repo_description(
        self,
        repo_name: str,
        languages: list[str],
        frameworks: list[str],
        entry_points: list[dict[str, str]],
        repo_tree: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate a concise repo description based on detected entry points and structure.
        
        Args:
            repo_name: Name of the repository
            languages: Programming languages used
            frameworks: Frameworks detected
            entry_points: List of entry point dicts with name, type, description
            repo_tree: Optional repo directory tree
            
        Returns:
            A 2-4 sentence description of the repository
        """
        # Build entry points summary
        ep_by_type: dict[str, list[str]] = {}
        for ep in entry_points:
            ep_type = ep.get("type", "unknown").upper()
            if ep_type not in ep_by_type:
                ep_by_type[ep_type] = []
            ep_by_type[ep_type].append(f"  - {ep.get('name', 'unknown')}: {ep.get('description', '')}")

        ep_summary_parts = []
        for ep_type, names in ep_by_type.items():
            ep_summary_parts.append(f"\n{ep_type} entry points ({len(names)}):")
            ep_summary_parts.extend(names[:10])  # Limit to first 10 per type
            if len(names) > 10:
                ep_summary_parts.append(f"  ... and {len(names) - 10} more")

        ep_summary = "\n".join(ep_summary_parts)

        tree_section = ""
        if repo_tree:
            import json
            tree_json = json.dumps(repo_tree, indent=2)
            # Limit tree size to avoid token limits
            if len(tree_json) > 3000:
                tree_json = tree_json[:3000] + "\n... (truncated)"
            tree_section = f"\nRepository structure:\n{tree_json}"

        prompt = f"""Generate a concise technical description (2-4 sentences) for this code repository.

Repository: {repo_name}
Languages: {', '.join(languages) if languages else 'Unknown'}
Frameworks: {', '.join(frameworks) if frameworks else 'Unknown'}

Detected entry points:
{ep_summary}
{tree_section}

Write a description that would help an engineer quickly understand:
1. What this service/application does
2. What external interfaces it exposes (HTTP APIs, event consumers, scheduled jobs)
3. Key technologies used

Return ONLY the description text, no JSON, no formatting, no prefix. Just the plain text description."""

        try:
            response = await self._call_claude_bedrock(prompt, max_tokens=512)

            content = ""
            if "content" in response:
                if isinstance(response["content"], list):
                    for block in response["content"]:
                        if block.get("type") == "text":
                            content += block.get("text", "")
                else:
                    content = str(response["content"])

            return content.strip()
        except Exception as e:
            logger.error("repo_description_generation_error", error=str(e))
            # Fallback to a simple auto-generated description
            return (
                f"{repo_name} is a {', '.join(languages)} service using {', '.join(frameworks) if frameworks else 'various frameworks'}. "
                f"It exposes {len(entry_points)} entry points including "
                f"{', '.join(f'{len(v)} {k}' for k, v in ep_by_type.items())}."
            )

    async def generate_flow_documentation(
        self,
        entry_point_name: str,
        entry_point_type: str,
        entry_point_description: str,
        symbol_qualified_name: str,
        nodes_with_code: list[dict[str, Any]],  # List of dicts with id, name, qualified_name, depth, source_code, signature
        previous_steps: list[dict[str, Any]] | None = None,
        iteration: int = 1,
        start_depth: int = 0,
        end_depth: int = 3,
    ) -> dict[str, Any]:
        """
        Generate flow documentation for an entry point using AI.
        
        Args:
            entry_point_name: Name of the entry point
            entry_point_type: Type (HTTP, EVENT, SCHEDULER)
            entry_point_description: Description of the entry point
            symbol_qualified_name: Qualified name of the entry point symbol
            nodes_with_code: List of call graph nodes with their source code
            previous_steps: Previous flow steps from earlier iterations (if any)
            iteration: Current iteration number (1-4)
            start_depth: Starting depth for this iteration
            end_depth: Ending depth for this iteration
            
        Returns:
            Dictionary with flow_name, technical_summary, and steps
        """
        logger.debug(
            "ai_flow_documentation_starting",
            iteration=iteration,
            entry_point_name=entry_point_name,
            nodes_count=len(nodes_with_code),
            depth_range=f"{start_depth}-{end_depth}",
            has_previous_steps=previous_steps is not None,
        )
        
        # Build nodes section
        nodes_section = []
        for node in nodes_with_code:
            nodes_section.append(f"""
Node: {node.get('name', 'unknown')} ({node.get('qualified_name', 'unknown')})
Depth: {node.get('depth', 0)}
Signature: {node.get('signature', 'N/A')}
Source Code:
```{node.get('language', '')}
{node.get('source_code', '')}
```
""")
        
        logger.debug(
            "ai_flow_documentation_prompt_built",
            iteration=iteration,
            prompt_length=sum(len(section) for section in nodes_section),
            nodes_in_prompt=len(nodes_section),
        )

        # Build previous steps section if available
        previous_steps_section = ""
        if previous_steps and iteration > 1:
            previous_steps_json = json.dumps(previous_steps, indent=2)
            previous_steps_section = f"""
Previous Flow Steps (from earlier iterations):
{previous_steps_json}

Please merge the new analysis with the previous steps, maintaining flow coherence.
"""

        prompt = f"""Analyze the following entry point and its call graph (depths {start_depth}-{end_depth}).

Entry Point:
- Name: {entry_point_name}
- Type: {entry_point_type}
- Description: {entry_point_description}
- Symbol: {symbol_qualified_name}

Call Graph Nodes (depths {start_depth}-{end_depth}):
{''.join(nodes_section)}
{previous_steps_section}

CRITICAL: You MUST return ONLY valid JSON. Your response will be parsed by json.loads() - if it fails, the entire request fails.

STRICT JSON FORMATTING RULES - FOLLOW THESE EXACTLY:

1. RESPONSE FORMAT:
   - Return ONLY the JSON object, nothing else
   - NO markdown code blocks (no ```json or ```)
   - NO explanations before or after
   - NO comments
   - Start with {{ and end with }}

2. STRING ESCAPING - MANDATORY:
   - Every double quote INSIDE a string value MUST be escaped as \"
   - Every backslash MUST be escaped as \\
   - Every newline MUST be escaped as \\n (two characters: backslash then n)
   - Every tab MUST be escaped as \\t
   - Every carriage return MUST be escaped as \\r
   
   CORRECT: "description": "User said \\"hello\\" and left"
   WRONG:   "description": "User said "hello" and left"
   
   CORRECT: "file_path": "src/main/file.py"
   WRONG:   "file_path": "src\\main\\file.py" (unescaped backslashes)

3. STRING CLOSING - MANDATORY:
   - EVERY string MUST have BOTH opening " and closing "
   - If a string value is long, ensure it ends with " before the comma or }}
   - NEVER leave a string unterminated
   
   CORRECT: "long_description": "This is a very long description that ends properly"
   WRONG:   "long_description": "This is a very long description that doesn't end

4. CODE CONTENT RESTRICTIONS:
   - DO NOT include actual source code in JSON strings
   - For code snippets, provide ONLY references:
     * symbol_name: just the name (e.g., "processPayment")
     * qualified_name: full qualified name (e.g., "com.example.Service.processPayment")
     * file_path: file path (e.g., "src/service.py")
     * line_range: {{"start": 10, "end": 25}}
   - DO NOT put code blocks, function bodies, or multi-line code in JSON strings

5. STRUCTURAL REQUIREMENTS:
   - Use commas to separate ALL array elements and object properties
   - Ensure ALL opening braces {{ have matching closing braces }}
   - Ensure ALL opening brackets [ have matching closing brackets ]
   - No trailing commas after last element in arrays/objects

6. VALIDATION CHECKLIST - VERIFY BEFORE RETURNING:
   ✓ Every " has a matching closing "
   ✓ Every quote inside a string is escaped as \"
   ✓ Every backslash is escaped as \\
   ✓ Every {{ has a matching }}
   ✓ Every [ has a matching ]
   ✓ No unescaped newlines in strings (use \\n)
   ✓ Response starts with {{ and ends with }}
   ✓ Steps array contains at least 1 step
   ✓ Can be parsed by json.loads() without errors

RETURN ONLY THE JSON OBJECT BELOW - NO OTHER TEXT:

Return this exact JSON structure:
{{
  "flow_name": "concise technical name",
  "technical_summary": "complete technical summary describing what happens",
  "file_paths": ["file1.py", "file2.py"],
  "steps": [
    {{
      "step_number": 1,
      "title": "step title",
      "description": "technical description",
      "file_path": "main file path",
      "important_log_lines": ["logger.info message about processing payment"],
      "important_code_snippets": [
        {{
          "symbol_name": "processPayment",
          "qualified_name": "com.example.PaymentService.processPayment",
          "file_path": "src/payment/service.py",
          "line_range": {{"start": 10, "end": 25}}
        }}
      ]
    }}
  ]
}}
"""

        try:
            logger.debug(
                "ai_flow_documentation_calling_claude",
                iteration=iteration,
                prompt_length=len(prompt),
            )
            
            # Use higher max_tokens for flow generation (large JSON responses)
            response = await self._call_claude_bedrock(prompt, max_tokens=16384)
            
            logger.debug(
                "ai_flow_documentation_response_received",
                iteration=iteration,
                response_keys=list(response.keys()) if isinstance(response, dict) else [],
            )
            
            # Extract content from response
            content = ""
            if "content" in response:
                if isinstance(response["content"], list):
                    for block in response["content"]:
                        if block.get("type") == "text":
                            content += block.get("text", "")
                else:
                    content = str(response["content"])
            
            logger.debug(
                "ai_flow_documentation_extracting_json",
                iteration=iteration,
                content_length=len(content),
            )
            
            # Simple JSON extraction: remove markdown code blocks if present
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end != -1:
                    content = content[start:end].strip()
                else:
                    # No closing ``` found, extract from start to end
                    content = content[start:].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                if end != -1:
                    content = content[start:end].strip()
                else:
                    # No closing ``` found, extract from start to end
                    content = content[start:].strip()
            
            # Find JSON object if not starting with {
            content_stripped = content.strip()
            if not content_stripped.startswith("{"):
                json_start = content.find("{")
                if json_start == -1:
                    # No JSON object found - will fail parsing with clear error
                    logger.warning(
                        "no_json_object_found",
                        iteration=iteration,
                        content_preview=content[:200],
                    )
                else:
                    # Find matching closing brace (accounting for strings)
                    brace_count = 0
                    in_string = False
                    escape_next = False
                    json_end = None
                    for i in range(json_start, len(content)):
                        char = content[i]
                        if escape_next:
                            escape_next = False
                            continue
                        if char == "\\":
                            escape_next = True
                            continue
                        if char == '"':
                            in_string = not in_string
                            continue
                        if not in_string:
                            if char == "{":
                                brace_count += 1
                            elif char == "}":
                                brace_count -= 1
                                if brace_count == 0:
                                    json_end = i + 1
                                    break
                    
                    if json_end:
                        content = content[json_start:json_end]
                    # If brace_count never reached 0, content remains unchanged and will fail parsing with clear error
            
            # Check if content looks complete (ends with } or ])
            content_stripped = content.strip()
            if not content_stripped.endswith(("}", "]")):
                logger.warning(
                    "json_content_may_be_incomplete",
                    iteration=iteration,
                    content_end=content_stripped[-50:] if len(content_stripped) > 50 else content_stripped,
                )
            
            # Parse JSON - simple and direct
            try:
                ai_data = json.loads(content)
            except json.JSONDecodeError as e:
                error_pos = getattr(e, 'pos', None)
                error_line = getattr(e, 'lineno', None)
                error_col = getattr(e, 'colno', None)
                error_msg = str(e)
                
                # If unterminated string and near end of content, try closing it (truncated response)
                if "Unterminated string" in error_msg and error_pos is not None:
                    # Check if we're very close to the end (likely truncated response)
                    if error_pos >= len(content) - 100:
                        # Find where the string started by looking backwards
                        string_start = None
                        for i in range(error_pos - 1, max(0, error_pos - 500), -1):
                            if content[i] == '"':
                                # Check if not escaped
                                escaped = False
                                j = i - 1
                                while j >= 0 and content[j] == '\\':
                                    escaped = not escaped
                                    j -= 1
                                if not escaped and (i == 0 or content[i - 1] in [':', ',', '{', '[', ' ', '\n']):
                                    string_start = i
                                    break
                        
                        if string_start is not None:
                            # Try closing the string and any open structures
                            repaired = content + '"'
                            # Try to close any open braces/brackets
                            brace_count = 0
                            bracket_count = 0
                            in_str = False
                            escape = False
                            for char in content:
                                if escape:
                                    escape = False
                                    continue
                                if char == '\\':
                                    escape = True
                                    continue
                                if char == '"':
                                    in_str = not in_str
                                    continue
                                if not in_str:
                                    if char == '{':
                                        brace_count += 1
                                    elif char == '}':
                                        brace_count -= 1
                                    elif char == '[':
                                        bracket_count += 1
                                    elif char == ']':
                                        bracket_count -= 1
                            
                            # Close any open structures
                            while bracket_count > 0:
                                repaired += ']'
                                bracket_count -= 1
                            while brace_count > 0:
                                repaired += '}'
                                brace_count -= 1
                            
                            try:
                                ai_data = json.loads(repaired)
                                logger.warning(
                                    "json_truncated_repaired",
                                    iteration=iteration,
                                    original_length=len(content),
                                    repaired_length=len(repaired),
                                )
                            except Exception:
                                pass
                
                # If still failed, log and raise
                if 'ai_data' not in locals():
                    # Log error with context
                    error_snippet = ""
                    if error_pos is not None:
                        snippet_start = max(0, error_pos - 200)
                        snippet_end = min(len(content), error_pos + 200)
                        error_snippet = content[snippet_start:snippet_end]
                    else:
                        error_snippet = content[:500]
                    
                    logger.error(
                        "json_parse_error",
                        iteration=iteration,
                        error=error_msg,
                        error_line=error_line,
                        error_col=error_col,
                        error_pos=error_pos,
                        content_snippet=error_snippet,
                        content_length=len(content),
                    )
                    
                    # Raise with clear message
                    raise ValueError(
                        f"Invalid JSON response from AI: {error_msg}. "
                        f"The AI must return valid JSON following the strict formatting rules. "
                        f"Error at position {error_pos} (line {error_line}, column {error_col})."
                    ) from e
            
            logger.debug(
                "ai_flow_documentation_parsed",
                iteration=iteration,
                flow_name=ai_data.get("flow_name"),
                technical_summary_length=len(ai_data.get("technical_summary", "")),
                steps_count=len(ai_data.get("steps", [])),
            )
            
            logger.info(
                "flow_documentation_generated",
                iteration=iteration,
                depth_range=f"{start_depth}-{end_depth}",
                steps_count=len(ai_data.get("steps", [])),
                flow_name=ai_data.get("flow_name"),
            )
            
            return ai_data
        except Exception as e:
            logger.error("flow_documentation_generation_error", error=str(e), iteration=iteration)
            raise
