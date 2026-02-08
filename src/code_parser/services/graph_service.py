"""Graph query service for call graph traversal."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from code_parser.core import SymbolKind
from code_parser.repositories import SymbolRepository


@dataclass(frozen=True, slots=True)
class GraphNode:
    """A node in the call graph."""

    id: str
    name: str
    qualified_name: str
    kind: str | None
    source_code: str | None
    signature: str | None
    depth: int
    reference_type: str


@dataclass(frozen=True, slots=True)
class GraphQueryResult:
    """Result of a graph traversal query."""

    root_symbol_id: str
    root_qualified_name: str
    nodes: list[GraphNode]
    total_count: int


class GraphService:
    """
    Service for querying the call graph.
    
    Provides methods to traverse upstream (callers) and
    downstream (callees) from any symbol.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._symbol_repository = SymbolRepository(session)

    async def get_downstream(
        self,
        repo_id: str,
        symbol_id: str,
        max_depth: int = 5,
    ) -> GraphQueryResult:
        """
        Get downstream call graph (what this symbol calls).
        
        Traverses the call graph from the given symbol to find
        all symbols it calls, directly or indirectly.
        """
        # Verify symbol exists
        symbol = await self._symbol_repository.get_symbol_by_id(symbol_id)
        if not symbol:
            raise ValueError(f"Symbol not found: {symbol_id}")

        if symbol.repo_id != repo_id:
            raise ValueError("Symbol does not belong to the specified repository")

        # Query downstream graph
        raw_results = await self._symbol_repository.get_downstream(
            symbol_id, max_depth
        )

        nodes = [
            GraphNode(
                id=row["id"] or "",
                name=row["name"] or row["qualified_name"].split(".")[-1],
                qualified_name=row["qualified_name"],
                kind=row["kind"],
                source_code=row["source_code"],
                signature=row["signature"],
                depth=row["depth"],
                reference_type=row["reference_type"],
            )
            for row in raw_results
        ]

        return GraphQueryResult(
            root_symbol_id=symbol_id,
            root_qualified_name=symbol.qualified_name,
            nodes=nodes,
            total_count=len(nodes),
        )

    async def get_upstream(
        self,
        repo_id: str,
        symbol_id: str,
        max_depth: int = 5,
    ) -> GraphQueryResult:
        """
        Get upstream call graph (what calls this symbol).
        
        Traverses the call graph backwards from the given symbol
        to find all symbols that call it, directly or indirectly.
        """
        # Verify symbol exists
        symbol = await self._symbol_repository.get_symbol_by_id(symbol_id)
        if not symbol:
            raise ValueError(f"Symbol not found: {symbol_id}")

        if symbol.repo_id != repo_id:
            raise ValueError("Symbol does not belong to the specified repository")

        # Query upstream graph
        raw_results = await self._symbol_repository.get_upstream(
            symbol_id, max_depth
        )

        nodes = [
            GraphNode(
                id=row["id"],
                name=row["name"],
                qualified_name=row["qualified_name"],
                kind=row["kind"],
                source_code=row["source_code"],
                signature=row["signature"],
                depth=row["depth"],
                reference_type=row["reference_type"],
            )
            for row in raw_results
        ]

        return GraphQueryResult(
            root_symbol_id=symbol_id,
            root_qualified_name=symbol.qualified_name,
            nodes=nodes,
            total_count=len(nodes),
        )

    async def get_symbol_context(
        self,
        repo_id: str,
        symbol_id: str,
        upstream_depth: int = 2,
        downstream_depth: int = 2,
    ) -> dict:
        """
        Get full context for a symbol: both callers and callees.
        
        Useful for understanding how a symbol fits into the
        larger codebase architecture.
        """
        symbol = await self._symbol_repository.get_symbol_by_id(symbol_id)
        if not symbol:
            raise ValueError(f"Symbol not found: {symbol_id}")

        if symbol.repo_id != repo_id:
            raise ValueError("Symbol does not belong to the specified repository")

        upstream = await self.get_upstream(repo_id, symbol_id, upstream_depth)
        downstream = await self.get_downstream(repo_id, symbol_id, downstream_depth)

        return {
            "symbol": {
                "id": symbol.id,
                "name": symbol.name,
                "qualified_name": symbol.qualified_name,
                "kind": symbol.kind,
                "source_code": symbol.source_code,
                "signature": symbol.signature,
            },
            "upstream": {
                "nodes": [
                    {
                        "id": n.id,
                        "name": n.name,
                        "qualified_name": n.qualified_name,
                        "kind": n.kind,
                        "depth": n.depth,
                        "reference_type": n.reference_type,
                    }
                    for n in upstream.nodes
                ],
                "total_count": upstream.total_count,
            },
            "downstream": {
                "nodes": [
                    {
                        "id": n.id,
                        "name": n.name,
                        "qualified_name": n.qualified_name,
                        "kind": n.kind,
                        "depth": n.depth,
                        "reference_type": n.reference_type,
                    }
                    for n in downstream.nodes
                ],
                "total_count": downstream.total_count,
            },
        }

