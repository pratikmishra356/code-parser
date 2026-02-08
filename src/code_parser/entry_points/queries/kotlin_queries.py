"""Tree-sitter query patterns for Kotlin entry point detection.

These queries are designed to be universal and work across different repositories,
detecting entry points for HTTP endpoints, event handlers, and schedulers in
various Kotlin frameworks.
"""

from typing import Dict


# ============ HTTP Endpoints ============

# Spring Boot REST Controllers - matches classes annotated with @RestController or @Controller
# and methods annotated with HTTP mapping annotations (@GetMapping, @PostMapping, etc.)
SPRING_REST_CONTROLLER_QUERY = """
(class_declaration
  (modifiers
    (annotation
      (user_type
        (identifier) @controller_annotation)))
  (class_body
    (function_declaration
      (modifiers
        (annotation
          (user_type
            (identifier) @mapping_annotation)))
      name: (identifier) @function_name)))
"""

# Spring Boot Request Mapping - matches any method with HTTP mapping annotations
# This is more flexible and catches methods even outside @RestController classes
# Note: Kotlin annotations can be simple (user_type) or with args (constructor_invocation)
SPRING_REQUEST_MAPPING_QUERY = """
(function_declaration
  (modifiers
    (annotation
      [
        (user_type
          (identifier) @mapping_annotation)
        (constructor_invocation
          (user_type
            (identifier) @mapping_annotation))
      ]))
  name: (identifier) @function_name)
"""

# Jersey/JAX-RS Resource Methods - matches methods annotated with @Path and HTTP method annotations (@GET, @POST, etc.)
# These are the actual HTTP endpoints, not the resource class registration
JAX_RS_RESOURCE_METHOD_QUERY = """
(function_declaration
  (modifiers
    (annotation
      [
        (user_type
          (identifier) @http_method_annotation)
        (constructor_invocation
          (user_type
            (identifier) @http_method_annotation))
      ])
    (annotation
      [
        (user_type
          (identifier) @path_annotation)
        (constructor_invocation
          (user_type
            (identifier) @path_annotation))
      ])?)
  name: (identifier) @function_name)
"""

# Jersey/JAX-RS Resource Methods - matches methods with @Path annotation (may have HTTP method annotation too)
JAX_RS_PATH_METHOD_QUERY = """
(function_declaration
  (modifiers
    (annotation
      [
        (user_type
          (identifier) @path_annotation)
        (constructor_invocation
          (user_type
            (identifier) @path_annotation))
      ])
    (annotation
      [
        (user_type
          (identifier) @http_method_annotation)
        (constructor_invocation
          (user_type
            (identifier) @http_method_annotation))
      ])?)
  name: (identifier) @function_name)
"""

# Ktor routing - matches routing DSL calls (routing { get { ... } })
KTOR_ROUTING_QUERY = """
(call_expression
  (identifier) @routing_function
  (lambda_literal
    (call_expression
      (identifier) @http_method))?)
"""

# Ktor route definitions - matches route() calls with HTTP methods (get, post, etc.)
KTOR_ROUTE_QUERY = """
(call_expression
  (navigation_expression
    (identifier) @router_object
    (identifier) @http_method))
"""

# ============ Event Handlers - Apache Camel ============

# Apache Camel RouteBuilder classes - matches classes with any method
# We filter by method name == "configure" in the service layer
# This is more universal and avoids complex delegation_specifiers matching
CAMEL_ROUTE_BUILDER_CLASS_QUERY = """
(class_declaration
  name: (identifier) @class_name
  (class_body
    (function_declaration
      name: (identifier) @configure_method)))
"""

# Apache Camel configure() method - matches any function_declaration
# We filter by function name == "configure" in the service layer
# This is simpler and more reliable than trying to match nested structures
CAMEL_CONFIGURE_METHOD_QUERY = """
(function_declaration
  name: (identifier) @function_name)
"""

