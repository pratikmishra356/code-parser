"""Service for generating flow documentation for entry points."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from code_parser.core import CodeSnippet, EntryPointFlow, FlowStep
from code_parser.database.models import EntryPointModel, SymbolModel
from code_parser.logging import get_logger
from code_parser.repositories import (
    EntryPointRepository,
    FileRepository,
    FlowRepository,
    SymbolRepository,
)
from code_parser.services.ai_service import AIService
from code_parser.services.graph_service import GraphService

logger = get_logger(__name__)


class FlowService:
    """Service for generating flow documentation for entry points."""

    def __init__(
        self,
        session: AsyncSession,
        flow_repo: FlowRepository,
        entry_point_repo: EntryPointRepository,
        symbol_repo: SymbolRepository,
        file_repo: FileRepository,
        graph_service: GraphService,
        ai_service: AIService,
    ) -> None:
        self._session = session
        self._flow_repo = flow_repo
        self._entry_point_repo = entry_point_repo
        self._symbol_repo = symbol_repo
        self._file_repo = file_repo
        self._graph_service = graph_service
        self._ai_service = ai_service

    async def generate_flow(
        self, entry_point_id: str, repo_id: str
    ) -> EntryPointFlow:
        """
        Generate flow documentation for an entry point.
        
        Process:
        1. Get entry point and its symbol
        2. Iteratively analyze call graph (max 4 iterations, 3 depths each)
        3. For each iteration:
           - Get downstream nodes for depth range
           - Collect source code for nodes
           - Send to AI with previous context
           - Merge results
        4. Store and return final flow documentation
        """
        # Get entry point
        entry_point = await self._entry_point_repo.get_by_id(repo_id, entry_point_id)
        if not entry_point:
            raise ValueError(f"Entry point not found: {entry_point_id}")

        # Get entry point symbol
        entry_symbol = await self._symbol_repo.get_symbol_by_id(entry_point.symbol_id)
        if not entry_symbol:
            raise ValueError(f"Entry point symbol not found: {entry_point.symbol_id}")

        # Get entry point file for language detection
        entry_file = await self._file_repo.get_by_id(entry_point.file_id)
        if not entry_file:
            raise ValueError(f"Entry point file not found: {entry_point.file_id}")

        logger.info(
            "flow_generation_started",
            entry_point_id=entry_point_id,
            symbol_id=entry_point.symbol_id,
            entry_point_name=entry_point.name,
            entry_point_type=entry_point.entry_point_type,
        )
        
        logger.debug(
            "flow_generation_entry_point_details",
            entry_point_id=entry_point_id,
            symbol_id=entry_point.symbol_id,
            file_id=entry_point.file_id,
            framework=entry_point.framework,
            description=entry_point.description,
            entry_symbol_id=entry_symbol.id,
            entry_symbol_name=entry_symbol.name,
            entry_symbol_qualified_name=entry_symbol.qualified_name,
            entry_file_path=entry_file.relative_path,
        )

        # Track all analyzed symbol IDs and file paths
        all_symbol_ids: set[str] = {entry_point.symbol_id}
        all_file_paths: set[str] = {entry_file.relative_path}
        previous_steps: list[dict[str, Any]] | None = None
        max_depth_reached = 0
        iterations_completed = 0
        last_flow_name: str | None = None
        last_technical_summary: str | None = None

        # Iterative flow generation (max 4 iterations, 3 depths each)
        for iteration in range(1, 5):  # iterations 1-4
            start_depth = (iteration - 1) * 3  # 0, 3, 6, 9
            end_depth = iteration * 3  # 3, 6, 9, 12

            logger.info(
                "flow_iteration_started",
                iteration=iteration,
                start_depth=start_depth,
                end_depth=end_depth,
            )

            # Get downstream call graph for this depth range
            # We need to get full graph up to end_depth, then filter
            logger.debug(
                "flow_iteration_fetching_graph",
                iteration=iteration,
                start_depth=start_depth,
                end_depth=end_depth,
                max_depth_requested=end_depth,
            )
            
            graph_result = await self._graph_service.get_downstream(
                repo_id, entry_point.symbol_id, max_depth=end_depth
            )
            
            logger.debug(
                "flow_iteration_graph_fetched",
                iteration=iteration,
                total_nodes=len(graph_result.nodes),
                root_symbol=graph_result.root_qualified_name,
                root_symbol_id=graph_result.root_symbol_id,
                requested_symbol_id=entry_point.symbol_id,
                nodes_at_depths={depth: sum(1 for n in graph_result.nodes if n.depth == depth) for depth in range(end_depth + 1)},
            )

            # Filter nodes in the current depth range
            nodes_in_range = [
                node
                for node in graph_result.nodes
                if start_depth <= node.depth <= end_depth
            ]
            
            logger.debug(
                "flow_iteration_nodes_filtered",
                iteration=iteration,
                nodes_in_range=len(nodes_in_range),
                depth_range=f"{start_depth}-{end_depth}",
            )

            # If no nodes in this range, stop early
            if not nodes_in_range:
                logger.info(
                    "flow_iteration_no_nodes",
                    iteration=iteration,
                    start_depth=start_depth,
                    end_depth=end_depth,
                )
                break

            # Track symbol IDs
            for node in nodes_in_range:
                if node.id:
                    all_symbol_ids.add(node.id)

            # Collect source code for all nodes in range
            symbol_ids_to_fetch = [node.id for node in nodes_in_range if node.id]
            logger.debug(
                "flow_iteration_fetching_symbols",
                iteration=iteration,
                symbol_count=len(symbol_ids_to_fetch),
            )
            
            symbols = await self._symbol_repo.get_symbols_by_ids(symbol_ids_to_fetch)
            
            logger.debug(
                "flow_iteration_symbols_fetched",
                iteration=iteration,
                symbols_found=len(symbols),
                symbols_requested=len(symbol_ids_to_fetch),
            )

            # Create a map of symbol_id -> symbol for quick lookup
            symbol_map: dict[str, SymbolModel] = {s.id: s for s in symbols}

            # Build nodes with code for AI
            nodes_with_code = []
            for node in nodes_in_range:
                symbol = symbol_map.get(node.id)
                if not symbol:
                    logger.debug(
                        "flow_iteration_symbol_not_found",
                        iteration=iteration,
                        node_id=node.id,
                        node_name=node.name,
                    )
                    continue

                # Get file for this symbol to get file path and language
                symbol_file = await self._file_repo.get_by_id(symbol.file_id)
                file_path = symbol_file.relative_path if symbol_file else "unknown"
                language = symbol_file.language if symbol_file else ""

                node_data = {
                    "id": node.id,
                    "name": node.name,
                    "qualified_name": node.qualified_name or symbol.qualified_name,
                    "depth": node.depth,
                    "source_code": symbol.source_code or "",
                    "signature": symbol.signature or "",
                    "language": language,
                    "file_path": file_path,
                }
                nodes_with_code.append(node_data)
                
                # Track file path
                if file_path and file_path != "unknown":
                    all_file_paths.add(file_path)
                
                logger.debug(
                    "flow_iteration_node_prepared",
                    iteration=iteration,
                    node_id=node.id,
                    node_name=node.name,
                    depth=node.depth,
                    file_path=file_path,
                    source_code_length=len(symbol.source_code or ""),
                )

                # Update max depth
                max_depth_reached = max(max_depth_reached, node.depth)

            # Include entry point symbol in first iteration
            if iteration == 1:
                entry_node_data = {
                    "id": entry_symbol.id,
                    "name": entry_symbol.name,
                    "qualified_name": entry_symbol.qualified_name,
                    "depth": 0,
                    "source_code": entry_symbol.source_code or "",
                    "signature": entry_symbol.signature or "",
                    "language": entry_file.language,
                    "file_path": entry_file.relative_path,
                }
                logger.debug(
                    "flow_iteration_adding_entry_point",
                    iteration=iteration,
                    entry_symbol_id=entry_symbol.id,
                    entry_symbol_name=entry_symbol.name,
                    entry_symbol_qualified_name=entry_symbol.qualified_name,
                    entry_file_path=entry_file.relative_path,
                    source_code_preview=entry_symbol.source_code[:200] if entry_symbol.source_code else "",
                )
                nodes_with_code.insert(0, entry_node_data)
                # Track entry point file path
                if entry_file.relative_path:
                    all_file_paths.add(entry_file.relative_path)

            # Call AI to generate flow documentation for this iteration
            logger.debug(
                "flow_iteration_calling_ai",
                iteration=iteration,
                nodes_count=len(nodes_with_code),
                has_previous_steps=previous_steps is not None,
                previous_steps_count=len(previous_steps) if previous_steps else 0,
            )
            
            try:
                ai_response = await self._ai_service.generate_flow_documentation(
                    entry_point_name=entry_point.name,
                    entry_point_type=entry_point.entry_point_type,
                    entry_point_description=entry_point.description,
                    symbol_qualified_name=entry_symbol.qualified_name,
                    nodes_with_code=nodes_with_code,
                    previous_steps=previous_steps,
                    iteration=iteration,
                    start_depth=start_depth,
                    end_depth=end_depth,
                )
                
                # Populate code snippets from nodes_with_code based on AI references
                for step in ai_response.get("steps", []):
                    for snippet_ref in step.get("important_code_snippets", []):
                        # Find matching node by qualified_name or symbol_name + file_path
                        snippet_code = None
                        for node in nodes_with_code:
                            if (node.get("qualified_name") == snippet_ref.get("qualified_name") or
                                (node.get("name") == snippet_ref.get("symbol_name") and 
                                 node.get("file_path") == snippet_ref.get("file_path"))):
                                snippet_code = node.get("source_code", "")
                                break
                        
                        # Extract code based on line_range if provided
                        if snippet_code and snippet_ref.get("line_range"):
                            line_range = snippet_ref["line_range"]
                            lines = snippet_code.split("\n")
                            start_line = max(0, line_range.get("start", 1) - 1)
                            end_line = min(len(lines), line_range.get("end", len(lines)))
                            snippet_code = "\n".join(lines[start_line:end_line])
                        
                        # Add code to snippet reference - use full source_code if line extraction fails
                        if snippet_code:
                            snippet_ref["code"] = snippet_code
                        elif snippet_ref.get("code"):
                            # Keep existing code if present
                            pass
                        else:
                            # If no code found, try to get from any node with matching symbol_name
                            for node in nodes_with_code:
                                if node.get("name") == snippet_ref.get("symbol_name"):
                                    snippet_ref["code"] = node.get("source_code", "")
                                    break
                            
                            # If still no code, set a placeholder (will be filtered out later)
                            if not snippet_ref.get("code"):
                                snippet_ref["code"] = ""
                
                logger.debug(
                    "flow_iteration_ai_response_received",
                    iteration=iteration,
                    flow_name=ai_response.get("flow_name"),
                    technical_summary_length=len(ai_response.get("technical_summary", "")),
                    steps_count=len(ai_response.get("steps", [])),
                )

                # Store flow name and summary from this iteration
                last_flow_name = ai_response.get("flow_name")
                last_technical_summary = ai_response.get("technical_summary")

                # Update previous steps for next iteration
                previous_steps = ai_response.get("steps", [])

                iterations_completed = iteration

                logger.info(
                    "flow_iteration_complete",
                    iteration=iteration,
                    steps_count=len(previous_steps),
                    flow_name=ai_response.get("flow_name"),
                )

            except Exception as e:
                logger.error(
                    "flow_iteration_error",
                    iteration=iteration,
                    error=str(e),
                )
                # Continue with previous steps if available
                if not previous_steps:
                    raise

        # Build final flow from last iteration's AI response
        if not previous_steps:
            raise ValueError("No flow steps generated")

        # Track the last successful AI response from iterations
        # We need to store flow_name and technical_summary from the last iteration
        # Since we don't store it in previous_steps, we'll use the last iteration's response
        # For efficiency, we'll use the last iteration's response directly instead of
        # making another expensive AI call
        
        # Get the full graph once to extract all file paths
        final_graph = await self._graph_service.get_downstream(
            repo_id, entry_point.symbol_id, max_depth=max_depth_reached
        )
        
        # Extract file paths from all nodes in the graph
        all_symbol_ids_list = list(all_symbol_ids)
        all_symbols = await self._symbol_repo.get_symbols_by_ids(all_symbol_ids_list)
        symbol_map_final = {s.id: s for s in all_symbols}
        
        for node in final_graph.nodes:
            symbol = symbol_map_final.get(node.id)
            if symbol:
                symbol_file = await self._file_repo.get_by_id(symbol.file_id)
                if symbol_file and symbol_file.relative_path:
                    all_file_paths.add(symbol_file.relative_path)
        
        # Ensure entry point file is included
        if entry_file.relative_path:
            all_file_paths.add(entry_file.relative_path)

        # Use the last iteration's response - we need to track flow_name and technical_summary
        # Since we don't have it stored, we'll make one final AI call but only for summary
        # Actually, let's optimize: use the last iteration's steps and generate summary from them
        # For now, use a simple approach: use entry point info + steps
        
        logger.debug(
            "flow_generation_building_final_flow",
            max_depth=max_depth_reached,
            iterations_completed=iterations_completed,
            steps_count=len(previous_steps),
            total_symbols=len(all_symbol_ids),
        )

        # Use flow name and summary from the last successful iteration
        flow_name = last_flow_name or f"{entry_point.name} Flow"
        technical_summary = last_technical_summary or entry_point.description or f"Execution flow for {entry_point.name}"
        
        final_steps = previous_steps
        
        # Ensure at least 1 step
        if len(final_steps) < 1:
            logger.warning(
                "flow_steps_empty",
                using_previous=len(previous_steps) if previous_steps else 0,
            )
            # Use previous steps if available
            if previous_steps:
                final_steps = previous_steps

        # File paths are already collected from all iterations
        # No need to check AI-provided file_paths since we track them during iterations
        
        file_paths_list = sorted(list(all_file_paths))
        
        logger.debug(
            "flow_generation_file_paths_extracted",
            total_file_paths=len(file_paths_list),
            file_paths=file_paths_list[:10],  # Log first 10
        )

        # Convert steps to FlowStep objects
        flow_steps = []
        for step_data in final_steps:
            code_snippets = []
            for snippet_data in step_data.get("important_code_snippets", []):
                # Skip snippets without code
                code = snippet_data.get("code", "")
                if not code or not code.strip():
                    logger.warning(
                        "skipping_empty_code_snippet",
                        symbol_name=snippet_data.get("symbol_name"),
                        qualified_name=snippet_data.get("qualified_name"),
                        file_path=snippet_data.get("file_path"),
                    )
                    continue
                
                code_snippets.append(
                    CodeSnippet(
                        code=code,
                        symbol_name=snippet_data["symbol_name"],
                        qualified_name=snippet_data["qualified_name"],
                        file_path=snippet_data["file_path"],
                        line_range=snippet_data["line_range"],
                    )
                )
            
            # Get file_path for step - use AI-provided or extract from first code snippet
            step_file_path = step_data.get("file_path", "")
            if not step_file_path and code_snippets:
                step_file_path = code_snippets[0].file_path

            flow_steps.append(
                FlowStep(
                    step_number=step_data["step_number"],
                    title=step_data["title"],
                    description=step_data["description"],
                    file_path=step_file_path,
                    important_log_lines=step_data.get("important_log_lines", []),
                    important_code_snippets=code_snippets,
                )
            )

        # Create EntryPointFlow
        flow = EntryPointFlow(
            entry_point_id=entry_point_id,
            repo_id=repo_id,
            flow_name=flow_name,
            technical_summary=technical_summary,
            file_paths=file_paths_list,
            steps=flow_steps,
            max_depth_analyzed=max_depth_reached,
            iterations_completed=iterations_completed,
            symbol_ids_analyzed=list(all_symbol_ids),
        )

        # Store in database
        logger.debug(
            "flow_generation_storing",
            entry_point_id=entry_point_id,
            flow_name=flow_name,
            steps_count=len(flow_steps),
            symbol_ids_count=len(all_symbol_ids),
        )
        
        await self._flow_repo.create_or_replace(flow)
        await self._session.commit()
        
        logger.debug(
            "flow_generation_stored",
            entry_point_id=entry_point_id,
        )

        logger.info(
            "flow_generation_complete",
            entry_point_id=entry_point_id,
            flow_name=flow_name,
            steps_count=len(flow_steps),
            max_depth=max_depth_reached,
            iterations=iterations_completed,
            total_symbols_analyzed=len(all_symbol_ids),
        )

        return flow

    async def get_flow(
        self, entry_point_id: str, repo_id: str
    ) -> EntryPointFlow | None:
        """Get flow documentation for an entry point."""
        model = await self._flow_repo.get_by_entry_point_id(entry_point_id)
        if not model or model.repo_id != repo_id:
            return None

        return self._flow_repo.model_to_core(model)
