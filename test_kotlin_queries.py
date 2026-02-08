#!/usr/bin/env python3
"""Test Kotlin tree-sitter queries to validate they work correctly."""

import sys
import tree_sitter_kotlin as ts_kotlin
from tree_sitter import Language, Parser, Query, QueryCursor

# Import queries
from src.code_parser.entry_points.queries.kotlin_queries import get_kotlin_queries

def test_query(query_name: str, query_string: str, test_code: str, expected_matches: list[str] = None):
    """Test a single query against test code."""
    print(f"\n{'='*60}")
    print(f"Testing: {query_name}")
    print(f"{'='*60}")
    
    # Setup parser
    lang = Language(ts_kotlin.language())
    parser = Parser(lang)
    
    # Parse code
    source_bytes = test_code.encode("utf-8")
    tree = parser.parse(source_bytes)
    
    # Compile query
    try:
        query = Query(lang, query_string.strip())
        print(f"✅ Query compiled successfully")
    except Exception as e:
        print(f"❌ Query compilation failed: {e}")
        return False
    
    # Execute query
    cursor = QueryCursor(query)
    matches = cursor.matches(tree.root_node)
    
    match_count = 0
    found_names = []
    
    for match in matches:
        pattern_index, captures_dict = match
        match_count += 1
        
        # Extract captures
        captures = {}
        for capture_name, nodes in captures_dict.items():
            if nodes:
                node = nodes[-1]
                text = source_bytes[node.start_byte:node.end_byte].decode("utf-8")
                captures[capture_name] = text
        
        print(f"  Match {match_count}:")
        for name, text in captures.items():
            print(f"    {name}: {text}")
            if name in ["function_name", "configure_method", "from_method", "class_name"]:
                found_names.append(text)
    
    print(f"\nTotal matches: {match_count}")
    
    if expected_matches:
        print(f"Expected matches: {expected_matches}")
        print(f"Found names: {found_names}")
        success = all(name in found_names for name in expected_matches)
        if success:
            print("✅ All expected matches found")
        else:
            print("❌ Some expected matches missing")
        return success
    
    return True

# Test code samples
CAMEL_ROUTE_CODE = """
package com.toasttab.pipeline.paymentfraudchecker.route

import org.apache.camel.builder.RouteBuilder

class HealthCheckRoute(private val port: Int, private val path: String) : RouteBuilder() {
    override fun configure() {
        from("netty-http:http://0.0.0.0:$port/$path").routeId(HEALTH_CHECK_ROUTE_ID)
            .transform()
            .constant(HEALTH_CHECK_RESPONSE)
    }
}
"""

CAMEL_ROUTE_WITH_FROM = """
class DSFallbackRoute : BaseRouteBuilder() {
    override fun configure() {
        super.configure()
        from(consumer.toURI())
            .routeId(RouteId.DS_FRAUD_CONSUMER_ROUTE.id)
    }
}
"""

SPRING_CONTROLLER_CODE = """
package com.example

import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/api")
class UserController {
    @GetMapping("/users")
    fun getUsers(): List<User> {
        return listOf()
    }
    
    @PostMapping("/users")
    fun createUser(@RequestBody user: User): User {
        return user
    }
}
"""

KTOR_ROUTE_CODE = """
import io.ktor.server.routing.*

fun Application.configureRouting() {
    routing {
        get("/") {
            call.respondText("Hello World!")
        }
        post("/users") {
            // create user
        }
    }
}
"""

def main():
    """Run all query tests."""
    queries = get_kotlin_queries()
    
    print("Testing Kotlin Entry Point Queries")
    print("=" * 60)
    
    results = {}
    
    # Test Camel queries
    print("\n\n=== Testing Apache Camel Queries ===")
    
    results["camel_route_builder_class"] = test_query(
        "camel_route_builder_class",
        queries["camel_route_builder_class"],
        CAMEL_ROUTE_CODE,
        expected_matches=["configure"]  # Should find configure method
    )
    
    results["camel_configure_method"] = test_query(
        "camel_configure_method",
        queries["camel_configure_method"],
        CAMEL_ROUTE_CODE,
        expected_matches=["configure"]  # Should find configure method
    )
    
    results["camel_from_call"] = test_query(
        "camel_from_call",
        queries["camel_from_call"],
        CAMEL_ROUTE_CODE,
        expected_matches=["from"]  # Should find from() call
    )
    
    # Test Spring queries
    print("\n\n=== Testing Spring Boot Queries ===")
    
    results["spring_rest_controller"] = test_query(
        "spring_rest_controller",
        queries["spring_rest_controller"],
        SPRING_CONTROLLER_CODE,
        expected_matches=["getUsers", "createUser"]  # Should find both methods
    )
    
    results["spring_request_mapping"] = test_query(
        "spring_request_mapping",
        queries["spring_request_mapping"],
        SPRING_CONTROLLER_CODE,
        expected_matches=["getUsers", "createUser"]  # Should find both methods
    )
    
    # Test Ktor queries
    print("\n\n=== Testing Ktor Queries ===")
    
    results["ktor_routing"] = test_query(
        "ktor_routing",
        queries["ktor_routing"],
        KTOR_ROUTE_CODE
    )
    
    results["ktor_route"] = test_query(
        "ktor_route",
        queries["ktor_route"],
        KTOR_ROUTE_CODE
    )
    
    # Summary
    print("\n\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All queries validated successfully!")
        return 0
    else:
        print(f"\n❌ {total - passed} queries failed validation")
        return 1

if __name__ == "__main__":
    sys.exit(main())
