"""Tree-sitter query executor for entry point pattern matching."""

from dataclasses import dataclass
from typing import Any

from tree_sitter import Language, Node, Parser, Query, QueryCursor


@dataclass(frozen=True, slots=True)
class QueryMatch:
    """A match from a Tree-sitter query."""

    pattern_index: int  # Which pattern in the query matched
    captures: dict[str, Node]  # Named captures from the query
    node: Node  # The matched node


class QueryExecutor:
    """Executes Tree-sitter queries and extracts matches."""

    def __init__(self, language: Language, parser: Parser) -> None:
        """
        Initialize query executor.
        
        Args:
            language: Tree-sitter Language instance
            parser: Tree-sitter Parser instance
        """
        self._language = language
        self._parser = parser
        self._queries: dict[str, Query] = {}  # Cache compiled queries

    def execute_query(
        self, source_code: str, query_string: str, query_name: str = "unnamed"
    ) -> list[QueryMatch]:
        """
        Execute a Tree-sitter query on source code.
        
        Args:
            source_code: Source code to query
            query_string: S-expression query string
            query_name: Name for caching (optional)
            
        Returns:
            List of QueryMatch objects with captures
        """
        # Parse source code
        source_bytes = source_code.encode("utf-8")
        tree = self._parser.parse(source_bytes)

        # Compile query (with caching)
        if query_name not in self._queries:
            try:
                # Strip leading/trailing whitespace from query string
                cleaned_query = query_string.strip()
                self._queries[query_name] = Query(self._language, cleaned_query)
            except Exception as e:
                raise ValueError(f"Failed to compile query '{query_name}': {e}") from e

        query = self._queries[query_name]

        # Execute query using QueryCursor
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        # Extract matches with captures
        results: list[QueryMatch] = []
        for match in matches:
            # match is a tuple: (pattern_index, captures_dict)
            pattern_index, captures_dict = match
            
            # Build captures dict (already a dict from QueryCursor)
            captures: dict[str, Node] = {}
            for capture_name, nodes in captures_dict.items():
                # Handle multiple captures with same name (take last)
                if nodes:
                    captures[capture_name] = nodes[-1]

            results.append(
                QueryMatch(
                    pattern_index=pattern_index,
                    captures=captures,
                    node=list(captures.values())[0] if captures else tree.root_node,
                )
            )

        return results

    def execute_queries(
        self, source_code: str, queries: dict[str, str]
    ) -> dict[str, list[QueryMatch]]:
        """
        Execute multiple queries on source code.
        
        Args:
            source_code: Source code to query
            queries: Dict mapping query names to query strings
            
        Returns:
            Dict mapping query names to lists of matches
        """
        results: dict[str, list[QueryMatch]] = {}
        for query_name, query_string in queries.items():
            results[query_name] = self.execute_query(source_code, query_string, query_name)
        return results

    def extract_node_text(self, node: Node, source_code: str) -> str:
        """Extract text content from a node."""
        source_bytes = source_code.encode("utf-8")
        start_byte = node.start_byte
        end_byte = node.end_byte
        return source_bytes[start_byte:end_byte].decode("utf-8", errors="replace")

    def extract_node_position(self, node: Node) -> tuple[int, int, int, int]:
        """
        Extract position information from a node.
        
        Returns:
            (start_line, end_line, start_column, end_column)
            Lines are 1-indexed, columns are 0-indexed
        """
        start_point = node.start_point
        end_point = node.end_point

        start_line = start_point[0] + 1  # Convert to 1-indexed
        end_line = end_point[0] + 1
        start_column = start_point[1]
        end_column = end_point[1]

        return (start_line, end_line, start_column, end_column)