# Apache Camel from() call - matches any call_expression
# We filter by method name == "from" in the service layer
# This is intentionally broad - filtering ensures we only get actual "from()" calls
CAMEL_FROM_CALL_QUERY = """
(call_expression
  (identifier) @from_method)
"""

# ============ Event Handlers - Messaging ============

# Kafka Consumer - matches methods annotated with @KafkaListener
KAFKA_LISTENER_QUERY = """
(function_declaration
  (modifiers
    (annotation
      [
        (user_type
          (identifier) @kafka_annotation)
        (constructor_invocation
          (user_type
            (identifier) @kafka_annotation))
      ]))
  name: (identifier) @function_name)
"""

# Pulsar Consumer - matches Pulsar consumer patterns
# Can be via annotations or direct consumer setup
PULSAR_CONSUMER_QUERY = """
(function_declaration
  (modifiers
    (annotation
      [
        (user_type
          (identifier) @pulsar_annotation)
        (constructor_invocation
          (user_type
            (identifier) @pulsar_annotation))
      ]))
  name: (identifier) @function_name)
"""

# ============ Schedulers ============

# Spring @Scheduled annotation - matches methods annotated with @Scheduled
# Note: annotation value_arguments contains value_argument nodes
SPRING_SCHEDULED_QUERY = """
(function_declaration
  (modifiers
    (annotation
      (constructor_invocation
        (user_type
          (identifier) @scheduled_annotation)
        (value_arguments
          (value_argument
            (identifier) @schedule_param
            (string_literal) @schedule_value))?)))
  name: (identifier) @function_name)
"""

# Quartz Job - matches classes with execute() method
# We match execute() method directly rather than checking inheritance
QUARTZ_JOB_QUERY = """
(class_declaration
  name: (identifier) @class_name
  (class_body
    (function_declaration
      name: (identifier) @execute_method)))
"""

# ============ Universal Patterns ============

# Generic route class pattern - matches any class with "Route" in name
# This is a fallback to catch route classes that might not match specific patterns
CAMEL_ROUTE_CLASS_PATTERN_QUERY = """
(class_declaration
  name: (identifier) @class_name
  (class_body
    (function_declaration
      name: (identifier) @function_name)))
"""


def get_kotlin_queries() -> Dict[str, str]:
    """
    Get all Kotlin entry point query patterns.
    
    These queries are designed to be universal and work across different repositories.
    They detect entry points for:
    - HTTP endpoints (Spring Boot, Ktor)
    - Event handlers (Apache Camel, Kafka, Pulsar)
    - Schedulers (Spring @Scheduled, Quartz)
    
    Returns:
        Dict mapping query names to query strings
    """
    return {
        # HTTP endpoints
        # Note: spring_rest_controller query temporarily disabled due to tree-sitter syntax error
        # spring_request_mapping should catch individual HTTP methods anyway
        # "spring_rest_controller": SPRING_REST_CONTROLLER_QUERY,
        "spring_request_mapping": SPRING_REQUEST_MAPPING_QUERY,
        "jax_rs_resource_method": JAX_RS_RESOURCE_METHOD_QUERY,
        "jax_rs_path_method": JAX_RS_PATH_METHOD_QUERY,
        "ktor_routing": KTOR_ROUTING_QUERY,
        "ktor_route": KTOR_ROUTE_QUERY,
        # Event handlers - Apache Camel (most specific to least specific)
        "camel_route_builder_class": CAMEL_ROUTE_BUILDER_CLASS_QUERY,
        "camel_configure_method": CAMEL_CONFIGURE_METHOD_QUERY,
        "camel_from_call": CAMEL_FROM_CALL_QUERY,
        # Event handlers - Messaging
        "kafka_listener": KAFKA_LISTENER_QUERY,
        "pulsar_consumer": PULSAR_CONSUMER_QUERY,
        # Schedulers
        "spring_scheduled": SPRING_SCHEDULED_QUERY,
        "quartz_job": QUARTZ_JOB_QUERY,
    }
