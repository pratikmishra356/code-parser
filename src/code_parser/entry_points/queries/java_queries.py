"""Tree-sitter query patterns for Java entry point detection."""

from typing import Dict


# Spring Boot REST controller patterns
# In Java tree-sitter: @RestController (no args) = marker_annotation, @GetMapping("/path") = annotation
# Both are direct children of modifiers
SPRING_REST_CONTROLLER_QUERY = """
(class_declaration
  (modifiers
    (marker_annotation
      (identifier) @rest_controller))
  name: (identifier) @class_name)
"""

# Spring request mapping - matches methods with HTTP mapping annotations
# Handles both marker_annotation (no args) and annotation (with args)
SPRING_REQUEST_MAPPING_QUERY = """
(method_declaration
  (modifiers
    [
      (marker_annotation
        (identifier) @mapping_annotation)
      (annotation
        (identifier) @mapping_annotation)
    ])
  name: (identifier) @method_name)
"""

# Jersey/JAX-RS Resource Methods - matches methods annotated with HTTP method annotations
JAX_RS_RESOURCE_METHOD_QUERY = """
(method_declaration
  (modifiers
    [
      (marker_annotation
        (identifier) @http_method_annotation)
      (annotation
        (identifier) @http_method_annotation)
    ])
  name: (identifier) @method_name)
"""

# Jersey/JAX-RS Path Methods - matches methods annotated with @Path
JAX_RS_PATH_METHOD_QUERY = """
(method_declaration
  (modifiers
    [
      (marker_annotation
        (identifier) @path_annotation)
      (annotation
        (identifier) @path_annotation)
    ])
  name: (identifier) @method_name)
"""

# Event handlers
KAFKA_LISTENER_QUERY = """
(method_declaration
  (modifiers
    [
      (marker_annotation
        (identifier) @kafka_listener)
      (annotation
        (identifier) @kafka_listener)
    ])
  name: (identifier) @method_name)
"""

# Schedulers
SCHEDULED_ANNOTATION_QUERY = """
(method_declaration
  (modifiers
    [
      (marker_annotation
        (identifier) @scheduled)
      (annotation
        (identifier) @scheduled)
    ])
  name: (identifier) @method_name)
"""


def get_java_queries() -> Dict[str, str]:
    """
    Get all Java entry point query patterns.
    
    Returns:
        Dict mapping query names to query strings
    """
    return {
        # HTTP endpoints
        "spring_rest_controller": SPRING_REST_CONTROLLER_QUERY,
        "spring_request_mapping": SPRING_REQUEST_MAPPING_QUERY,
        "jax_rs_resource_method": JAX_RS_RESOURCE_METHOD_QUERY,
        "jax_rs_path_method": JAX_RS_PATH_METHOD_QUERY,
        # Event handlers
        "kafka_listener": KAFKA_LISTENER_QUERY,
        # Schedulers
        "scheduled_annotation": SCHEDULED_ANNOTATION_QUERY,
    }
