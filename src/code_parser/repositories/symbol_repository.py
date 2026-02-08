"""Repository for managing symbols and references (call graph)."""

from ulid import ULID
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from code_parser.core import ParsedFile, Reference, ReferenceType, Symbol, SymbolKind
from code_parser.database.models import ReferenceModel, SymbolModel


class SymbolRepository:
    """Data access layer for Symbol and Reference entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_insert_from_parsed_file(
        self,
        repo_id: str,
        file_id: str,
        parsed_file: ParsedFile,
    ) -> None:
        """
        Bulk insert symbols and references from a parsed file.
        
        First deletes existing symbols/references for the file,
        then inserts new ones.
        """
        # Delete existing symbols for this file (references cascade)
        await self._session.execute(
            delete(SymbolModel).where(SymbolModel.file_id == file_id)
        )

        # Map qualified names to symbol IDs for reference resolution
        qualified_name_to_id: dict[str, str] = {}

        # Insert symbols with validation
        for symbol in parsed_file.symbols:
            # Validate symbol before insertion
            if not symbol.name or not symbol.qualified_name:
                from code_parser.logging import get_logger
                logger = get_logger(__name__)
                logger.warning(
                    "skipping_invalid_symbol",
                    file_id=file_id,
                    has_name=bool(symbol.name),
                    has_qualified_name=bool(symbol.qualified_name),
                )
                continue
            
            symbol_id = str(ULID())
            qualified_name_to_id[symbol.qualified_name] = symbol_id

            # Find parent symbol ID
            parent_id = None
            if symbol.parent_qualified_name:
                parent_id = qualified_name_to_id.get(symbol.parent_qualified_name)

            model = SymbolModel(
                id=symbol_id,
                file_id=file_id,
                repo_id=repo_id,
                name=symbol.name,
                qualified_name=symbol.qualified_name,
                kind=symbol.kind.value,
                source_code=symbol.source_code,
                signature=symbol.signature,
                parent_symbol_id=parent_id,
                extra_data=dict(symbol.metadata),
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                start_column=symbol.start_column,
                end_column=symbol.end_column,
            )
            self._session.add(model)

        await self._session.flush()

        # Insert references
        for ref in parsed_file.references:
            # Get normalized values using helper methods
            source_path = ref.get_source_path()
            source_name = ref.get_source_name()
            target_path = ref.get_target_path()
            target_name = ref.get_target_name()
            
            # Find source symbol by building its qualified name
            source_qualified = f"{source_path}.{source_name}"
            source_id = qualified_name_to_id.get(source_qualified)
            if not source_id:
                # Try with legacy qualified name if available
                if ref.source_qualified_name:
                    source_id = qualified_name_to_id.get(ref.source_qualified_name)
            if not source_id:
                # Try just the path (for file-level imports)
                source_id = qualified_name_to_id.get(source_path)
            if not source_id:
                # Source symbol not found in this file, skip
                continue

            # Try to resolve target within the same repo
            target_qualified = f"{target_path}.{target_name}"
            target_id = qualified_name_to_id.get(target_qualified)

            ref_model = ReferenceModel(
                id=str(ULID()),
                repo_id=repo_id,
                source_symbol_id=source_id,
                target_symbol_id=target_id,
                source_file_path=source_path,
                source_symbol_name=source_name,
                target_file_path=target_path,
                target_symbol_name=target_name,
                reference_type=ref.reference_type.value,
            )
            self._session.add(ref_model)

        await self._session.flush()

    async def resolve_cross_file_references(self, repo_id: str) -> int:
        """
        Resolve references that point to symbols in other files.
        
        Matches symbols by name where the symbol's file path ends with 
        the reference's target_file_path (converted to slashes).
        """
        # Match symbols by name where file path matches
        # target_file_path: "com.toasttab.service.MyClass" 
        # -> matches file: "...kotlin/com/toasttab/service/MyClass.kt"
        result = await self._session.execute(
            text("""
                UPDATE "references" r
                SET target_symbol_id = (
                    SELECT s.id 
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE s.repo_id = :repo_id
                      AND s.name = r.target_symbol_name
                      AND f.relative_path LIKE '%' || replace(r.target_file_path, '.', '/') || '%'
                    LIMIT 1
                )
                WHERE r.repo_id = :repo_id
                  AND r.target_symbol_id IS NULL
                  AND EXISTS (
                      SELECT 1 
                      FROM symbols s
                      JOIN files f ON s.file_id = f.id
                      WHERE s.repo_id = :repo_id
                        AND s.name = r.target_symbol_name
                        AND f.relative_path LIKE '%' || replace(r.target_file_path, '.', '/') || '%'
                  )
            """),
            {"repo_id": repo_id},
        )
        return result.rowcount

    async def get_symbol_by_id(self, symbol_id: str) -> SymbolModel | None:
        """Get a symbol by ID."""
        result = await self._session.execute(
            select(SymbolModel).where(SymbolModel.id == symbol_id)
        )
        return result.scalar_one_or_none()

    async def get_symbols_by_ids(
        self, symbol_ids: list[str]
    ) -> list[SymbolModel]:
        """Bulk fetch symbols by their IDs."""
        if not symbol_ids:
            return []
        result = await self._session.execute(
            select(SymbolModel).where(SymbolModel.id.in_(symbol_ids))
        )
        return list(result.scalars().all())

    async def get_symbol_by_qualified_name(
        self, repo_id: str, qualified_name: str
    ) -> SymbolModel | None:
        """Get a symbol by its qualified name."""
        result = await self._session.execute(
            select(SymbolModel).where(
                SymbolModel.repo_id == repo_id,
                SymbolModel.qualified_name == qualified_name,
            )
        )
        return result.scalar_one_or_none()

    async def list_symbols(
        self,
        repo_id: str,
        kind: SymbolKind | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SymbolModel]:
        """List symbols in a repository with optional filtering."""
        query = select(SymbolModel).where(SymbolModel.repo_id == repo_id)

        if kind:
            query = query.where(SymbolModel.kind == kind.value)

        query = query.order_by(SymbolModel.qualified_name).limit(limit).offset(offset)

        result = await self._session.execute(query)
        return list(result.scalars())

    async def search_symbols(
        self,
        repo_id: str,
        query: str,
        limit: int = 50,
    ) -> list[SymbolModel]:
        """Search symbols by name (prefix match)."""
        result = await self._session.execute(
            select(SymbolModel)
            .where(
                SymbolModel.repo_id == repo_id,
                SymbolModel.name.ilike(f"{query}%"),
            )
            .order_by(SymbolModel.name)
            .limit(limit)
        )
        return list(result.scalars())

    async def get_downstream(
        self,
        symbol_id: str,
        max_depth: int = 5,
    ) -> list[dict]:
        """
        Get downstream symbols (what this symbol calls).
        
        Returns symbols that are called by the given symbol,
        traversing the call graph up to max_depth levels.
        
        For external references, includes target_file_path and target_symbol_name
        for direct use with get_symbol_details API.
        """
        result = await self._session.execute(
            text("""
                WITH RECURSIVE downstream AS (
                    SELECT 
                        r.target_symbol_id as symbol_id,
                        r.target_file_path,
                        r.target_symbol_name,
                        r.reference_type,
                        1 as depth
                    FROM "references" r
                    WHERE r.source_symbol_id = :symbol_id
                    
                    UNION ALL
                    
                    SELECT 
                        r.target_symbol_id,
                        r.target_file_path,
                        r.target_symbol_name,
                        r.reference_type,
                        d.depth + 1
                    FROM "references" r
                    JOIN downstream d ON r.source_symbol_id = d.symbol_id
                    WHERE d.depth < :max_depth
                      AND d.symbol_id IS NOT NULL
                )
                SELECT DISTINCT
                    s.id,
                    s.name,
                    s.qualified_name,
                    s.kind,
                    s.source_code,
                    s.signature,
                    d.depth,
                    d.reference_type,
                    d.target_file_path,
                    d.target_symbol_name
                FROM downstream d
                LEFT JOIN symbols s ON d.symbol_id = s.id
                ORDER BY d.depth, s.qualified_name
            """),
            {"symbol_id": symbol_id, "max_depth": max_depth},
        )

        return [
            {
                "id": row.id,
                "name": row.name or row.target_symbol_name,
                "qualified_name": row.qualified_name,
                "kind": row.kind,
                "source_code": row.source_code,
                "signature": row.signature,
                "depth": row.depth,
                "reference_type": row.reference_type,
                "target_file_path": row.target_file_path,
                "target_symbol_name": row.target_symbol_name,
            }
            for row in result
        ]

    async def get_upstream(
        self,
        symbol_id: str,
        max_depth: int = 5,
    ) -> list[dict]:
        """
        Get upstream symbols (what calls this symbol).
        
        Returns symbols that call the given symbol,
        traversing the call graph up to max_depth levels.
        """
        result = await self._session.execute(
            text("""
                WITH RECURSIVE upstream AS (
                    SELECT 
                        r.source_symbol_id as symbol_id,
                        r.reference_type,
                        1 as depth
                    FROM "references" r
                    WHERE r.target_symbol_id = :symbol_id
                    
                    UNION ALL
                    
                    SELECT 
                        r.source_symbol_id,
                        r.reference_type,
                        u.depth + 1
                    FROM "references" r
                    JOIN upstream u ON r.target_symbol_id = u.symbol_id
                    WHERE u.depth < :max_depth
                )
                SELECT DISTINCT
                    s.id,
                    s.name,
                    s.qualified_name,
                    s.kind,
                    s.source_code,
                    s.signature,
                    u.depth,
                    u.reference_type
                FROM upstream u
                JOIN symbols s ON u.symbol_id = s.id
                ORDER BY u.depth, s.qualified_name
            """),
            {"symbol_id": symbol_id, "max_depth": max_depth},
        )

        return [
            {
                "id": row.id,
                "name": row.name,
                "qualified_name": row.qualified_name,
                "kind": row.kind,
                "source_code": row.source_code,
                "signature": row.signature,
                "depth": row.depth,
                "reference_type": row.reference_type,
            }
            for row in result
        ]

    async def get_symbols_in_file(self, file_id: str) -> list[SymbolModel]:
        """Get all symbols defined in a file."""
        result = await self._session.execute(
            select(SymbolModel)
            .where(SymbolModel.file_id == file_id)
            .order_by(SymbolModel.qualified_name)
        )
        return list(result.scalars())

    async def get_stats(self, repo_id: str) -> dict:
        """Get symbol statistics for a repository."""
        # Total count
        total_result = await self._session.execute(
            text("SELECT COUNT(*) FROM symbols WHERE repo_id = :repo_id"),
            {"repo_id": repo_id},
        )
        total = total_result.scalar() or 0

        # Count by kind
        by_kind_result = await self._session.execute(
            text("""
                SELECT kind, COUNT(*) as count 
                FROM symbols 
                WHERE repo_id = :repo_id 
                GROUP BY kind 
                ORDER BY count DESC
            """),
            {"repo_id": repo_id},
        )
        by_kind = {row.kind: row.count for row in by_kind_result}

        # Count by language (from files)
        by_lang_result = await self._session.execute(
            text("""
                SELECT f.language, COUNT(s.id) as count
                FROM files f
                LEFT JOIN symbols s ON f.id = s.file_id
                WHERE f.repo_id = :repo_id
                GROUP BY f.language
                ORDER BY count DESC
            """),
            {"repo_id": repo_id},
        )
        by_language = {row.language: row.count for row in by_lang_result}

        return {
            "total": total,
            "by_kind": by_kind,
            "by_language": by_language,
        }

    async def get_symbols_by_path_and_name(
        self,
        repo_id: str,
        path_pattern: str,
        symbol_name: str,
    ) -> list[dict]:
        """
        Get all symbols matching file path pattern and symbol name.
        
        First searches files by path pattern, then joins symbols.
        This is more efficient than searching symbols table directly.
        
        Args:
            repo_id: Repository ID
            path_pattern: Can be either:
                - Package path (e.g., 'com.toasttab.service.Example') - will convert . to /
                - File path (e.g., 'src/main/kotlin/.../Example.kt') - used directly
            symbol_name: Name of the symbol (method, class, etc.)
        
        Returns:
            List of matching symbols with file info. Empty list if none found.
        """
        # Detect if it's a file path (contains /) or package path (dots only)
        if "/" in path_pattern:
            # It's already a file path - use directly
            file_path_pattern = "%" + path_pattern + "%"
        else:
            # It's a package path - convert dots to slashes
            # e.g., 'com.toasttab.service.MerchantService' -> '%com/toasttab/service/MerchantService%'
            file_path_pattern = "%" + path_pattern.replace(".", "/") + "%"
        
        # First filter files, then join symbols (more efficient)
        result = await self._session.execute(
            text("""
                WITH matching_files AS (
                    SELECT id, relative_path, language
                    FROM files
                    WHERE repo_id = :repo_id
                      AND relative_path LIKE :file_path_pattern
                )
                SELECT 
                    s.id,
                    s.name,
                    s.qualified_name,
                    s.kind,
                    s.source_code,
                    s.signature,
                    s.parent_symbol_id,
                    s.extra_data,
                    f.id as file_id,
                    f.relative_path,
                    f.language
                FROM matching_files f
                JOIN symbols s ON s.file_id = f.id
                WHERE s.name = :symbol_name
                ORDER BY f.relative_path
            """),
            {
                "repo_id": repo_id,
                "symbol_name": symbol_name,
                "file_path_pattern": file_path_pattern,
            },
        )
        
        return [
            {
                "id": row.id,
                "name": row.name,
                "qualified_name": row.qualified_name,
                "kind": row.kind,
                "source_code": row.source_code,
                "signature": row.signature,
                "parent_symbol_id": row.parent_symbol_id,
                "extra_data": row.extra_data,
                "file_id": row.file_id,
                "relative_path": row.relative_path,
                "language": row.language,
            }
            for row in result
        ]

    async def get_symbol_details_with_context(
        self,
        repo_id: str,
        path_pattern: str,
        symbol_name: str,
        depth: int = 0,
    ) -> list[dict]:
        """
        Get symbol details with optional upstream/downstream context.
        
        Returns all matching symbols (could be multiple if same path exists
        in different modules).
        
        Args:
            repo_id: Repository ID
            path_pattern: Package path pattern (e.g., 'com.toasttab.service.Example')
            symbol_name: Name of the symbol
            depth: Context depth (0 = symbol only, 1+ = include upstream/downstream)
        
        Returns:
            List of results, each containing symbol + upstream + downstream.
            Empty list if no symbols found.
        """
        # Find all matching symbols
        symbols = await self.get_symbols_by_path_and_name(repo_id, path_pattern, symbol_name)
        
        if not symbols:
            return []
        
        results = []
        for symbol in symbols:
            result = {
                "symbol": symbol,
                "upstream": [],
                "downstream": [],
            }
            
            # If depth > 0, get upstream and downstream
            if depth > 0:
                result["upstream"] = await self.get_upstream(symbol["id"], max_depth=depth)
                result["downstream"] = await self.get_downstream(symbol["id"], max_depth=depth)
            
            results.append(result)
        
        return results