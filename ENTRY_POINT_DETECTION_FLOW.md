# Entry Point Detection Flow

## Overview
The system detects entry points in 3 stages:
1. **Tree-sitter Detection**: Finds candidate entry points using AST queries
2. **AI Confirmation**: Validates candidates and generates names/descriptions
3. **Storage**: Saves confirmed entry points

## Stage 1: Tree-sitter Detection

### What Happens:
- Scans all files in the repository
- Uses Tree-sitter queries to match patterns (e.g., `camel_route_builder_class`, `camel_configure_method`)
- Creates `EntryPointCandidate` objects for each match

### Current Results:
- **28 candidates detected** for `payment-fraud-checker` repo
- Detection patterns:
  - `camel_route_builder_class`: Classes that extend RouteBuilder
  - `camel_configure_method`: Methods named `configure()`
  - `camel_from_call`: Calls to `from()` method

### Issues Found:
- Many candidates are from **test files** (`*Test.kt`)
- Some candidates are duplicates (same symbol detected multiple times)
- Framework inference was wrong: showing `"unknown"` and `"http"` instead of `"apache-camel"` and `"event"`

## Stage 2: AI Confirmation

### What Gets Sent to AI:

The AI receives a prompt with:

1. **Entry Point Type**: `HTTP`, `EVENT`, or `SCHEDULER`
2. **Repository Context**:
   - Languages detected: `["kotlin"]`
   - Frameworks detected: `["apache-camel"]`

3. **For Each Candidate** (all 28 sent in one batch):
   ```
   Candidate 0:
   - Symbol ID: 01KG9VW0PWP0XRY9B2HXP79GDX
   - Framework: unknown (should be apache-camel)
   - Detection Pattern: camel_route_builder_class
   - Metadata: {} (empty)
   - Confidence Score: 0.8
   
   - File: application/src/main/kotlin/.../HealthCheckRoute.kt
   - Function Name: configure
   - Signature: override fun configure()
   - Source Code:
   ```kotlin
   override fun configure() {
       from("netty-http://0.0.0.0:${port}/health")
           .routeId("health-check")
           .process { exchange -> ... }
   }
   ```
   ```

### AI Prompt Instructions:
```
You are analyzing code to identify real entry points. For each candidate below, determine:

1. Is this a real entry point? (true/false)
2. What is a human-readable name for this entry point?
3. Generate a 1-2 line description of what this entry point does
4. Confidence (0-1) - how confident are you this is a real entry point?
5. Reasoning - why you confirmed/rejected it

Only include candidates that are real entry points in the "confirmed" array. 
Be strict - only confirm if you're confident it's a real entry point.
```

### AI Response Format:
```json
{
  "confirmed": [
    {
      "candidate_index": 0,
      "is_entry_point": true,
      "name": "Health Check HTTP Endpoint",
      "description": "HTTP endpoint listening on port (configured) at /health path using netty-http",
      "confidence": 0.95,
      "reasoning": "This is a real HTTP entry point using netty-http component..."
    }
  ],
  "rejected": [
    {
      "candidate_index": 1,
      "is_entry_point": false,
      "reasoning": "This is a test class, not a real entry point..."
    }
  ]
}
```

### Why Only 2 Confirmed?

The AI is **strictly filtering** and likely rejecting:
1. **Test files**: Many candidates are from `*Test.kt` files (test classes, not real entry points)
2. **Duplicate detections**: Same `configure()` method detected multiple times via different patterns
3. **Incomplete routes**: Routes that don't have actual `from()` calls with real endpoints
4. **Helper/utility classes**: Classes that extend RouteBuilder but aren't actual entry points

### Current Results:
- **2 confirmed** out of 28 candidates
- Both are from `HealthCheckRoute.kt` (real HTTP endpoint)
- AI confidence: 0.95
- The other 26 were likely rejected because:
  - They're test files
  - They're duplicates
  - They don't have complete route definitions

## Stage 3: Storage

### Confirmed Entry Points:
- Stored in `entry_points` table
- Include: name, description, AI confidence, reasoning
- Can be queried via API: `GET /api/v1/repos/{repo_id}/entry-points`

### Candidates:
- Stored in `entry_point_candidates` table
- Remain even after confirmation (for audit/debugging)
- Can be queried via API: `GET /api/v1/repos/{repo_id}/entry-points/candidates`

## Improvements Needed

1. **Filter test files** before sending to AI (save API costs)
2. **Deduplicate candidates** (same symbol detected multiple times)
3. **Fix framework inference** (already fixed in code, but old candidates still have wrong values)
4. **Add more context** to AI prompt (e.g., file path patterns to help identify test files)
5. **Lower confidence threshold** or make AI less strict for event-driven entry points

## Example: What AI Sees

For a candidate from a test file, AI sees:
```
Candidate 5:
- Symbol ID: 01KG9VW0VM4NV6CQXCXXSSPA20
- Framework: unknown
- Detection Pattern: camel_route_builder_class
- Metadata: {}
- Confidence Score: 0.8

- File: application/src/test/kotlin/.../DSFraudConsumerRouteTest.kt
- Function Name: configure
- Signature: override fun configure()
- Source Code:
```kotlin
override fun configure() {
    from("direct:test-input")
        .to("mock:result")
}
```
```

AI reasoning: "This is a test class (`*Test.kt`), not a real entry point. The route uses `direct:` which is for testing, not production."

## Next Steps

1. Re-run detection with fixed framework inference
2. Add test file filtering
3. Add deduplication logic
4. Review AI prompt to be less strict for event-driven entry points
