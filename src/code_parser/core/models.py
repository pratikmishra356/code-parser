"""Core domain models - pure Python dataclasses with no framework dependencies."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Self


class Language(StrEnum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVA = "java"
    RUST = "rust"
    JAVASCRIPT = "javascript"
    KOTLIN = "kotlin"

    @classmethod
    def from_extension(cls, extension: str) -> Self | None:
        """Get language from file extension."""
        mapping = {
            ".py": cls.PYTHON,
            ".java": cls.JAVA,
            ".rs": cls.RUST,
            ".js": cls.JAVASCRIPT,
            ".mjs": cls.JAVASCRIPT,
            ".cjs": cls.JAVASCRIPT,
            ".kt": cls.KOTLIN,
            ".kts": cls.KOTLIN,
        }
        return mapping.get(extension.lower())


class SymbolKind(StrEnum):
    """Types of code symbols we extract."""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    IMPORT = "import"
    INTERFACE = "interface"  # Java/TypeScript
    ENUM = "enum"
    STRUCT = "struct"  # Rust
    TRAIT = "trait"  # Rust
    IMPL = "impl"  # Rust


class ReferenceType(StrEnum):
    """Types of references between symbols."""

    CALL = "call"  # Function/method call
    IMPORT = "import"  # Import statement
    INHERITANCE = "inheritance"  # Class extends/implements
    TYPE_ANNOTATION = "type_annotation"  # Type hints/annotations
    INSTANTIATION = "instantiation"  # new ClassName()
    MEMBER = "member"  # Class contains method/property (for traversal)


class RepositoryStatus(StrEnum):
    """Status of a repository in the parsing pipeline."""

    PENDING = "pending"
    PARSING = "parsing"
    COMPLETED = "completed"
    FAILED = "failed"


class EntryPointType(StrEnum):
    """Types of entry points that can be detected."""

    HTTP = "http"  # HTTP endpoints (REST, GraphQL, gRPC)
    EVENT = "event"  # Event handlers (Kafka, Pulsar, SQS, etc.)
    SCHEDULER = "scheduler"  # Scheduled tasks (cron, periodic tasks)


@dataclass(frozen=True, slots=True)
class Symbol:
    """
    A code symbol extracted from source code.
    
    Immutable value object representing a function, class, method, etc.
    """

    name: str
    qualified_name: str  # e.g., "mymodule.MyClass.my_method"
    kind: SymbolKind
    source_code: str
    signature: str | None = None  # e.g., "def foo(x: int, y: str) -> bool"
    parent_qualified_name: str | None = None  # For nested symbols
    metadata: dict[str, str | int | bool | list] = field(default_factory=dict)
    # Position information (1-indexed, like most editors)
    start_line: int | None = None
    end_line: int | None = None
    start_column: int | None = None  # 0-indexed column position
    end_column: int | None = None  # 0-indexed column position

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Symbol name cannot be empty")
        if not self.qualified_name:
            raise ValueError("Symbol qualified_name cannot be empty")
        # Validate position information if provided
        if self.start_line is not None and self.start_line < 1:
            raise ValueError("start_line must be >= 1")
        if self.end_line is not None and self.end_line < 1:
            raise ValueError("end_line must be >= 1")
        if self.start_line is not None and self.end_line is not None:
            if self.end_line < self.start_line:
                raise ValueError("end_line must be >= start_line")


@dataclass(frozen=True, slots=True)
class Reference:
    """
    A reference from one symbol to another (edge in call graph).
    
    New style (preferred) - stores file paths and symbol names for direct 
    use with get_symbol_details API:
    - source_file_path, source_symbol_name
    - target_file_path, target_symbol_name
    
    Legacy style (for backward compatibility with other parsers):
    - source_qualified_name, target_qualified_name
    
    File paths use dot notation matching import statements.
    """

    reference_type: ReferenceType
    # New style fields (preferred)
    source_file_path: str | None = None
    source_symbol_name: str | None = None
    target_file_path: str | None = None
    target_symbol_name: str | None = None
    # Legacy fields (for backward compatibility)
    source_qualified_name: str | None = None
    target_qualified_name: str | None = None

    def __post_init__(self) -> None:
        # Must have either new style or legacy style
        has_new = self.source_file_path and self.target_file_path and self.target_symbol_name
        has_legacy = self.source_qualified_name and self.target_qualified_name
        if not has_new and not has_legacy:
            raise ValueError("Reference must have either new style fields or legacy fields")
    
    def get_source_path(self) -> str:
        """Get source file path (new or derived from legacy)."""
        if self.source_file_path:
            return self.source_file_path
        if self.source_qualified_name and "." in self.source_qualified_name:
            return ".".join(self.source_qualified_name.split(".")[:-1])
        return self.source_qualified_name or ""
    
    def get_source_name(self) -> str:
        """Get source symbol name (new or derived from legacy)."""
        if self.source_symbol_name:
            return self.source_symbol_name
        if self.source_qualified_name:
            return self.source_qualified_name.split(".")[-1]
        return ""
    
    def get_target_path(self) -> str:
        """Get target file path (new or derived from legacy)."""
        if self.target_file_path:
            return self.target_file_path
        if self.target_qualified_name and "." in self.target_qualified_name:
            return ".".join(self.target_qualified_name.split(".")[:-1])
        return self.target_qualified_name or ""
    
    def get_target_name(self) -> str:
        """Get target symbol name (new or derived from legacy)."""
        if self.target_symbol_name:
            return self.target_symbol_name
        if self.target_qualified_name:
            return self.target_qualified_name.split(".")[-1]
        return ""


@dataclass(frozen=True, slots=True)
class ParsedFile:
    """Result of parsing a single source file."""

    relative_path: str
    language: Language
    content_hash: str
    symbols: tuple[Symbol, ...]
    references: tuple[Reference, ...]
    errors: tuple[str, ...] = ()

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def symbol_count(self) -> int:
        return len(self.symbols)


@dataclass(slots=True)
class Organization:
    """An organization - top-level multi-tenancy entity."""

    id: str
    name: str
    description: str | None = None
    # AI / LLM config (pushed from CodeCircle platform)
    claude_api_key: str | None = None
    claude_bedrock_url: str | None = None
    claude_model_id: str | None = None
    claude_max_tokens: int | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class Repository:
    """A code repository being parsed."""

    id: str
    name: str
    root_path: str
    status: RepositoryStatus
    org_id: str = ""
    description: str | None = None
    total_files: int = 0
    parsed_files: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_message: str | None = None
    languages: list[str] = field(default_factory=list)
    repo_tree: dict | None = None

    @property
    def progress_percentage(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.parsed_files / self.total_files) * 100


@dataclass(slots=True)
class ParsingJob:
    """A job in the parsing queue."""

    id: str
    repo_id: str
    status: RepositoryStatus
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    worker_id: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class EntryPointCandidate:
    """
    A candidate entry point detected by Tree-sitter queries.
    
    This represents a potential entry point before AI confirmation.
    """

    symbol_id: str
    file_id: str
    entry_point_type: EntryPointType
    framework: str  # e.g., "flask", "spring-boot", "ktor"
    detection_pattern: str  # Which query pattern matched
    metadata: dict[str, str | int | bool | list] = field(default_factory=dict)
    confidence_score: float | None = None  # 0-1, from pattern matching

    def __post_init__(self) -> None:
        if not self.symbol_id:
            raise ValueError("symbol_id cannot be empty")
        if not self.file_id:
            raise ValueError("file_id cannot be empty")
        if self.confidence_score is not None and not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError("confidence_score must be between 0.0 and 1.0")


@dataclass(frozen=True, slots=True)
class ConfirmedEntryPoint:
    """
    An AI-confirmed entry point.
    
    This represents a real entry point that has been validated by AI
    and includes a human-readable name and description.
    """

    symbol_id: str
    file_id: str
    entry_point_type: EntryPointType
    framework: str  # e.g., "flask", "spring-boot", "ktor"
    name: str  # Human-readable entry point name
    description: str  # 1-2 line AI-generated description
    metadata: dict[str, str | int | bool | list] = field(default_factory=dict)
    ai_confidence: float = 0.0  # 0-1, AI's confidence in confirmation
    ai_reasoning: str | None = None  # Why AI confirmed/rejected it

    def __post_init__(self) -> None:
        if not self.symbol_id:
            raise ValueError("symbol_id cannot be empty")
        if not self.file_id:
            raise ValueError("file_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if not self.description:
            raise ValueError("description cannot be empty")
        if not (0.0 <= self.ai_confidence <= 1.0):
            raise ValueError("ai_confidence must be between 0.0 and 1.0")


@dataclass(frozen=True, slots=True)
class CodeSnippet:
    """A code snippet with context information."""

    code: str
    symbol_name: str
    qualified_name: str
    file_path: str
    line_range: dict[str, int]  # {"start": int, "end": int}

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("code cannot be empty")
        if not self.symbol_name:
            raise ValueError("symbol_name cannot be empty")
        if not self.qualified_name:
            raise ValueError("qualified_name cannot be empty")
        if not self.file_path:
            raise ValueError("file_path cannot be empty")
        if "start" not in self.line_range or "end" not in self.line_range:
            raise ValueError("line_range must contain 'start' and 'end' keys")


@dataclass(frozen=True, slots=True)
class FlowStep:
    """A single step in a flow documentation."""

    step_number: int
    title: str
    description: str  # What's happening
    file_path: str  # Full file path containing the main code for this step
    important_log_lines: list[str] = field(default_factory=list)  # Actual log statements
    important_code_snippets: list[CodeSnippet] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.step_number < 1:
            raise ValueError("step_number must be >= 1")
        if not self.title:
            raise ValueError("title cannot be empty")
        if not self.description:
            raise ValueError("description cannot be empty")
        if not self.file_path:
            raise ValueError("file_path cannot be empty")


@dataclass(frozen=True, slots=True)
class EntryPointFlow:
    """Complete flow documentation for an entry point."""

    entry_point_id: str
    repo_id: str
    flow_name: str
    technical_summary: str  # Full technical summary, no filler
    steps: list[FlowStep]  # 2-5 coarse steps
    max_depth_analyzed: int
    iterations_completed: int  # 1-4
    file_paths: list[str] = field(default_factory=list)  # All file paths involved in the flow
    symbol_ids_analyzed: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.entry_point_id:
            raise ValueError("entry_point_id cannot be empty")
        if not self.repo_id:
            raise ValueError("repo_id cannot be empty")
        if not self.flow_name:
            raise ValueError("flow_name cannot be empty")
        if not self.technical_summary:
            raise ValueError("technical_summary cannot be empty")
        if len(self.steps) < 1:
            raise ValueError("steps must contain at least 1 step")
        if not (1 <= self.iterations_completed <= 4):
            raise ValueError("iterations_completed must be between 1 and 4")
        if self.max_depth_analyzed < 0:
            raise ValueError("max_depth_analyzed must be >= 0")

