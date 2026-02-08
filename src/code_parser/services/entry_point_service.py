"""Service for detecting entry points using Tree-sitter queries and AI confirmation."""

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from code_parser.core import (
    ConfirmedEntryPoint,
    EntryPointCandidate,
    EntryPointType,
    Language,
)
from code_parser.database.models import FileModel, RepositoryModel, SymbolModel
from code_parser.entry_points.query_executor import QueryExecutor, QueryMatch
from code_parser.entry_points.queries import (
    java_queries,
    javascript_queries,
    kotlin_queries,
    python_queries,
    rust_queries,
)
from code_parser.logging import get_logger
from code_parser.parsers.registry import get_parser_registry
from code_parser.repositories.entry_point_repository import EntryPointRepository
from code_parser.repositories.file_repository import FileRepository
from code_parser.repositories.repo_repository import RepoRepository
from code_parser.repositories.symbol_repository import SymbolRepository
from code_parser.services.ai_service import AIService

logger = get_logger(__name__)


class EntryPointService:
    """Service for detecting and confirming entry points."""

    def __init__(
        self,
        session: AsyncSession,
        entry_point_repo: EntryPointRepository,
        file_repo: FileRepository,
        repo_repo: RepoRepository,
        symbol_repo: SymbolRepository,
    ) -> None:
        self._session = session
        self._entry_point_repo = entry_point_repo
        self._file_repo = file_repo
        self._repo_repo = repo_repo
        self._symbol_repo = symbol_repo
        self._parser_registry = get_parser_registry()
        self._ai_service = AIService()

    async def detect_entry_points(
        self, repo_id: str, force_redetect: bool = False
    ) -> dict[str, Any]:
        """
        Detect entry points for a repository using AI-only flow:
        1. AI analyzes repo structure to suggest file paths likely to contain entry points
        2. AI analyzes those files in batches to confirm entry points
        
        Args:
            repo_id: Repository ID
            force_redetect: If True, delete existing entry points and re-detect
            
        Returns:
            Dictionary with detection statistics
        """
        # Check if repository exists
        repo = await self._repo_repo.get_by_id(repo_id)
        if not repo:
            raise ValueError(f"Repository not found: {repo_id}")

        # Delete existing if force_redetect
        if force_redetect:
            await self._entry_point_repo.delete_by_repo(repo_id)
            await self._session.commit()

        # Get all files for repository
        files = await self._file_repo.list_by_repo(repo_id, limit=10000)
        logger.info("entry_point_detection_started", repo_id=repo_id, file_count=len(files))

        # STEP 1: AI analyzes repo structure and suggests potential file paths
        ai_suggested_file_paths = await self._step2_ai_file_path_detection(
            repo_id, repo
        )
        
        logger.info(
            "step1_ai_file_paths_complete",
            repo_id=repo_id,
            ai_suggested_paths=len(ai_suggested_file_paths),
        )

        # Build file map from AI-suggested paths
        files_to_analyze = {
            f.relative_path: f for f in files 
            if f.relative_path in ai_suggested_file_paths
        }
        
        # Cap at reasonable limit to avoid excessive AI calls
        MAX_FILES_FOR_AI = 60
        if len(files_to_analyze) > MAX_FILES_FOR_AI:
            logger.warning(
                "too_many_files_for_ai",
                total_files=len(files_to_analyze),
                max_files=MAX_FILES_FOR_AI,
            )
            # Keep only the first MAX_FILES_FOR_AI (AI already ranked them by relevance)
            sorted_paths = list(files_to_analyze.keys())[:MAX_FILES_FOR_AI]
            files_to_analyze = {p: files_to_analyze[p] for p in sorted_paths}
        
        logger.info(
            "files_selected_for_analysis",
            repo_id=repo_id,
            ai_suggested_paths=len(ai_suggested_file_paths),
            files_to_analyze=len(files_to_analyze),
        )

        if not files_to_analyze:
            logger.warning("no_files_to_analyze", repo_id=repo_id)
            return {
                "candidates_detected": 0,
                "entry_points_confirmed": 0,
                "frameworks_detected": [],
                "statistics": {"by_type": {}, "by_framework": {}},
            }

        # Build symbol contexts for all files to analyze
        symbol_contexts = await self._build_symbol_contexts_for_files(
            repo_id, list(files_to_analyze.values())
        )

        # STEP 2: AI confirmation in batches
        repo_context = {
            "languages": repo.languages or [],
            "repo_tree": repo.repo_tree,
        }

        # Define callback to store confirmed entry points after each batch
        async def store_batch_confirmed(batch_confirmed: list, batch_index: int) -> None:
            """Store confirmed entry points after each batch."""
            if batch_confirmed:
                await self._entry_point_repo.bulk_insert_confirmed(repo_id, batch_confirmed)
                await self._session.commit()
                logger.info(
                    "batch_confirmed_stored",
                    repo_id=repo_id,
                    batch_index=batch_index,
                    confirmed_count=len(batch_confirmed),
                )

        confirmed = await self._ai_service.confirm_entry_points_from_files(
            files_to_analyze,
            repo_context,
            symbol_contexts,
            batch_size=5,
            on_batch_confirmed=store_batch_confirmed,
        )

        logger.info(
            "entry_point_confirmation_complete",
            repo_id=repo_id,
            confirmed_count=len(confirmed),
        )
        
        # Log entry points by type for diagnostics
        confirmed_by_type = defaultdict(int)
        for ep in confirmed:
            confirmed_by_type[ep.entry_point_type.value] += 1
        
        logger.info(
            "entry_point_confirmation_by_type",
            repo_id=repo_id,
            by_type=dict(confirmed_by_type),
            total_confirmed=len(confirmed),
        )

        # Build statistics
        stats = self._build_statistics(confirmed)
        
        # Extract frameworks from confirmed entry points
        frameworks_detected = list(set(ep.framework for ep in confirmed if ep.framework != "unknown"))

        # Generate repo description based on detected entry points
        if confirmed:
            try:
                description = await self._ai_service.generate_repo_description(
                    repo_name=repo.name,
                    languages=repo.languages or [],
                    frameworks=frameworks_detected,
                    entry_points=[
                        {"name": ep.name, "type": ep.entry_point_type.value, "description": ep.description}
                        for ep in confirmed
                    ],
                    repo_tree=repo.repo_tree,
                )
                if description:
                    await self._repo_repo.update_description(repo_id, description)
                    logger.info(
                        "repo_description_generated",
                        repo_id=repo_id,
                        description_length=len(description),
                    )
            except Exception as e:
                logger.warning(
                    "repo_description_generation_failed",
                    repo_id=repo_id,
                    error=str(e),
                )

        return {
            "candidates_detected": 0,
            "entry_points_confirmed": len(confirmed),
            "frameworks_detected": frameworks_detected,
            "statistics": stats,
        }

    async def _step1_tree_sitter_detection(
        self, repo_id: str, files: list[FileModel]
    ) -> tuple[list[EntryPointCandidate], set[str]]:
        """
        STEP 1: Run ALL Tree-sitter queries on ALL files (no framework filtering).
        
        Returns:
            Tuple of (candidates list, set of file paths with candidates)
        """
        all_candidates: list[EntryPointCandidate] = []
        file_paths_with_candidates: set[str] = set()

        for file_model in files:
            if not file_model.content:
                continue

            try:
                file_candidates = await self._detect_for_file_tree_sitter(
                    repo_id, file_model
                )
                if file_candidates:
                    all_candidates.extend(file_candidates)
                    file_paths_with_candidates.add(file_model.relative_path)
            except Exception as e:
                logger.warning(
                    "tree_sitter_detection_file_error",
                    repo_id=repo_id,
                    file_path=file_model.relative_path,
                    error=str(e),
                )

        return all_candidates, file_paths_with_candidates

    async def _detect_for_file_tree_sitter(
        self, repo_id: str, file_model: FileModel
    ) -> list[EntryPointCandidate]:
        """
        Detect entry point candidates for a single file using Tree-sitter.
        Runs ALL queries for the file's language (no framework filtering).
        """
        if not file_model.content:
            return []

        # Get parser for file language
        language = Language(file_model.language)
        parser = self._parser_registry.get_parser(language)
        if not parser:
            return []

        # Create query executor
        query_executor = QueryExecutor(parser._language, parser._parser)

        # Get ALL queries for this language (no framework filtering)
        all_queries = self._get_all_queries_for_language(language)
        
        if not all_queries:
            return []

        # Execute all queries
        matches_by_query = query_executor.execute_queries(file_model.content, all_queries)

        # Extract candidates from matches
        candidates: list[EntryPointCandidate] = []
        for query_name, matches in matches_by_query.items():
            for match in matches:
                # Apply query-specific filtering (e.g., camel_from_call must be "from")
                if not self._should_include_match(query_name, match, query_executor, file_model.content):
                    continue
                
                candidate = await self._extract_candidate(
                    repo_id, file_model, match, query_name, language, query_executor
                )
                if candidate:
                    candidates.append(candidate)

        return candidates

    def _get_all_queries_for_language(self, language: Language) -> dict[str, str]:
        """Get ALL query strings for a language (no filtering)."""
        if language == Language.PYTHON:
            return python_queries.get_python_queries()
        elif language == Language.JAVA:
            return java_queries.get_java_queries()
        elif language == Language.KOTLIN:
            return kotlin_queries.get_kotlin_queries()
        elif language == Language.JAVASCRIPT:
            return javascript_queries.get_javascript_queries()
        elif language == Language.RUST:
            return rust_queries.get_rust_queries()
        else:
            return {}

    # Annotation names that indicate Spring HTTP mapping entry points
    _SPRING_HTTP_ANNOTATIONS = {
        "RequestMapping", "GetMapping", "PostMapping", "PutMapping",
        "DeleteMapping", "PatchMapping", "Mapping",
    }
    
    # Annotation names that indicate Spring REST controller classes
    _SPRING_CONTROLLER_ANNOTATIONS = {
        "RestController", "Controller",
    }
    
    # Annotation names for JAX-RS HTTP methods
    _JAX_RS_HTTP_ANNOTATIONS = {
        "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS",
    }
    
    # Annotation names for Kafka listeners
    _KAFKA_ANNOTATIONS = {
        "KafkaListener", "KafkaHandler",
    }
    
    # Annotation names for Pulsar consumers
    _PULSAR_ANNOTATIONS = {
        "PulsarListener", "PulsarConsumer",
    }
    
    # Annotation names for schedulers
    _SCHEDULER_ANNOTATIONS = {
        "Scheduled", "Schedules", "CronSchedule",
    }

    def _should_include_match(
        self, query_name: str, match: QueryMatch, query_executor: QueryExecutor, source_code: str
    ) -> bool:
        """Apply query-specific filtering to matches."""
        # Filter camel_from_call to only match actual "from()" calls
        if query_name == "camel_from_call":
            from_method_node = match.captures.get("from_method")
            if from_method_node:
                method_name = query_executor.extract_node_text(from_method_node, source_code)
                return method_name == "from"
        
        # Filter camel_configure_method to only match "configure()" methods
        elif query_name == "camel_configure_method":
            function_name_node = match.captures.get("function_name")
            if function_name_node:
                function_name = query_executor.extract_node_text(function_name_node, source_code)
                return function_name == "configure"
        
        # Filter camel_route_builder_class to only match classes with configure() method
        elif query_name == "camel_route_builder_class":
            configure_method_node = match.captures.get("configure_method")
            if configure_method_node:
                method_name = query_executor.extract_node_text(configure_method_node, source_code)
                return method_name == "configure"
        
        # Filter Spring request mapping to only match actual HTTP mapping annotations
        elif query_name == "spring_request_mapping":
            mapping_annotation = match.captures.get("mapping_annotation")
            if mapping_annotation:
                annotation_name = query_executor.extract_node_text(mapping_annotation, source_code)
                return annotation_name in self._SPRING_HTTP_ANNOTATIONS
            return False
        
        # Filter Spring REST controller to only match actual controller annotations
        elif query_name == "spring_rest_controller":
            controller_annotation = match.captures.get("rest_controller") or match.captures.get("controller_annotation")
            if controller_annotation:
                annotation_name = query_executor.extract_node_text(controller_annotation, source_code)
                return annotation_name in self._SPRING_CONTROLLER_ANNOTATIONS
            return False
        
        # Filter JAX-RS resource methods to only match methods with HTTP method annotations
        elif query_name in ["jax_rs_resource_method"]:
            http_method_annotation = match.captures.get("http_method_annotation")
            if http_method_annotation:
                annotation_name = query_executor.extract_node_text(http_method_annotation, source_code)
                return annotation_name in self._JAX_RS_HTTP_ANNOTATIONS
            return False
        
        # Filter JAX-RS path methods to only match @Path annotations
        elif query_name == "jax_rs_path_method":
            path_annotation = match.captures.get("path_annotation")
            if path_annotation:
                annotation_name = query_executor.extract_node_text(path_annotation, source_code)
                return annotation_name == "Path"
            return False
        
        # Filter Kafka listener to only match actual Kafka annotations
        elif query_name == "kafka_listener":
            kafka_annotation = match.captures.get("kafka_annotation") or match.captures.get("kafka_listener")
            if kafka_annotation:
                annotation_name = query_executor.extract_node_text(kafka_annotation, source_code)
                return annotation_name in self._KAFKA_ANNOTATIONS
            return False
        
        # Filter Pulsar consumer to only match actual Pulsar annotations
        elif query_name == "pulsar_consumer":
            pulsar_annotation = match.captures.get("pulsar_annotation")
            if pulsar_annotation:
                annotation_name = query_executor.extract_node_text(pulsar_annotation, source_code)
                return annotation_name in self._PULSAR_ANNOTATIONS
            return False
        
        # Filter scheduled annotation to only match actual Scheduled annotations
        elif query_name in ["spring_scheduled", "scheduled_annotation"]:
            sched_annotation = match.captures.get("scheduled_annotation") or match.captures.get("scheduled")
            if sched_annotation:
                annotation_name = query_executor.extract_node_text(sched_annotation, source_code)
                return annotation_name in self._SCHEDULER_ANNOTATIONS
            return False
        
        # By default, include all matches
        return True

    async def _step2_ai_file_path_detection(
        self, repo_id: str, repo: RepositoryModel
    ) -> set[str]:
        """
        STEP 2: AI analyzes repo structure and suggests potential file paths.
        
        Returns:
            Set of file paths suggested by AI
        """
        if not repo.repo_tree:
            logger.warning("no_repo_tree", repo_id=repo_id)
            return set()

        # Call AI to analyze repo structure
        suggested_paths = await self._ai_service.suggest_entry_point_file_paths(
            repo.repo_tree,
            repo.languages or [],
        )
        
        return set(suggested_paths)

    async def _build_symbol_contexts_for_files(
        self, repo_id: str, files: list[FileModel]
    ) -> dict[str, dict[str, Any]]:
        """Build symbol contexts for files (for AI analysis)."""
        contexts: dict[str, dict[str, Any]] = {}
        
        for file_model in files:
            if not file_model.content:
                continue
            
            # Get all symbols in this file
            symbols = await self._symbol_repo.get_symbols_in_file(file_model.id)
            
            for symbol in symbols:
                contexts[symbol.id] = {
                    "name": symbol.name,
                    "qualified_name": symbol.qualified_name,
                    "signature": symbol.signature or "",
                    "source_code": symbol.source_code,
                    "file_path": file_model.relative_path,
                    "file_content": file_model.content,
                    "language": file_model.language,
                }
        
        return contexts

    async def _extract_candidate(
        self,
        repo_id: str,
        file_model: FileModel,
        match: QueryMatch,
        query_name: str,
        language: Language,
        query_executor: QueryExecutor,
    ) -> EntryPointCandidate | None:
        """Extract an EntryPointCandidate from a query match."""
        # Extract function/class name from captures
        function_name_node = (
            match.captures.get("function_name")
            or match.captures.get("method_name")
            or match.captures.get("configure_method")
            or match.captures.get("execute_method")
            or match.captures.get("from_method")
            or match.captures.get("http_method")
        )
        
        class_name_node = match.captures.get("class_name")
        
        # Determine which symbol to look for
        symbol = None
        function_name = None
        
        # Priority 1: Function/method name
        if function_name_node:
            function_name = query_executor.extract_node_text(
                function_name_node, file_model.content or ""
            )
            if function_name:
                symbol = await self._find_symbol_by_name_async(
                    repo_id, file_model.id, function_name
                )
                if not symbol:
                    start_line, end_line, _, _ = query_executor.extract_node_position(
                        function_name_node
                    )
                    if start_line:
                        symbol = await self._find_symbol_by_position(
                            repo_id, file_model.id, start_line
                        )
        
        # Priority 2: Class name
        if not symbol and class_name_node:
            class_name = query_executor.extract_node_text(
                class_name_node, file_model.content or ""
            )
            if class_name:
                symbol = await self._find_symbol_by_name_async(
                    repo_id, file_model.id, class_name
                )
                # For Camel routes, prefer the configure() method if it exists
                if symbol and query_name.startswith("camel_"):
                    configure_symbol = await self._find_symbol_by_name_async(
                        repo_id, file_model.id, "configure"
                    )
                    if configure_symbol:
                        symbol = configure_symbol
                        function_name = "configure"

        if not symbol:
            # Try to find symbol by qualified name if we have class context
            if class_name_node and function_name:
                class_name = query_executor.extract_node_text(
                    class_name_node, file_model.content or ""
                )
                if class_name:
                    # Try qualified name: ClassName.functionName
                    qualified_name = f"{class_name}.{function_name}"
                    result = await self._session.execute(
                        select(SymbolModel).where(
                            SymbolModel.repo_id == repo_id,
                            SymbolModel.file_id == file_model.id,
                            SymbolModel.qualified_name.like(f"%{qualified_name}%"),
                        )
                    )
                    symbol = result.scalars().first()
                    if symbol:
                        logger.debug(
                            "symbol_found_by_qualified_name",
                            repo_id=repo_id,
                            file_path=file_model.relative_path,
                            qualified_name=qualified_name,
                            symbol_id=symbol.id,
                        )
            
            if not symbol:
                return None

        # Determine entry point type and framework from query name
        entry_point_type, framework = self._infer_type_and_framework(query_name)

        # Extract metadata from captures
        metadata = self._extract_metadata(match, language, query_executor, file_model.content or "")

        return EntryPointCandidate(
            symbol_id=symbol.id,
            file_id=file_model.id,
            entry_point_type=entry_point_type,
            framework=framework,
            detection_pattern=query_name,
            metadata=metadata,
            confidence_score=0.8,
        )

    async def _find_symbol_by_name_async(
        self, repo_id: str, file_id: str, name: str
    ) -> SymbolModel | None:
        """Find a symbol by name in a file. Returns first match if multiple exist (overloaded methods)."""
        result = await self._session.execute(
            select(SymbolModel).where(
                SymbolModel.repo_id == repo_id,
                SymbolModel.file_id == file_id,
                SymbolModel.name == name,
            )
        )
        return result.scalars().first()

    async def _find_symbol_by_position(
        self, repo_id: str, file_id: str, start_line: int
    ) -> SymbolModel | None:
        """Find a symbol by position in a file. Returns first match if multiple exist."""
        result = await self._session.execute(
            select(SymbolModel).where(
                SymbolModel.repo_id == repo_id,
                SymbolModel.file_id == file_id,
                SymbolModel.start_line == start_line,
            )
        )
        return result.scalars().first()

    def _infer_type_and_framework(
        self, query_name: str
    ) -> tuple[EntryPointType, str]:
        """Infer entry point type and framework from query name."""
        # Apache Camel routes
        if "camel" in query_name:
            return EntryPointType.EVENT, "apache-camel"
        
        # HTTP endpoints
        if any(x in query_name for x in ["flask", "fastapi", "django", "route", "api_view", "ktor", "jax_rs", "spring"]):
            if "flask" in query_name:
                return EntryPointType.HTTP, "flask"
            elif "fastapi" in query_name:
                return EntryPointType.HTTP, "fastapi"
            elif "django" in query_name:
                return EntryPointType.HTTP, "django"
            elif "ktor" in query_name:
                return EntryPointType.HTTP, "ktor"
            elif "jax_rs" in query_name:
                return EntryPointType.HTTP, "jax-rs"
            elif "spring" in query_name:
                return EntryPointType.HTTP, "spring-boot"
            return EntryPointType.HTTP, "unknown"

        # Event handlers
        if any(x in query_name for x in ["kafka", "pulsar", "celery", "consumer", "subscribe"]):
            if "kafka" in query_name:
                return EntryPointType.EVENT, "kafka"
            elif "pulsar" in query_name:
                return EntryPointType.EVENT, "pulsar"
            elif "celery" in query_name:
                return EntryPointType.EVENT, "celery"
            return EntryPointType.EVENT, "unknown"

        # Schedulers
        if any(x in query_name for x in ["scheduled", "cron", "scheduler", "quartz"]):
            return EntryPointType.SCHEDULER, "scheduler"

        return EntryPointType.HTTP, "unknown"

    def _extract_metadata(
        self, match: QueryMatch, language: Language, query_executor: QueryExecutor, source_code: str
    ) -> dict[str, Any]:
        """Extract metadata from query match captures."""
        metadata: dict[str, Any] = {}

        # Extract path if available
        path_node = match.captures.get("path")
        if path_node:
            path = query_executor.extract_node_text(path_node, source_code).strip('"\'')
            metadata["path"] = path

        # Extract HTTP method if available
        method_node = match.captures.get("method")
        if method_node:
            method = query_executor.extract_node_text(method_node, source_code).lower()
            metadata["method"] = method

        # Extract topic/event name for event handlers
        topic_node = match.captures.get("topic")
        if topic_node:
            topic = query_executor.extract_node_text(topic_node, source_code).strip('"\'')
            metadata["topic"] = topic

        # Extract schedule for schedulers
        schedule_node = match.captures.get("schedule_value") or match.captures.get("cron_expression")
        if schedule_node:
            schedule = query_executor.extract_node_text(schedule_node, source_code).strip('"\'')
            metadata["schedule"] = schedule

        return metadata

    def _build_statistics(
        self, confirmed: list[ConfirmedEntryPoint]
    ) -> dict[str, Any]:
        """Build statistics from confirmed entry points."""
        stats: dict[str, Any] = {
            "by_type": defaultdict(int),
            "by_framework": defaultdict(int),
        }

        for ep in confirmed:
            stats["by_type"][ep.entry_point_type.value] += 1
            stats["by_framework"][ep.framework] += 1

        return {
            "by_type": dict(stats["by_type"]),
            "by_framework": dict(stats["by_framework"]),
        }
