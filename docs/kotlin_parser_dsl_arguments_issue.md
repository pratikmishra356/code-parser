# Kotlin Parser: Missing DSL Method Arguments

## Problem

The Kotlin parser captures DSL method **calls** but not the **arguments** passed to them. This prevents tracing the actual business logic in declarative frameworks like Apache Camel.

### Example: Apache Camel Route

```kotlin
override fun configure() {
    from(RouteId.UNLINKED_REFUND_FRAUD_CHECKER_ROUTE.directUri())
        .routeId(RouteId.UNLINKED_REFUND_FRAUD_CHECKER_ROUTE.id)
        .filter(unlinkedRefundPredicate)              // ← Predicate class (MISSED)
        .process(unlinkedRefundFraudProcessor)        // ← Processor class (MISSED)
        .to(UnlinkedRefundFraudProducerRoute.RouteId.UNLINKED_REFUND_FRAUD_PRODUCER_ROUTE.directUri())
        .end()
}
```

### What Parser Currently Does

**Captures (call targets)**:
- `from` (framework DSL method)
- `routeId` (framework DSL method)
- `filter` (framework DSL method)
- `process` (framework DSL method)
- `to` (framework DSL method)
- `end` (framework DSL method)

**Misses (arguments)**:
- `unlinkedRefundPredicate` (the actual predicate logic)
- `unlinkedRefundFraudProcessor` (the actual fraud checking logic)
- Route ID references

### Result in Call Graph

```
Downstream nodes for configure():
  1. from (no file path, no source)
  2. filter (no file path, no source)
  3. process (no file path, no source)
  4. to (no file path, no source)
  ...
```

**Missing**:
- No reference to `UnlinkedRefundFraudProcessor.kt`
- No reference to `UnlinkedRefundPredicate.kt`
- Cannot trace to actual business logic

---

## Impact on Flow Analysis

**Current AI Analysis**:
```
"This flow implements an Apache Camel routing configuration for message processing 
from Pulsar or Kafka messaging systems. The flow begins by establishing a consumer 
endpoint registration..."
```

**Generic description** because AI only sees DSL structure, not actual logic.

**Desired AI Analysis**:
```
"This flow detects unlinked refund fraud by consuming Pulsar messages, filtering 
based on fraud risk criteria (UnlinkedRefundPredicate), processing through fraud 
detection algorithms (UnlinkedRefundFraudProcessor) that check payment patterns 
and customer history, then routing results to the producer..."
```

**Detailed description** with actual business logic from Processor/Predicate classes.

---

## Root Cause: Parser Implementation

### Current Code (`_process_call` method)

```python
def _process_call(self, node: Node, ctx: KotlinParseContext) -> None:
    """Extract function call as reference with resolved path and symbol name."""
    
    # Get the called expression (method name)
    call_target = None
    for child in node.children:
        if child.type == "identifier":
            call_target = self._get_node_text(child, ctx.source_bytes)
            break
        elif child.type == "navigation_expression":
            call_target = self._get_node_text(child, ctx.source_bytes)
            break
    
    # ❌ STOPS HERE - Only captures call_target (e.g., "process")
    # ❌ Ignores value_arguments which contain the processor class
    
    # Resolve and create reference for call_target
    target_path, target_symbol_name = self._resolve_call_target(call_target, ctx)
    ctx.add_reference(...)
```

**Missing**: Extract `value_arguments` node and process identifiers within it.

### Tree-Sitter AST Structure

For `.process(unlinkedRefundFraudProcessor)`:

```
call_expression
├── navigation_expression
│   └── identifier: "process"
└── value_arguments
    └── value_argument
        └── simple_identifier: "unlinkedRefundFraudProcessor"  ← THIS IS MISSED
```

---

## Solution

### Add Argument Extraction to `_process_call`

