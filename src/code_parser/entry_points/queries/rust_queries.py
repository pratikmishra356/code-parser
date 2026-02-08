"""Tree-sitter query patterns for Rust entry point detection."""

from typing import Dict


# Actix-web handlers
ACTIX_GET_QUERY = """
(function_item
  (attribute_item
    (attribute
      (identifier) @get_attribute))
  name: (identifier) @function_name)
"""

ACTIX_POST_QUERY = """
(function_item
  (attribute_item
    (attribute
      (identifier) @post_attribute))
  name: (identifier) @function_name)
"""

# Rocket handlers
ROCKET_GET_QUERY = """
(function_item
  (attribute_item
    (attribute
      (identifier) @rocket_get))
  name: (identifier) @function_name)
"""


def get_rust_queries() -> Dict[str, str]:
    """
    Get all Rust entry point query patterns.
    
    Returns:
        Dict mapping query names to query strings
    """
    return {
        # HTTP endpoints
        "actix_get": ACTIX_GET_QUERY,
        "actix_post": ACTIX_POST_QUERY,
        "rocket_get": ROCKET_GET_QUERY,
    }
