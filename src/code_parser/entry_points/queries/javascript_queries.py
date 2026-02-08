"""Tree-sitter query patterns for JavaScript entry point detection."""

from typing import Dict


# Express.js routes
EXPRESS_ROUTE_QUERY = """
(call_expression
  function: (member_expression
    object: (identifier) @app_var
    property: (property_identifier) @method)
  arguments: (arguments
    (string) @path
    (arrow_function
      (identifier) @handler_name)?))
"""

# Next.js API routes
NEXTJS_API_ROUTE_QUERY = """
(export_statement
  (function_declaration
    name: (identifier) @handler_name))
"""

# AWS Lambda handlers
LAMBDA_HANDLER_QUERY = """
(export_statement
  (variable_declaration
    (variable_declarator
      name: (identifier) @handler_name
      value: (arrow_function | function))))
"""


def get_javascript_queries() -> Dict[str, str]:
    """
    Get all JavaScript entry point query patterns.
    
    Returns:
        Dict mapping query names to query strings
    """
    return {
        # HTTP endpoints
        "express_route": EXPRESS_ROUTE_QUERY,
        "nextjs_api_route": NEXTJS_API_ROUTE_QUERY,
        # Event handlers
        "lambda_handler": LAMBDA_HANDLER_QUERY,
    }
