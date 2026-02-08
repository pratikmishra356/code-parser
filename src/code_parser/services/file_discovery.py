"""File discovery utilities for walking codebases."""

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from code_parser.config import get_settings
from code_parser.logging import get_logger
from code_parser.parsers import get_parser_registry

logger = get_logger(__name__)

# Directories to always skip
SKIP_DIRECTORIES = frozenset({
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "venv",
    ".venv",
    "env",
    ".env",
    "target",  # Rust
    "build",
    "dist",
    ".idea",
    ".vscode",
})


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    """A file discovered for parsing."""

    relative_path: str
    absolute_path: str
    size_bytes: int


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


def discover_files(root_path: str) -> list[DiscoveredFile]:
    """
    Walk a directory tree and discover parseable files.
    
    Respects SKIP_DIRECTORIES and filters by supported extensions.
    Returns files sorted by path.
    """
    settings = get_settings()
    registry = get_parser_registry()
    supported_extensions = set(registry.supported_extensions)

    root = Path(root_path).resolve()
    if not root.is_dir():
        raise ValueError(f"Root path is not a directory: {root_path}")

    discovered: list[DiscoveredFile] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Filter out directories we should skip (in-place modification)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRECTORIES]

        for filename in filenames:
            # Check extension
            ext = Path(filename).suffix.lower()
            if ext not in supported_extensions:
                continue

            abs_path = Path(dirpath) / filename
            
            # Skip files that are too large
            try:
                size = abs_path.stat().st_size
                if size > settings.max_file_size_bytes:
                    logger.debug(
                        "file_skipped_too_large",
                        path=str(abs_path),
                        size=size,
                        max_size=settings.max_file_size_bytes,
                    )
                    continue
            except OSError:
                continue

            # Calculate relative path
            rel_path = str(abs_path.relative_to(root))

            discovered.append(
                DiscoveredFile(
                    relative_path=rel_path,
                    absolute_path=str(abs_path),
                    size_bytes=size,
                )
            )

    # Sort by path for deterministic processing
    discovered.sort(key=lambda f: f.relative_path)

    logger.info(
        "files_discovered",
        root_path=str(root),
        file_count=len(discovered),
    )

    return discovered


def read_file_content(file_path: str) -> tuple[str, str]:
    """
    Read file content and compute hash.
    
    Returns (content, hash).
    """
    with open(file_path, "rb") as f:
        raw_content = f.read()

    content_hash = compute_file_hash(raw_content)
    content = raw_content.decode("utf-8", errors="replace")

    return content, content_hash


def build_repo_tree(files: list[DiscoveredFile]) -> dict:
    """
    Build a complete directory tree structure from discovered files.
    
    Returns a nested dictionary representing the full repository structure.
    Example:
    {
        "routes": {
            "user.py": {},
            "models.py": {},
            "util": {
                "helper.py": {}
            }
        }
    }
    
    The tree structure is stored in the repositories table as JSONB
    and represents the complete directory hierarchy of the repository.
    """
    tree: dict = {}
    
    for file in files:
        try:
            parts = Path(file.relative_path).parts
            current = tree
            
            # Navigate/create the directory structure
            for part in parts[:-1]:  # All parts except the filename
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Add the file (as empty dict to distinguish from directories)
            filename = parts[-1]
            current[filename] = {}
        except Exception as e:
            logger.warning(
                "failed_to_add_file_to_tree",
                path=file.relative_path,
                error=str(e),
            )
            continue
    
    return tree


def validate_repo_tree(repo_tree: dict) -> bool:
    """
    Validate that repo_tree has the correct structure.
    
    Returns True if valid, False otherwise.
    """
    if not isinstance(repo_tree, dict):
        return False
    
    def validate_node(node: dict, depth: int = 0) -> bool:
        """Recursively validate tree nodes."""
        if depth > 100:  # Prevent infinite recursion
            return False
        
        for key, value in node.items():
            if not isinstance(key, str):
                return False
            if not isinstance(value, dict):
                return False
            if not validate_node(value, depth + 1):
                return False
        
        return True
    
    return validate_node(repo_tree)


def build_folder_structure(
    file_path: str, all_files: list[DiscoveredFile]
) -> dict:
    """
    Build the folder structure for a specific file.
    
    Returns the immediate parent directory's contents (files and subdirectories)
    as a tree structure, always starting with the parent directory name.
    
    Example for "routes/models.py":
    {
        "routes": {
            "user.py": {},
            "models.py": {},
            "util": {}
        }
    }
    
    Example for root-level "main.py":
    {
        ".": {
            "main.py": {},
            "routes": {}
        }
    }
    """
    file_path_obj = Path(file_path)
    parent_dir = file_path_obj.parent
    
    # Get all files in the same parent directory
    parent_files: list[str] = []
    parent_dirs: set[str] = set()
    
    for discovered_file in all_files:
        discovered_path = Path(discovered_file.relative_path)
        
        # Check if file is in the same parent directory
        if discovered_path.parent == parent_dir:
            parent_files.append(discovered_path.name)
        # Check if any file is in a subdirectory of the parent
        elif len(discovered_path.parts) > len(parent_dir.parts) + 1:
            # Check if the first part after parent_dir matches
            if discovered_path.parts[:len(parent_dir.parts)] == parent_dir.parts:
                subdir_name = discovered_path.parts[len(parent_dir.parts)]
                parent_dirs.add(subdir_name)
    
    # Build the structure - always show parent directory
    structure: dict = {}
    
    if parent_dir.parts:
        # Has parent directory - use the directory name
        parent_name = str(parent_dir).replace("\\", "/")  # Normalize path separators
    else:
        # Root level - use "." to represent root
        parent_name = "."
    
    structure[parent_name] = {}
    
    # Add files
    for filename in sorted(parent_files):
        structure[parent_name][filename] = {}
    
    # Add subdirectories
    for dirname in sorted(parent_dirs):
        structure[parent_name][dirname] = {}
    
    return structure