```python
def _process_call(self, node: Node, ctx: KotlinParseContext) -> None:
    """Extract function call as reference with resolved path and symbol name."""
    if not ctx.current_scope:
        return

    # 1. Get the called expression (existing logic)
    call_target = None
    for child in node.children:
        if child.type == "identifier":
            call_target = self._get_node_text(child, ctx.source_bytes)
            break
        elif child.type == "navigation_expression":
            call_target = self._get_node_text(child, ctx.source_bytes)
            break

    if not call_target:
        return

    # Create reference for the call target (existing logic)
    target_path, target_symbol_name = self._resolve_call_target(call_target, ctx)
    source_path, source_name = self._split_scope(ctx.current_scope)
    ctx.add_reference(
        Reference(
            source_file_path=source_path,
            source_symbol_name=source_name,
            target_file_path=target_path,
            target_symbol_name=target_symbol_name,
            reference_type=ReferenceType.CALL,
        )
    )
    
    # 2. NEW: Extract and process arguments
    self._process_call_arguments(node, ctx)

def _process_call_arguments(self, node: Node, ctx: KotlinParseContext) -> None:
    """
    Extract identifiers from call arguments and create references.
    
    For DSL patterns like:
      .process(unlinkedRefundFraudProcessor)
      .filter(myPredicate)
    
    Creates references to the argument classes/variables.
    """
    for child in node.children:
        if child.type == "value_arguments":
            self._extract_argument_identifiers(child, ctx)

def _extract_argument_identifiers(self, node: Node, ctx: KotlinParseContext) -> None:
    """Recursively extract simple_identifier nodes from arguments."""
    if node.type == "simple_identifier":
        identifier_name = self._get_node_text(node, ctx.source_bytes)
        
        # Skip literals, keywords, primitives
        if identifier_name in {"true", "false", "null", "this", "it"}:
            return
        if identifier_name[0].islower() and identifier_name in {"true", "false"}:
            return
            
        # Check if it's a field/parameter with a known type
        if identifier_name in ctx.field_types:
            type_name = ctx.field_types[identifier_name]
            target_path = self._resolve_type_to_path(type_name, ctx)
            
            source_path, source_name = self._split_scope(ctx.current_scope)
            ctx.add_reference(
                Reference(
                    source_file_path=source_path,
                    source_symbol_name=source_name,
                    target_file_path=target_path,
                    target_symbol_name=type_name,
                    reference_type=ReferenceType.USAGE,  # or CALL
                )
            )
    
    # Recurse into children
    for child in node.children:
        self._extract_argument_identifiers(child, ctx)

def _resolve_type_to_path(self, type_name: str, ctx: KotlinParseContext) -> str:
    """Resolve a type name to its full qualified path."""
    # Check imports first
    if type_name in ctx.imports:
        return ctx.imports[type_name]
    
    # Check if it's in the same package
    if ctx.package_name:
        return f"{ctx.package_name}.{type_name}"
    
    # Fall back to just the type name
    return type_name
```

### Expected Result After Fix

```
Downstream nodes for configure():
  1. from (DSL method)
  2. filter (DSL method)
  3. unlinkedRefundPredicate (file: UnlinkedRefundPredicate.kt) ✅
  4. process (DSL method)
  5. unlinkedRefundFraudProcessor (file: UnlinkedRefundFraudProcessor.kt) ✅
  6. to (DSL method)
  7. UnlinkedRefundFraudProducerRoute (file: UnlinkedRefundFraudProducerRoute.kt) ✅
  ...
```

**Now AI can analyze**:
- Processor source code (fraud detection logic)
- Predicate conditions (filter criteria)
- Producer route (where results go)

---

## Testing

1. Parse `UnlinkedRefundFraudCheckerRoute.kt`
2. Query downstream for `configure()` method
3. Verify downstream includes:
   - `unlinkedRefundFraudProcessor` → `UnlinkedRefundFraudProcessor.kt`
   - `unlinkedRefundPredicate` → predicate class file

---

## Priority

**High** - Without this, declarative framework analysis (Camel, Spring DSL, builders) provides no value beyond basic structure.

**Affected frameworks**:
- Apache Camel routes
- Spring Cloud Stream bindings
- Kotlin DSL builders (Exposed, Ktor routing, etc.)
- Any fluent API pattern where logic is in arguments

---

## Alternative: Post-Processing Enhancement

If parser changes are complex, an alternative is to enhance the flow analyzer to:
1. Detect DSL patterns (`process()`, `filter()`, etc.)
2. Parse source code to extract arguments
3. Look up those argument symbols in the database
4. Fetch their files for AI analysis

**Pros**: No parser changes needed  
**Cons**: Hacky, less reliable, doesn't populate call graph properly
