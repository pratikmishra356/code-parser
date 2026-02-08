"""Tree-sitter query patterns for Python entry point detection."""

from typing import Dict


# Flask route patterns - simplified to avoid "Impossible pattern" errors
FLASK_ROUTE_QUERY = """
(decorated_definition
  (decorator
    (call
      function: (attribute
        object: (identifier) @app_var
        attribute: (identifier) @method)
      arguments: (argument_list
        (string) @path)))
  definition: (function_definition
    name: (identifier) @function_name))
"""

FLASK_BLUEPRINT_ROUTE_QUERY = """
(decorated_definition
  (decorator
    (call
      function: (attribute
        object: (attribute
          object: (identifier) @blueprint_var
          attribute: (identifier) @blueprint_attr)
        attribute: (identifier) @method)
      arguments: (argument_list
        (string) @path)))
  definition: (function_definition
    name: (identifier) @function_name))
"""

# FastAPI route patterns
FASTAPI_ROUTE_QUERY = """
(decorated_definition
  (decorator
    (call
      function: (identifier) @method
      arguments: (argument_list
        (string) @path)))
  definition: (function_definition
    name: (identifier) @function_name))
"""

FASTAPI_ROUTER_QUERY = """
(decorated_definition
  (decorator
    (call
      function: (attribute
        object: (identifier) @router_var
        attribute: (identifier) @method)
      arguments: (argument_list
        (string) @path)))
  definition: (function_definition
    name: (identifier) @function_name))
"""

FASTAPI_WEBSOCKET_QUERY = """
(decorated_definition
  (decorator
    (call
      function: (attribute
        object: (identifier) @app_var
        attribute: (identifier) @websocket_method)
      arguments: (argument_list
        (string) @path)))
  definition: (function_definition
    name: (identifier) @function_name))
"""

# Django REST Framework patterns
DJANGO_API_VIEW_QUERY = """
(decorated_definition
  (decorator
    (call
      function: (identifier) @api_view_decorator))
  definition: (function_definition
    name: (identifier) @function_name))
"""

DJANGO_VIEWSET_ACTION_QUERY = """
(decorated_definition
  (decorator
    (call
      function: (identifier) @action_decorator
      arguments: (argument_list
        (string) @path)))
  definition: (function_definition
    name: (identifier) @function_name))
"""

# Event handler patterns
CELERY_TASK_QUERY = """
(decorated_definition
  (decorator
    (call
      function: (attribute
        object: (identifier) @celery_var
        attribute: (identifier) @task_method)))
  definition: (function_definition
    name: (identifier) @function_name))
"""

KAFKA_CONSUMER_QUERY = """
(decorated_definition
  (decorator
    (call
      function: (identifier) @kafka_consumer))
  definition: (function_definition
    name: (identifier) @function_name))
"""

PULSAR_SUBSCRIBE_QUERY = """
(decorated_definition
  (decorator
    (call
      function: (attribute
        object: (identifier) @pulsar_var
        attribute: (identifier) @subscribe_method)
      arguments: (argument_list
        (string) @topic)))
  definition: (function_definition
    name: (identifier) @function_name))
"""

# Scheduler patterns
SCHEDULED_DECORATOR_QUERY = """
(decorated_definition
  (decorator
    (call
      function: (identifier) @scheduled_decorator
      arguments: (argument_list
        (keyword_argument
          argument: (identifier) @schedule_kw
          value: (string) @schedule_value))))
  definition: (function_definition
    name: (identifier) @function_name))
"""

CRON_DECORATOR_QUERY = """
(decorated_definition
  (decorator
    (call
      function: (identifier) @cron_decorator
      arguments: (argument_list
        (string) @cron_expression)))
  definition: (function_definition
    name: (identifier) @function_name))
"""

APSCHEDULER_QUERY = """
(call
  function: (attribute
    object: (identifier) @scheduler_var
    attribute: (identifier) @scheduler_method)
  arguments: (argument_list
    (string) @schedule_string
    (identifier) @function_ref))
"""


def get_python_queries() -> Dict[str, str]:
    """
    Get all Python entry point query patterns.
    
    Returns:
        Dict mapping query names to query strings
    """
    return {
        # HTTP endpoints
        "flask_route": FLASK_ROUTE_QUERY,
        "flask_blueprint_route": FLASK_BLUEPRINT_ROUTE_QUERY,
        "fastapi_route": FASTAPI_ROUTE_QUERY,
        "fastapi_router": FASTAPI_ROUTER_QUERY,
        "fastapi_websocket": FASTAPI_WEBSOCKET_QUERY,
        "django_api_view": DJANGO_API_VIEW_QUERY,
        "django_viewset_action": DJANGO_VIEWSET_ACTION_QUERY,
        # Event handlers
        "celery_task": CELERY_TASK_QUERY,
        "kafka_consumer": KAFKA_CONSUMER_QUERY,
        "pulsar_subscribe": PULSAR_SUBSCRIBE_QUERY,
        # Schedulers
        "scheduled_decorator": SCHEDULED_DECORATOR_QUERY,
        "cron_decorator": CRON_DECORATOR_QUERY,
        "apscheduler": APSCHEDULER_QUERY,
    }
