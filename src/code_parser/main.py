"""Application entry point."""

import uvicorn

from code_parser.api.app import create_app
from code_parser.config import get_settings


def run() -> None:
    """Run the application using uvicorn."""
    settings = get_settings()

    uvicorn.run(
        "code_parser.api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=settings.debug,
    )


# For direct execution
if __name__ == "__main__":
    run()

