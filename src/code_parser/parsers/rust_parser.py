"""Rust language parser using tree-sitter."""

import tree_sitter_rust as ts_rust
from tree_sitter import Language, Node, Parser

from code_parser.core import (
    Language as CodeLanguage,
    ParsedFile,
    Reference,
    ReferenceType,
    Symbol,
    SymbolKind,
)
from code_parser.parsers.base import LanguageParser, ParseContext


class RustParser(LanguageParser):
    """
    Parser for Rust source code.
    
    Extracts functions, structs, traits, impls, and call references
    using tree-sitter-rust.
    """

    def __init__(self) -> None:
        self._language = Language(ts_rust.language())
        self._parser = Parser(self._language)

    @property
    def language(self) -> CodeLanguage:
        return CodeLanguage.RUST

    @property
    def file_extensions(self) -> frozenset[str]:
        return frozenset({".rs"})

    def parse(self, source_code: str, file_path: str, content_hash: str) -> ParsedFile:
        """Parse Rust source code and extract symbols and references."""
        source_bytes = source_code.encode("utf-8")
        tree = self._parser.parse(source_bytes)

        ctx = ParseContext(file_path, source_bytes)

        self._process_node(tree.root_node, ctx)

        return ParsedFile(
            relative_path=file_path,
            language=self.language,
            content_hash=content_hash,
            symbols=tuple(ctx.symbols),
            references=tuple(ctx.references),
            errors=tuple(ctx.errors),
        )

    def _process_node(self, node: Node, ctx: ParseContext) -> None:
        """Recursively process AST nodes."""
        match node.type:
            case "function_item":
                self._process_function(node, ctx)
            case "struct_item":
                self._process_struct(node, ctx)
            case "enum_item":
                self._process_enum(node, ctx)
            case "trait_item":
                self._process_trait(node, ctx)
            case "impl_item":
                self._process_impl(node, ctx)
            case "mod_item":
                self._process_mod(node, ctx)
            case "use_declaration":
                self._process_use(node, ctx)
            case "call_expression":
                self._process_call(node, ctx)
            case "macro_invocation":
                self._process_macro_call(node, ctx)
            case _:
                for child in node.children:
                    self._process_node(child, ctx)

    def _process_function(self, node: Node, ctx: ParseContext) -> None:
        """Extract function definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}::{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        signature = self._extract_function_signature(node, ctx.source_bytes)
        
        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        
        # Check for visibility
        visibility = self._extract_visibility(node, ctx.source_bytes)
        if visibility:
            metadata["visibility"] = visibility
        
        # Extract attributes
        attributes = self._extract_attributes(node, ctx.source_bytes)
        if attributes:
            metadata["attributes"] = attributes
        
        # Extract doc comments
        doc_comment = self._extract_doc_comment(node, ctx.source_bytes)
        if doc_comment:
            metadata["doc_comment"] = doc_comment
        
        # Extract return type
        return_type = self._extract_return_type(node, ctx.source_bytes)
        if return_type:
            metadata["return_type"] = return_type
        
        # Extract parameters
        parameters = self._extract_parameters(node, ctx.source_bytes)
        if parameters:
            metadata["parameters"] = parameters

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.FUNCTION,
                source_code=source_code,
                signature=signature,
                parent_qualified_name=ctx.current_scope,
                metadata=metadata,
                start_line=start_line,
                end_line=end_line,
                start_column=start_column,
                end_column=end_column,
            )
        )

        # Add MEMBER reference from parent (impl block/trait) to this function
        if ctx.current_scope:
            parent_path, parent_name = self._split_qualified_name(ctx.current_scope)
            fn_path, fn_name = self._split_qualified_name(qualified_name)
            ctx.add_reference(
                Reference(
                    source_file_path=parent_path,
                    source_symbol_name=parent_name,
                    target_file_path=fn_path,
                    target_symbol_name=fn_name,
                    reference_type=ReferenceType.MEMBER,
                )
            )

        ctx.push_scope(qualified_name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_struct(self, node: Node, ctx: ParseContext) -> None:
        """Extract struct definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}::{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        visibility = self._extract_visibility(node, ctx.source_bytes)
        if visibility:
            metadata["visibility"] = visibility
        attributes = self._extract_attributes(node, ctx.source_bytes)
        if attributes:
            metadata["attributes"] = attributes
        doc_comment = self._extract_doc_comment(node, ctx.source_bytes)
        if doc_comment:
            metadata["doc_comment"] = doc_comment

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.STRUCT,
                source_code=source_code,
                parent_qualified_name=ctx.current_scope,
                metadata=metadata,
                start_line=start_line,
                end_line=end_line,
                start_column=start_column,
                end_column=end_column,
            )
        )

    def _process_enum(self, node: Node, ctx: ParseContext) -> None:
        """Extract enum definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}::{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        visibility = self._extract_visibility(node, ctx.source_bytes)
        if visibility:
            metadata["visibility"] = visibility
        attributes = self._extract_attributes(node, ctx.source_bytes)
        if attributes:
            metadata["attributes"] = attributes
        doc_comment = self._extract_doc_comment(node, ctx.source_bytes)
        if doc_comment:
            metadata["doc_comment"] = doc_comment

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.ENUM,
                source_code=source_code,
                parent_qualified_name=ctx.current_scope,
                metadata=metadata,
                start_line=start_line,
                end_line=end_line,
                start_column=start_column,
                end_column=end_column,
            )
        )

    def _process_trait(self, node: Node, ctx: ParseContext) -> None:
        """Extract trait definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}::{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        visibility = self._extract_visibility(node, ctx.source_bytes)
        if visibility:
            metadata["visibility"] = visibility
        attributes = self._extract_attributes(node, ctx.source_bytes)
        if attributes:
            metadata["attributes"] = attributes
        doc_comment = self._extract_doc_comment(node, ctx.source_bytes)
        if doc_comment:
            metadata["doc_comment"] = doc_comment

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.TRAIT,
                source_code=source_code,
                parent_qualified_name=ctx.current_scope,
                metadata=metadata,
                start_line=start_line,
                end_line=end_line,
                start_column=start_column,
                end_column=end_column,
            )
        )

        ctx.push_scope(qualified_name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_impl(self, node: Node, ctx: ParseContext) -> None:
        """Extract impl block."""
        source_code = self._get_node_text(node, ctx.source_bytes)

        # Get the type being implemented for
        type_node = node.child_by_field_name("type")
        if not type_node:
            return

        type_name = self._get_node_text(type_node, ctx.source_bytes)

        # Check if this is a trait implementation
        trait_node = node.child_by_field_name("trait")
        if trait_node:
            trait_name = self._get_node_text(trait_node, ctx.source_bytes)
            impl_name = f"impl {trait_name} for {type_name}"

            # Add inheritance reference
            if ctx.current_scope:
                qualified_name = f"{ctx.current_scope}::{impl_name}"
            else:
                qualified_name = self._build_qualified_name(ctx.file_path, impl_name)

            source_path, source_name = self._split_qualified_name(qualified_name)
            ctx.add_reference(
                Reference(
                    source_file_path=source_path,
                    source_symbol_name=source_name,
                    target_file_path=trait_name,
                    target_symbol_name=trait_name,
                    reference_type=ReferenceType.INHERITANCE,
                )
            )
        else:
            impl_name = f"impl {type_name}"
            if ctx.current_scope:
                qualified_name = f"{ctx.current_scope}::{impl_name}"
            else:
                qualified_name = self._build_qualified_name(ctx.file_path, impl_name)

        ctx.add_symbol(
            Symbol(
                name=impl_name,
                qualified_name=qualified_name,
                kind=SymbolKind.IMPL,
                source_code=source_code,
                parent_qualified_name=ctx.current_scope,
            )
        )

        ctx.push_scope(qualified_name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_mod(self, node: Node, ctx: ParseContext) -> None:
        """Extract module definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}::{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.MODULE,
                source_code=source_code,
                parent_qualified_name=ctx.current_scope,
            )
        )

        ctx.push_scope(qualified_name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_use(self, node: Node, ctx: ParseContext) -> None:
        """Extract use statement."""
        source_code = self._get_node_text(node, ctx.source_bytes)

        # Find the use path
        for child in node.children:
            if child.type in ("use_as_clause", "scoped_use_list", "use_wildcard", "scoped_identifier"):
                import_path = self._extract_use_path(child, ctx.source_bytes)
                if import_path:
                    qualified_name = self._build_qualified_name(
                        ctx.file_path, f"use:{import_path}"
                    )

                    ctx.add_symbol(
                        Symbol(
                            name=import_path.split("::")[-1],
                            qualified_name=qualified_name,
                            kind=SymbolKind.IMPORT,
                            source_code=source_code,
                        )
                    )

                    source_file_path = self._file_path_to_dot_notation(ctx.file_path)
                    # Rust uses :: as separator
                    if "::" in import_path:
                        target_path = "::".join(import_path.split("::")[:-1])
                        target_name = import_path.split("::")[-1]
                    else:
                        target_path = import_path
                        target_name = import_path

                    ctx.add_reference(
                        Reference(
                            source_file_path=source_file_path,
                            source_symbol_name="<file>",
                            target_file_path=target_path,
                            target_symbol_name=target_name,
                            reference_type=ReferenceType.IMPORT,
                        )
                    )

    def _extract_use_path(self, node: Node, source_bytes: bytes) -> str | None:
        """Extract the path from a use statement."""
        return self._get_node_text(node, source_bytes).replace(" ", "")

    def _process_call(self, node: Node, ctx: ParseContext) -> None:
        """Extract function call as reference."""
        if not ctx.current_scope:
            # Still process arguments for nested calls
            args = node.child_by_field_name("arguments")
            if args:
                for child in args.children:
                    self._process_node(child, ctx)
            return

        func_node = node.child_by_field_name("function")
        if not func_node:
            return

        call_name = self._get_node_text(func_node, ctx.source_bytes)

        source_path, source_name = self._split_qualified_name(ctx.current_scope)
        
        # Split call name (Rust uses :: as separator)
        if "::" in call_name:
            target_path = "::".join(call_name.split("::")[:-1])
            target_name = call_name.split("::")[-1]
        else:
            target_path = source_path
            target_name = call_name

        ctx.add_reference(
            Reference(
                source_file_path=source_path,
                source_symbol_name=source_name,
                target_file_path=target_path,
                target_symbol_name=target_name,
                reference_type=ReferenceType.CALL,
            )
        )

        # Process arguments for nested calls
        args = node.child_by_field_name("arguments")
        if args:
            for child in args.children:
                self._process_node(child, ctx)

    def _process_macro_call(self, node: Node, ctx: ParseContext) -> None:
        """Extract macro invocation as reference."""
        if not ctx.current_scope:
            return

        macro_node = node.child_by_field_name("macro")
        if macro_node:
            macro_name = self._get_node_text(macro_node, ctx.source_bytes)
            source_path, source_name = self._split_qualified_name(ctx.current_scope)
            
            ctx.add_reference(
                Reference(
                    source_file_path=source_path,
                    source_symbol_name=source_name,
                    target_file_path=macro_name,
                    target_symbol_name=f"{macro_name}!",
                    reference_type=ReferenceType.CALL,
                )
            )

    def _extract_function_signature(self, node: Node, source_bytes: bytes) -> str:
        """Extract function signature."""
        body = node.child_by_field_name("body")
        if body:
            return source_bytes[node.start_byte : body.start_byte].decode("utf-8").strip()
        return self._get_node_text(node, source_bytes).split("{")[0].strip()

    def _extract_visibility(self, node: Node, source_bytes: bytes) -> str | None:
        """Extract visibility modifier (pub, pub(crate), etc.)."""
        for child in node.children:
            if child.type == "visibility_modifier":
                return self._get_node_text(child, source_bytes)
        return None
    
    def _extract_attributes(self, node: Node, source_bytes: bytes) -> list[str]:
        """Extract attributes (e.g., #[derive(...)], #[test])."""
        attributes: list[str] = []
        for child in node.children:
            if child.type == "attribute_item":
                attr_text = self._get_node_text(child, source_bytes)
                if not attr_text.startswith("#"):
                    attr_text = "#" + attr_text
                attributes.append(attr_text)
        return attributes
    
    def _extract_doc_comment(self, node: Node, source_bytes: bytes) -> str | None:
        """Extract doc comment (/// or //!) preceding a node."""
        parent = node.parent
        if not parent:
            return None
        
        # Find the node's index in parent's children
        node_index = -1
        for i, child in enumerate(parent.children):
            if child == node:
                node_index = i
                break
        
        if node_index <= 0:
            return None
        
        # Check previous siblings for doc comments
        doc_lines = []
        for i in range(node_index - 1, -1, -1):
            prev_sibling = parent.children[i]
            if prev_sibling.type == "line_comment":
                comment_text = self._get_node_text(prev_sibling, source_bytes).strip()
                if comment_text.startswith("///") or comment_text.startswith("//!"):
                    # Extract doc comment content
                    line = comment_text.removeprefix("///").removeprefix("//!").strip()
                    if line:
                        doc_lines.insert(0, line)
                else:
                    # Stop at first non-doc comment
                    break
            else:
                # Stop at first non-comment
                break
        
        return "\n".join(doc_lines) if doc_lines else None
    
    def _extract_return_type(self, node: Node, source_bytes: bytes) -> str | None:
        """Extract return type from a function declaration."""
        return_type_node = node.child_by_field_name("return_type")
        if return_type_node:
            return self._get_node_text(return_type_node, source_bytes)
        return None
    
    def _extract_parameters(self, node: Node, source_bytes: bytes) -> list[dict[str, str | None]]:
        """Extract parameter information from a function declaration."""
        parameters: list[dict[str, str | None]] = []
        params_node = node.child_by_field_name("parameters")
        if not params_node:
            return parameters
        
        for child in params_node.children:
            if child.type == "parameter":
                name_node = child.child_by_field_name("pattern")
                type_node = child.child_by_field_name("type")
                
                name = None
                if name_node:
                    # Pattern can be identifier or more complex
                    if name_node.type == "identifier":
                        name = self._get_node_text(name_node, source_bytes)
                    else:
                        name = self._get_node_text(name_node, source_bytes)
                
                param_info: dict[str, str | None] = {
                    "name": name,
                    "type": self._get_node_text(type_node, source_bytes) if type_node else None,
                }
                parameters.append(param_info)
        
        return parameters

    def _get_node_text(self, node: Node, source_bytes: bytes) -> str:
        """Extract text from node."""
        return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def _file_path_to_dot_notation(self, file_path: str) -> str:
        """Convert file path to dot notation."""
        path = file_path
        for ext in self.file_extensions:
            if path.endswith(ext):
                path = path[:-len(ext)]
                break
        return path.replace("/", ".").replace("\\", ".")
    
    def _split_qualified_name(self, qualified_name: str) -> tuple[str, str]:
        """Split qualified name into (path, name). Handles both . and :: separators."""
        # Rust uses :: as separator
        if "::" in qualified_name:
            parts = qualified_name.rsplit("::", 1)
            return (parts[0], parts[1])
        # Fall back to . for file paths
        if "." in qualified_name:
            parts = qualified_name.rsplit(".", 1)
            return (parts[0], parts[1])
        return (qualified_name, qualified_name)
