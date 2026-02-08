"""Parser registry for managing language-specific parsers."""

from functools import lru_cache

from code_parser.core import Language
from code_parser.logging import get_logger
from code_parser.parsers.base import LanguageParser
from code_parser.parsers.java_parser import JavaParser
from code_parser.parsers.javascript_parser import JavaScriptParser
from code_parser.parsers.kotlin_parser import KotlinParser
from code_parser.parsers.python_parser import PythonParser
from code_parser.parsers.rust_parser import RustParser

logger = get_logger(__name__)


class ParserRegistry:
    """
    Registry of language-specific parsers.
    
    Provides factory methods for obtaining the appropriate parser
    based on language or file extension.
    """

    def __init__(self) -> None:
        self._parsers: dict[Language, LanguageParser] = {}
        self._extension_map: dict[str, Language] = {}

    def register(self, parser: LanguageParser) -> None:
        """Register a parser for its language."""
        self._parsers[parser.language] = parser
        for ext in parser.file_extensions:
            self._extension_map[ext] = parser.language
        logger.debug(
            "parser_registered",
            language=parser.language.value,
            extensions=list(parser.file_extensions),
        )

    def get_parser(self, language: Language) -> LanguageParser | None:
        """Get parser for a specific language."""
        return self._parsers.get(language)

    def get_parser_for_file(self, file_path: str) -> LanguageParser | None:
        """Get parser based on file extension."""
        ext = self._get_extension(file_path)
        language = self._extension_map.get(ext)
        if language:
            return self._parsers.get(language)
        return None

    def get_language_for_file(self, file_path: str) -> Language | None:
        """Get language based on file extension."""
        ext = self._get_extension(file_path)
        return self._extension_map.get(ext)

    def is_supported(self, file_path: str) -> bool:
        """Check if a file can be parsed."""
        return self.get_parser_for_file(file_path) is not None

    @property
    def supported_languages(self) -> list[Language]:
        """List of all supported languages."""
        return list(self._parsers.keys())

    @property
    def supported_extensions(self) -> list[str]:
        """List of all supported file extensions."""
        return list(self._extension_map.keys())

    def _get_extension(self, file_path: str) -> str:
        """Extract file extension from path."""
        # Handle multiple extensions like .test.py
        parts = file_path.rsplit("/", 1)[-1].split(".")
        if len(parts) >= 2:
            return f".{parts[-1]}"
        return ""


def _create_default_registry() -> ParserRegistry:
    """Create and configure the default parser registry."""
    registry = ParserRegistry()

    # Register all supported parsers
    registry.register(PythonParser())
    registry.register(JavaParser())
    registry.register(JavaScriptParser())
    registry.register(KotlinParser())
    registry.register(RustParser())

    logger.info(
        "parser_registry_initialized",
        languages=[lang.value for lang in registry.supported_languages],
    )

    return registry


@lru_cache
def get_parser_registry() -> ParserRegistry:
    """Get the singleton parser registry instance."""
    return _create_default_registry()

