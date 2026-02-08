"""Java language parser using tree-sitter."""

import tree_sitter_java as ts_java
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


class JavaParser(LanguageParser):
    """
    Parser for Java source code.
    
    Extracts classes, interfaces, methods, and call references
    using tree-sitter-java.
    """

    def __init__(self) -> None:
        self._language = Language(ts_java.language())
        self._parser = Parser(self._language)

    @property
    def language(self) -> CodeLanguage:
        return CodeLanguage.JAVA

    @property
    def file_extensions(self) -> frozenset[str]:
        return frozenset({".java"})

    def parse(self, source_code: str, file_path: str, content_hash: str) -> ParsedFile:
        """Parse Java source code and extract symbols and references."""
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
            case "class_declaration":
                self._process_class(node, ctx)
            case "interface_declaration":
                self._process_interface(node, ctx)
            case "enum_declaration":
                self._process_enum(node, ctx)
            case "method_declaration":
                self._process_method(node, ctx)
            case "constructor_declaration":
                self._process_constructor(node, ctx)
            case "import_declaration":
                self._process_import(node, ctx)
            case "method_invocation":
                self._process_method_call(node, ctx)
            case "object_creation_expression":
                self._process_instantiation(node, ctx)
            case _:
                for child in node.children:
                    self._process_node(child, ctx)

    def _process_class(self, node: Node, ctx: ParseContext) -> None:
        """Extract class definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        # Extract source path and name for references
        source_path, source_name = self._split_qualified_name(qualified_name)

        # Extract superclass
        superclass = node.child_by_field_name("superclass")
        if superclass:
            for child in superclass.children:
                if child.type == "type_identifier":
                    base_name = self._get_node_text(child, ctx.source_bytes)
                    ctx.add_reference(
                        Reference(
                            source_file_path=source_path,
                            source_symbol_name=source_name,
                            target_file_path=base_name,
                            target_symbol_name=base_name,
                            reference_type=ReferenceType.INHERITANCE,
                        )
                    )

        # Extract interfaces
        interfaces = node.child_by_field_name("interfaces")
        if interfaces:
            for child in interfaces.children:
                if child.type == "type_identifier":
                    iface_name = self._get_node_text(child, ctx.source_bytes)
                    ctx.add_reference(
                        Reference(
                            source_file_path=source_path,
                            source_symbol_name=source_name,
                            target_file_path=iface_name,
                            target_symbol_name=iface_name,
                            reference_type=ReferenceType.INHERITANCE,
                        )
                    )

        signature = self._extract_class_signature(node, ctx.source_bytes)
        
        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        
        # Extract annotations
        annotations = self._extract_annotations(node, ctx.source_bytes)
        if annotations:
            metadata["annotations"] = annotations
        
        # Extract modifiers (public, private, abstract, etc.)
        modifiers = self._extract_modifiers(node, ctx.source_bytes)
        if modifiers:
            metadata["modifiers"] = modifiers
        
        # Extract superclass and interfaces
        base_classes = []
        if superclass:
            for child in superclass.children:
                if child.type == "type_identifier":
                    base_classes.append(self._get_node_text(child, ctx.source_bytes))
        if interfaces:
            for child in interfaces.children:
                if child.type == "type_identifier":
                    base_classes.append(self._get_node_text(child, ctx.source_bytes))
        if base_classes:
            metadata["base_classes"] = base_classes
        
        # Extract Javadoc
        javadoc = self._extract_javadoc(node, ctx.source_bytes)
        if javadoc:
            metadata["javadoc"] = javadoc

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.CLASS,
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

        # Process class body
        ctx.push_scope(qualified_name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_interface(self, node: Node, ctx: ParseContext) -> None:
        """Extract interface definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)
        
        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        annotations = self._extract_annotations(node, ctx.source_bytes)
        if annotations:
            metadata["annotations"] = annotations
        modifiers = self._extract_modifiers(node, ctx.source_bytes)
        if modifiers:
            metadata["modifiers"] = modifiers
        javadoc = self._extract_javadoc(node, ctx.source_bytes)
        if javadoc:
            metadata["javadoc"] = javadoc

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.INTERFACE,
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

    def _process_enum(self, node: Node, ctx: ParseContext) -> None:
        """Extract enum definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)
        
        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        annotations = self._extract_annotations(node, ctx.source_bytes)
        if annotations:
            metadata["annotations"] = annotations
        modifiers = self._extract_modifiers(node, ctx.source_bytes)
        if modifiers:
            metadata["modifiers"] = modifiers
        javadoc = self._extract_javadoc(node, ctx.source_bytes)
        if javadoc:
            metadata["javadoc"] = javadoc

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

    def _process_method(self, node: Node, ctx: ParseContext) -> None:
        """Extract method definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        signature = self._extract_method_signature(node, ctx.source_bytes)
        
        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        
        # Extract annotations
        annotations = self._extract_annotations(node, ctx.source_bytes)
        if annotations:
            metadata["annotations"] = annotations
        
        # Extract modifiers
        modifiers = self._extract_modifiers(node, ctx.source_bytes)
        if modifiers:
            metadata["modifiers"] = modifiers
        
        # Extract return type
        return_type = self._extract_return_type(node, ctx.source_bytes)
        if return_type:
            metadata["return_type"] = return_type
        
        # Extract parameters
        parameters = self._extract_parameters(node, ctx.source_bytes)
        if parameters:
            metadata["parameters"] = parameters
        
        # Extract Javadoc
        javadoc = self._extract_javadoc(node, ctx.source_bytes)
        if javadoc:
            metadata["javadoc"] = javadoc

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.METHOD,
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

        # Add MEMBER reference from parent class to this method for traversal
        if ctx.current_scope:
            parent_path, parent_name = self._split_qualified_name(ctx.current_scope)
            method_path, method_name = self._split_qualified_name(qualified_name)
            ctx.add_reference(
                Reference(
                    source_file_path=parent_path,
                    source_symbol_name=parent_name,
                    target_file_path=method_path,
                    target_symbol_name=method_name,
                    reference_type=ReferenceType.MEMBER,
                )
            )

        # Process method body for calls
        ctx.push_scope(qualified_name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_constructor(self, node: Node, ctx: ParseContext) -> None:
        """Extract constructor definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {"is_constructor": True}
        annotations = self._extract_annotations(node, ctx.source_bytes)
        if annotations:
            metadata["annotations"] = annotations
        modifiers = self._extract_modifiers(node, ctx.source_bytes)
        if modifiers:
            metadata["modifiers"] = modifiers
        parameters = self._extract_parameters(node, ctx.source_bytes)
        if parameters:
            metadata["parameters"] = parameters
        javadoc = self._extract_javadoc(node, ctx.source_bytes)
        if javadoc:
            metadata["javadoc"] = javadoc

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.METHOD,
                source_code=source_code,
                signature=f"{name}(...)",
                parent_qualified_name=ctx.current_scope,
                metadata=metadata,
                start_line=start_line,
                end_line=end_line,
                start_column=start_column,
                end_column=end_column,
            )
        )

        # Add MEMBER reference from parent class to this constructor
        if ctx.current_scope:
            parent_path, parent_name = self._split_qualified_name(ctx.current_scope)
            ctor_path, ctor_name = self._split_qualified_name(qualified_name)
            ctx.add_reference(
                Reference(
                    source_file_path=parent_path,
                    source_symbol_name=parent_name,
                    target_file_path=ctor_path,
                    target_symbol_name=ctor_name,
                    reference_type=ReferenceType.MEMBER,
                )
            )

        ctx.push_scope(qualified_name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_import(self, node: Node, ctx: ParseContext) -> None:
        """Extract import statement."""
        source_code = self._get_node_text(node, ctx.source_bytes)

        # Find the imported name
        for child in node.children:
            if child.type == "scoped_identifier":
                import_name = self._get_node_text(child, ctx.source_bytes)

                qualified_name = self._build_qualified_name(ctx.file_path, f"import:{import_name}")
                ctx.add_symbol(
                    Symbol(
                        name=import_name,
                        qualified_name=qualified_name,
                        kind=SymbolKind.IMPORT,
                        source_code=source_code,
                    )
                )

                # Split import path into package and class
                source_file_path = self._file_path_to_dot_notation(ctx.file_path)
                if "." in import_name:
                    target_path = ".".join(import_name.split(".")[:-1])
                    target_name = import_name.split(".")[-1]
                else:
                    target_path = import_name
                    target_name = import_name

                ctx.add_reference(
                    Reference(
                        source_file_path=source_file_path,
                        source_symbol_name="<file>",
                        target_file_path=target_path,
                        target_symbol_name=target_name,
                        reference_type=ReferenceType.IMPORT,
                    )
                )

    def _process_method_call(self, node: Node, ctx: ParseContext) -> None:
        """Extract method invocation as reference."""
        if not ctx.current_scope:
            return

        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        method_name = self._get_node_text(name_node, ctx.source_bytes)

        # Get source path and name
        source_path, source_name = self._split_qualified_name(ctx.current_scope)

        # Check for object reference
        obj_node = node.child_by_field_name("object")
        if obj_node:
            obj_name = self._get_node_text(obj_node, ctx.source_bytes)
            # Clean up chained calls
            obj_name = obj_name.split("(")[0].split(".")[0]
            target_path = obj_name
        else:
            # Same class call
            target_path = source_path

        ctx.add_reference(
            Reference(
                source_file_path=source_path,
                source_symbol_name=source_name,
                target_file_path=target_path,
                target_symbol_name=method_name,
                reference_type=ReferenceType.CALL,
            )
        )

        # Process arguments for nested calls
        args = node.child_by_field_name("arguments")
        if args:
            for child in args.children:
                self._process_node(child, ctx)

    def _process_instantiation(self, node: Node, ctx: ParseContext) -> None:
        """Extract object creation (new ClassName())."""
        if not ctx.current_scope:
            return

        type_node = node.child_by_field_name("type")
        if type_node:
            type_name = self._get_node_text(type_node, ctx.source_bytes)
            source_path, source_name = self._split_qualified_name(ctx.current_scope)
            
            ctx.add_reference(
                Reference(
                    source_file_path=source_path,
                    source_symbol_name=source_name,
                    target_file_path=type_name,
                    target_symbol_name=type_name,
                    reference_type=ReferenceType.INSTANTIATION,
                )
            )

        # Process constructor arguments
        args = node.child_by_field_name("arguments")
        if args:
            for child in args.children:
                self._process_node(child, ctx)

    def _extract_class_signature(self, node: Node, source_bytes: bytes) -> str:
        """Extract class signature."""
        parts = []

        # Modifiers
        for child in node.children:
            if child.type == "modifiers":
                parts.append(self._get_node_text(child, source_bytes))

        parts.append("class")

        name_node = node.child_by_field_name("name")
        if name_node:
            parts.append(self._get_node_text(name_node, source_bytes))

        superclass = node.child_by_field_name("superclass")
        if superclass:
            parts.append(self._get_node_text(superclass, source_bytes))

        interfaces = node.child_by_field_name("interfaces")
        if interfaces:
            parts.append(self._get_node_text(interfaces, source_bytes))

        return " ".join(parts)

    def _extract_method_signature(self, node: Node, source_bytes: bytes) -> str:
        """Extract method signature."""
        # Get everything up to the body
        body = node.child_by_field_name("body")
        if body:
            return source_bytes[node.start_byte : body.start_byte].decode("utf-8").strip()
        return self._get_node_text(node, source_bytes).split("{")[0].strip()

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
        """Split qualified name into (path, name)."""
        if "." in qualified_name:
            parts = qualified_name.rsplit(".", 1)
            return (parts[0], parts[1])
        return (qualified_name, qualified_name)
    
    def _extract_annotations(self, node: Node, source_bytes: bytes) -> list[str]:
        """Extract annotations from a node."""
        annotations: list[str] = []
        for child in node.children:
            if child.type == "modifiers":
                for modifier_child in child.children:
                    if modifier_child.type == "marker_annotation":
                        ann_name = modifier_child.child_by_field_name("name")
                        if ann_name:
                            annotations.append(f"@{self._get_node_text(ann_name, source_bytes)}")
                    elif modifier_child.type == "annotation":
                        ann_name = modifier_child.child_by_field_name("name")
                        if ann_name:
                            ann_text = f"@{self._get_node_text(ann_name, source_bytes)}"
                            # Include arguments if present
                            args = modifier_child.child_by_field_name("arguments")
                            if args:
                                ann_text += self._get_node_text(args, source_bytes)
                            annotations.append(ann_text)
        return annotations
    
    def _extract_modifiers(self, node: Node, source_bytes: bytes) -> list[str]:
        """Extract access modifiers and other modifiers."""
        modifiers: list[str] = []
        for child in node.children:
            if child.type == "modifiers":
                for modifier_child in child.children:
                    if modifier_child.type in ("public", "private", "protected", "static", 
                                             "final", "abstract", "synchronized", "volatile", 
                                             "transient", "native", "strictfp"):
                        modifiers.append(modifier_child.type)
        return modifiers
    
    def _extract_return_type(self, node: Node, source_bytes: bytes) -> str | None:
        """Extract return type from a method declaration."""
        return_type_node = node.child_by_field_name("type")
        if return_type_node:
            return self._get_node_text(return_type_node, source_bytes)
        return None
    
    def _extract_parameters(self, node: Node, source_bytes: bytes) -> list[dict[str, str | None]]:
        """Extract parameter information from a method declaration."""
        parameters: list[dict[str, str | None]] = []
        params_node = node.child_by_field_name("parameters")
        if not params_node:
            return parameters
        
        for child in params_node.children:
            if child.type == "formal_parameter":
                type_node = child.child_by_field_name("type")
                name_node = child.child_by_field_name("name")
                
                param_info: dict[str, str | None] = {
                    "name": self._get_node_text(name_node, source_bytes) if name_node else None,
                    "type": self._get_node_text(type_node, source_bytes) if type_node else None,
                }
                parameters.append(param_info)
        
        return parameters
    
    def _extract_javadoc(self, node: Node, source_bytes: bytes) -> str | None:
        """Extract Javadoc comment preceding a node."""
        # Javadoc comments are typically before the node
        # We need to check the parent's children
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
        
        # Check previous siblings for Javadoc
        for i in range(node_index - 1, -1, -1):
            prev_sibling = parent.children[i]
            if prev_sibling.type == "line_comment":
                comment_text = self._get_node_text(prev_sibling, source_bytes)
                if comment_text.strip().startswith("/**"):
                    # Extract Javadoc content
                    lines = comment_text.split("\n")
                    javadoc_lines = []
                    for line in lines:
                        line = line.strip()
                        # Remove comment markers
                        line = line.removeprefix("/**").removesuffix("*/").strip()
                        line = line.removeprefix("*").strip()
                        if line:
                            javadoc_lines.append(line)
                    if javadoc_lines:
                        return "\n".join(javadoc_lines)
        
        return None