"""API route modules."""

from code_parser.api.routes.entry_points import router as entry_points_router
from code_parser.api.routes.explore import router as explore_router
from code_parser.api.routes.graph import router as graph_router
from code_parser.api.routes.health import router as health_router
from code_parser.api.routes.orgs import router as orgs_router
from code_parser.api.routes.repositories import router as repositories_router
from code_parser.api.routes.symbols import router as symbols_router

__all__ = [
    "entry_points_router",
    "explore_router",
    "graph_router",
    "health_router",
    "orgs_router",
    "repositories_router",
    "symbols_router",
]

