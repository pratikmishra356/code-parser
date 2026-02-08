"""Base parser abstraction for language-specific implementations."""

from abc import ABC, abstractmethod

from code_parser.core import Language, ParsedFile, Reference, Symbol


class LanguageParser(ABC):
    """
    Abstract base class for language-specific parsers.
    
    Each implementation uses tree-sitter to parse source code
    and extract symbols (functions, classes, etc.) and references
    (calls, imports, inheritance).
    """

    @property
    @abstractmethod
    def language(self) -> Language:
        """The programming language this parser handles."""
        ...

    @property
    @abstractmethod
    def file_extensions(self) -> frozenset[str]:
        """File extensions this parser can handle (e.g., {'.py'})."""
        ...

    @abstractmethod
    def parse(self, source_code: str, file_path: str, content_hash: str) -> ParsedFile:
        """
        Parse source code and extract symbols and references.
        
        Args:
            source_code: The raw source code content.
            file_path: Relative path of the file (used for qualified names).
            content_hash: SHA-256 hash of the content.
            
        Returns:
            ParsedFile containing extracted symbols and references.
        """
        ...

    def _build_qualified_name(self, file_path: str, *parts: str) -> str:
        """
        Build a qualified name from file path and symbol parts.
        
        Example: "src/utils/helpers.py" + "MyClass" + "my_method"
                 -> "src.utils.helpers.MyClass.my_method"
        """
        # Convert file path to module-like notation
        module_path = file_path.replace("/", ".").replace("\\", ".")
        # Remove extension
        for ext in self.file_extensions:
            if module_path.endswith(ext):
                module_path = module_path[: -len(ext)]
                break

        if parts:
            return f"{module_path}.{'.'.join(parts)}"
        return module_path

    def _extract_node_text(self, node: object, source_bytes: bytes) -> str:
        """Extract text content from a tree-sitter node."""
        # tree-sitter nodes have start_byte and end_byte attributes
        start = getattr(node, "start_byte", 0)
        end = getattr(node, "end_byte", len(source_bytes))
        return source_bytes[start:end].decode("utf-8", errors="replace")
    
    def _extract_position(self, node: object) -> tuple[int | None, int | None, int | None, int | None]:
        """
        Extract position information from a tree-sitter node.
        
        Returns (start_line, end_line, start_column, end_column).
        Lines are 1-indexed, columns are 0-indexed (tree-sitter convention).
        """
        start_point = getattr(node, "start_point", None)
        end_point = getattr(node, "end_point", None)
        
        if start_point is None or end_point is None:
            return (None, None, None, None)
        
        # tree-sitter points are (row, column) where row is 0-indexed
        # We convert to 1-indexed lines
        start_line = start_point[0] + 1 if start_point[0] is not None else None
        end_line = end_point[0] + 1 if end_point[0] is not None else None
        start_column = start_point[1] if start_point[1] is not None else None
        end_column = end_point[1] if end_point[1] is not None else None
        
        return (start_line, end_line, start_column, end_column)


class ParseContext:
    """
    Context object passed during parsing to accumulate results.
    
    Mutable container that parsers use to collect symbols and references
    as they traverse the AST.
    """

    def __init__(self, file_path: str, source_bytes: bytes) -> None:
        self.file_path = file_path
        self.source_bytes = source_bytes
        self.symbols: list[Symbol] = []
        self.references: list[Reference] = []
        self.errors: list[str] = []
        self._symbol_stack: list[str] = []  # Stack of parent qualified names

    def push_scope(self, qualified_name: str) -> None:
        """Enter a nested scope (class, function)."""
        self._symbol_stack.append(qualified_name)

    def pop_scope(self) -> str | None:
        """Exit the current scope."""
        return self._symbol_stack.pop() if self._symbol_stack else None

    @property
    def current_scope(self) -> str | None:
        """Get the current enclosing scope's qualified name."""
        return self._symbol_stack[-1] if self._symbol_stack else None

    def add_symbol(self, symbol: Symbol) -> None:
        """Add an extracted symbol."""
        self.symbols.append(symbol)

    def add_reference(self, reference: Reference) -> None:
        """Add an extracted reference."""
        self.references.append(reference)

    def add_error(self, message: str) -> None:
        """Record a parsing error."""
        self.errors.append(message)

