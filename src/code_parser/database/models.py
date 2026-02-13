"""SQLAlchemy ORM models for database tables."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class OrganizationModel(Base):
    """Organization table - top-level multi-tenancy entity."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)  # ULID
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI / LLM configuration (pushed from CodeCircle platform)
    claude_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    claude_bedrock_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    claude_model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    claude_max_tokens: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    repositories: Mapped[list["RepositoryModel"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_organizations_name", "name", unique=True),)


class RepositoryModel(Base):
    """Repository table - stores metadata about parsed codebases."""

    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)  # ULID
    org_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    total_files: Mapped[int] = mapped_column(default=0)
    parsed_files: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    languages: Mapped[list] = mapped_column(JSONB, default=list)  # ["python", "java", "kotlin"]
    repo_tree: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Full directory tree structure
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization: Mapped["OrganizationModel"] = relationship(back_populates="repositories")
    files: Mapped[list["FileModel"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    symbols: Mapped[list["SymbolModel"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    references: Mapped[list["ReferenceModel"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["ParsingJobModel"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_repositories_status", "status"),
        Index("ix_repositories_org_id", "org_id"),
        Index("ix_repositories_org_path", "org_id", "root_path", unique=True),
    )


class FileModel(Base):
    """File table - stores parsed source files."""

    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    repo_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    content: Mapped[str | None] = mapped_column(Text, nullable=True)  # File source code
    folder_structure: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Immediate parent folder structure
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship(back_populates="files")
    symbols: Mapped[list["SymbolModel"]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_files_repo_path", "repo_id", "relative_path", unique=True),
        Index("ix_files_content_hash", "content_hash"),
    )


class SymbolModel(Base):
    """Symbol table - stores extracted code symbols."""

    __tablename__ = "symbols"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    file_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    repo_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    qualified_name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_symbol_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("symbols.id", ondelete="CASCADE"), nullable=True
    )
    extra_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Position information (1-indexed lines, 0-indexed columns)
    start_line: Mapped[int | None] = mapped_column(nullable=True)
    end_line: Mapped[int | None] = mapped_column(nullable=True)
    start_column: Mapped[int | None] = mapped_column(nullable=True)
    end_column: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    file: Mapped["FileModel"] = relationship(back_populates="symbols")
    repository: Mapped["RepositoryModel"] = relationship(back_populates="symbols")
    parent: Mapped["SymbolModel | None"] = relationship(
        remote_side=[id], foreign_keys=[parent_symbol_id]
    )

    # References where this symbol is the source (outgoing edges)
    outgoing_references: Mapped[list["ReferenceModel"]] = relationship(
        back_populates="source_symbol",
        foreign_keys="ReferenceModel.source_symbol_id",
        cascade="all, delete-orphan",
    )

    # References where this symbol is the target (incoming edges)
    incoming_references: Mapped[list["ReferenceModel"]] = relationship(
        back_populates="target_symbol",
        foreign_keys="ReferenceModel.target_symbol_id",
    )

    __table_args__ = (
        Index("ix_symbols_qualified_name", "repo_id", "qualified_name"),
        Index("ix_symbols_kind", "repo_id", "kind"),
        Index("ix_symbols_name", "repo_id", "name"),
        Index("ix_symbols_file", "file_id"),
        Index("ix_symbols_position", "repo_id", "start_line", "end_line"),
    )


class ReferenceModel(Base):
    """Reference table - stores call graph edges between symbols."""

    __tablename__ = "references"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    repo_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    source_symbol_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False
    )
    target_symbol_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("symbols.id", ondelete="SET NULL"), nullable=True
    )
    # File paths (dot notation) and symbol names for get_symbol_details API
    source_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_symbol_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    target_symbol_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship(back_populates="references")
    source_symbol: Mapped["SymbolModel"] = relationship(
        back_populates="outgoing_references", foreign_keys=[source_symbol_id]
    )
    target_symbol: Mapped["SymbolModel | None"] = relationship(
        back_populates="incoming_references", foreign_keys=[target_symbol_id]
    )

    __table_args__ = (
        Index("ix_references_source", "source_symbol_id"),
        Index("ix_references_target", "target_symbol_id"),
        Index("ix_references_target_path", "repo_id", "target_file_path"),
        Index("ix_references_type", "repo_id", "reference_type"),
    )


class ParsingJobModel(Base):
    """Parsing job queue table - PostgreSQL-based job queue."""

    __tablename__ = "parsing_jobs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    repo_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship(back_populates="jobs")

    __table_args__ = (
        Index("ix_jobs_pending", "status", "created_at", postgresql_where=(status == "pending")),
    )


class EntryPointCandidateModel(Base):
    """Entry point candidate table - stores Tree-sitter detected candidates before AI confirmation."""

    __tablename__ = "entry_point_candidates"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    repo_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    symbol_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    entry_point_type: Mapped[str] = mapped_column(String(20), nullable=False)  # HTTP, EVENT, SCHEDULER
    framework: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "flask", "spring-boot"
    detection_pattern: Mapped[str] = mapped_column(String(100), nullable=False)  # Which pattern matched
    entry_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)  # Path, method, event_name, schedule, etc.
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-1
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship()
    symbol: Mapped["SymbolModel"] = relationship()
    file: Mapped["FileModel"] = relationship()

    __table_args__ = (
        Index("ix_entry_point_candidates_repo", "repo_id"),
        Index("ix_entry_point_candidates_symbol", "symbol_id"),
        Index("ix_entry_point_candidates_type", "repo_id", "entry_point_type"),
    )


class EntryPointModel(Base):
    """Entry point table - stores AI-confirmed entry points."""

    __tablename__ = "entry_points"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    repo_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    symbol_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    entry_point_type: Mapped[str] = mapped_column(String(20), nullable=False)  # HTTP, EVENT, SCHEDULER
    framework: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "flask", "spring-boot"
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # Human-readable name
    description: Mapped[str] = mapped_column(Text, nullable=False)  # 1-2 line AI-generated description
    entry_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)  # Type-specific info (path, method, etc.)
    ai_confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0-1
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)  # Why AI confirmed it
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship()
    symbol: Mapped["SymbolModel"] = relationship()
    file: Mapped["FileModel"] = relationship()

    __table_args__ = (
        Index("ix_entry_points_repo_type", "repo_id", "entry_point_type"),
        Index("ix_entry_points_symbol", "symbol_id"),
        Index("ix_entry_points_framework", "repo_id", "framework"),
    )


class EntryPointFlowModel(Base):
    """Entry point flow table - stores flow documentation for entry points."""

    __tablename__ = "entry_point_flows"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    entry_point_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("entry_points.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    repo_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    flow_name: Mapped[str] = mapped_column(String(255), nullable=False)
    technical_summary: Mapped[str] = mapped_column(Text, nullable=False)
    file_paths: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # Array of file paths involved in flow
    steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # Array of flow steps
    max_depth_analyzed: Mapped[int] = mapped_column(nullable=False)
    iterations_completed: Mapped[int] = mapped_column(nullable=False)
    symbol_ids_analyzed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # Array of symbol IDs
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship()
    entry_point: Mapped["EntryPointModel"] = relationship()

    __table_args__ = (
        Index("ix_entry_point_flows_entry_point", "entry_point_id"),
        Index("ix_entry_point_flows_repo", "repo_id"),
    )

