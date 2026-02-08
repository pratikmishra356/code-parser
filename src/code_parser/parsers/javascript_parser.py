"""JavaScript language parser using tree-sitter."""

import tree_sitter_javascript as ts_javascript
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


class JavaScriptParser(LanguageParser):
    """
    Parser for JavaScript source code.
    
    Extracts functions, classes, arrow functions, and call references
    using tree-sitter-javascript.
    """

    def __init__(self) -> None:
        self._language = Language(ts_javascript.language())
        self._parser = Parser(self._language)

    @property
    def language(self) -> CodeLanguage:
        return CodeLanguage.JAVASCRIPT

    @property
    def file_extensions(self) -> frozenset[str]:
        return frozenset({".js", ".mjs", ".cjs"})

    def parse(self, source_code: str, file_path: str, content_hash: str) -> ParsedFile:
        """Parse JavaScript source code and extract symbols and references."""
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
            case "function_declaration":
                self._process_function(node, ctx)
            case "class_declaration":
                self._process_class(node, ctx)
            case "method_definition":
                self._process_method(node, ctx)
            case "arrow_function":
                self._process_arrow_function(node, ctx)
            case "variable_declarator":
                self._process_variable_declarator(node, ctx)
            case "import_statement":
                self._process_import(node, ctx)
            case "call_expression":
                self._process_call(node, ctx)
            case "new_expression":
                self._process_new_expression(node, ctx)
            case _:
                for child in node.children:
                    self._process_node(child, ctx)

    def _process_function(self, node: Node, ctx: ParseContext) -> None:
        """Extract function declaration."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        signature = self._extract_function_signature(node, ctx.source_bytes)
        
        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        
        # Extract JSDoc
        jsdoc = self._extract_jsdoc(node, ctx.source_bytes)
        if jsdoc:
            metadata["jsdoc"] = jsdoc
        
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

        ctx.push_scope(qualified_name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_class(self, node: Node, ctx: ParseContext) -> None:
        """Extract class declaration."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        source_path, source_name = self._split_qualified_name(qualified_name)

        # Check for extends
        for child in node.children:
            if child.type == "class_heritage":
                for heritage_child in child.children:
                    if heritage_child.type == "identifier":
                        base_name = self._get_node_text(heritage_child, ctx.source_bytes)
                        ctx.add_reference(
                            Reference(
                                source_file_path=source_path,
                                source_symbol_name=source_name,
                                target_file_path=base_name,
                                target_symbol_name=base_name,
                                reference_type=ReferenceType.INHERITANCE,
                            )
                        )

        signature = self._extract_class_signature(node, ctx.source_bytes)
        
        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        
        # Extract JSDoc
        jsdoc = self._extract_jsdoc(node, ctx.source_bytes)
        if jsdoc:
            metadata["jsdoc"] = jsdoc

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

        ctx.push_scope(qualified_name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_method(self, node: Node, ctx: ParseContext) -> None:
        """Extract method definition in a class."""
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
        
        # Extract JSDoc
        jsdoc = self._extract_jsdoc(node, ctx.source_bytes)
        if jsdoc:
            metadata["jsdoc"] = jsdoc
        
        # Extract parameters
        parameters = self._extract_parameters(node, ctx.source_bytes)
        if parameters:
            metadata["parameters"] = parameters

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.METHOD,
                source_code=source_code,
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

        ctx.push_scope(qualified_name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_arrow_function(self, node: Node, ctx: ParseContext) -> None:
        """Process arrow function - typically assigned to a variable."""
        # Arrow functions don't have names, they're handled via variable_declarator
        body = node.child_by_field_name("body")
        if body:
            for child in body.children if body.type == "statement_block" else [body]:
                self._process_node(child, ctx)

    def _process_variable_declarator(self, node: Node, ctx: ParseContext) -> None:
        """Extract variable declarations, including arrow function assignments."""
        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")

        if not name_node or name_node.type != "identifier":
            return

        name = self._get_node_text(name_node, ctx.source_bytes)

        # Check if this is an arrow function or regular function expression
        if value_node and value_node.type in ("arrow_function", "function"):
            source_code = self._get_node_text(node.parent or node, ctx.source_bytes)

            if ctx.current_scope:
                qualified_name = f"{ctx.current_scope}.{name}"
            else:
                qualified_name = self._build_qualified_name(ctx.file_path, name)

            # Extract position information
            start_line, end_line, start_column, end_column = self._extract_position(node)
            
            # Extract enhanced metadata
            metadata: dict[str, str | int | bool | list] = {"is_arrow": value_node.type == "arrow_function"}
            
            # Extract parameters
            parameters = self._extract_parameters(value_node, ctx.source_bytes)
            if parameters:
                metadata["parameters"] = parameters
            
            ctx.add_symbol(
                Symbol(
                    name=name,
                    qualified_name=qualified_name,
                    kind=SymbolKind.FUNCTION,
                    source_code=source_code,
                    parent_qualified_name=ctx.current_scope,
                    metadata=metadata,
                    start_line=start_line,
                    end_line=end_line,
                    start_column=start_column,
                    end_column=end_column,
                )
            )

            # Process the function body
            ctx.push_scope(qualified_name)
            body = value_node.child_by_field_name("body")
            if body:
                if body.type == "statement_block":
                    for child in body.children:
                        self._process_node(child, ctx)
                else:
                    self._process_node(body, ctx)
            ctx.pop_scope()
        elif value_node:
            # Regular variable, process its value for calls
            self._process_node(value_node, ctx)

    def _process_import(self, node: Node, ctx: ParseContext) -> None:
        """Extract import statement."""
        source_code = self._get_node_text(node, ctx.source_bytes)

        # Find the source module
        source_node = node.child_by_field_name("source")
        if not source_node:
            return

        module_name = self._get_node_text(source_node, ctx.source_bytes).strip("'\"")

        # Find imported names
        for child in node.children:
            if child.type == "import_clause":
                self._extract_import_names(child, module_name, source_code, ctx)

    def _extract_import_names(
        self, node: Node, module_name: str, source_code: str, ctx: ParseContext
    ) -> None:
        """Extract names from import clause."""
        for child in node.children:
            if child.type == "identifier":
                # Default import
                name = self._get_node_text(child, ctx.source_bytes)
                self._add_import(name, module_name, source_code, ctx)
            elif child.type == "named_imports":
                for spec in child.children:
                    if spec.type == "import_specifier":
                        name_node = spec.child_by_field_name("name")
                        if name_node:
                            name = self._get_node_text(name_node, ctx.source_bytes)
                            self._add_import(name, f"{module_name}.{name}", source_code, ctx)
            elif child.type == "namespace_import":
                for subchild in child.children:
                    if subchild.type == "identifier":
                        name = self._get_node_text(subchild, ctx.source_bytes)
                        self._add_import(name, module_name, source_code, ctx)

    def _add_import(
        self, name: str, full_path: str, source_code: str, ctx: ParseContext
    ) -> None:
        """Add import symbol and reference."""
        qualified_name = self._build_qualified_name(ctx.file_path, f"import:{full_path}")

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.IMPORT,
                source_code=source_code,
            )
        )

        source_file_path = self._file_path_to_dot_notation(ctx.file_path)
        
        # Split path into target path and name
        if "." in full_path:
            target_path = ".".join(full_path.split(".")[:-1])
            target_name = full_path.split(".")[-1]
        else:
            target_path = full_path
            target_name = name

        ctx.add_reference(
            Reference(
                source_file_path=source_file_path,
                source_symbol_name="<file>",
                target_file_path=target_path,
                target_symbol_name=target_name,
                reference_type=ReferenceType.IMPORT,
            )
        )

    def _process_call(self, node: Node, ctx: ParseContext) -> None:
        """Extract function call as reference."""
        if not ctx.current_scope:
            # Process arguments even if not in scope
            args = node.child_by_field_name("arguments")
            if args:
                for child in args.children:
                    self._process_node(child, ctx)
            return

        func_node = node.child_by_field_name("function")
        if not func_node:
            return

        call_name = self._resolve_call_name(func_node, ctx.source_bytes)
        if call_name:
            source_path, source_name = self._split_qualified_name(ctx.current_scope)
            
            # Split call name
            if "." in call_name:
                target_path = ".".join(call_name.split(".")[:-1])
                target_name = call_name.split(".")[-1]
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

    def _process_new_expression(self, node: Node, ctx: ParseContext) -> None:
        """Extract new ClassName() as instantiation reference."""
        if not ctx.current_scope:
            return

        constructor = node.child_by_field_name("constructor")
        if constructor:
            class_name = self._get_node_text(constructor, ctx.source_bytes)
            source_path, source_name = self._split_qualified_name(ctx.current_scope)
            
            ctx.add_reference(
                Reference(
                    source_file_path=source_path,
                    source_symbol_name=source_name,
                    target_file_path=class_name,
                    target_symbol_name=class_name,
                    reference_type=ReferenceType.INSTANTIATION,
                )
            )

        # Process arguments
        args = node.child_by_field_name("arguments")
        if args:
            for child in args.children:
                self._process_node(child, ctx)

    def _resolve_call_name(self, node: Node, source_bytes: bytes) -> str | None:
        """Resolve the name of a called function."""
        match node.type:
            case "identifier":
                return self._get_node_text(node, source_bytes)
            case "member_expression":
                return self._get_node_text(node, source_bytes)
            case _:
                return None

    def _extract_function_signature(self, node: Node, source_bytes: bytes) -> str:
        """Extract function signature."""
        body = node.child_by_field_name("body")
        if body:
            return source_bytes[node.start_byte : body.start_byte].decode("utf-8").strip()
        return self._get_node_text(node, source_bytes).split("{")[0].strip()

    def _extract_class_signature(self, node: Node, source_bytes: bytes) -> str:
        """Extract class signature."""
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
    
    def _extract_jsdoc(self, node: Node, source_bytes: bytes) -> str | None:
        """Extract JSDoc comment preceding a node."""
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
        
        # Check previous siblings for JSDoc
        for i in range(node_index - 1, -1, -1):
            prev_sibling = parent.children[i]
            if prev_sibling.type == "comment":
                comment_text = self._get_node_text(prev_sibling, source_bytes)
                if comment_text.strip().startswith("/**"):
                    # Extract JSDoc content
                    lines = comment_text.split("\n")
                    jsdoc_lines = []
                    for line in lines:
                        line = line.strip()
                        line = line.removeprefix("/**").removesuffix("*/").strip()
                        line = line.removeprefix("*").strip()
                        if line:
                            jsdoc_lines.append(line)
                    if jsdoc_lines:
                        return "\n".join(jsdoc_lines)
        
        return None
    
    def _extract_parameters(self, node: Node, source_bytes: bytes) -> list[dict[str, str | None]]:
        """Extract parameter information from a function declaration."""
        parameters: list[dict[str, str | None]] = []
        params_node = node.child_by_field_name("parameters")
        if not params_node:
            return parameters
        
        for child in params_node.children:
            if child.type == "identifier":
                param_info: dict[str, str | None] = {
                    "name": self._get_node_text(child, source_bytes),
                    "type": None,  # JavaScript doesn't have type annotations in standard syntax
                    "default": None,
                }
                parameters.append(param_info)
            elif child.type == "assignment_pattern":
                # Parameter with default value
                name_node = child.child_by_field_name("left")
                default_node = child.child_by_field_name("right")
                if name_node and name_node.type == "identifier":
                    param_info = {
                        "name": self._get_node_text(name_node, source_bytes),
                        "type": None,
                        "default": self._get_node_text(default_node, source_bytes) if default_node else None,
                    }
                    parameters.append(param_info)
        
        return parameters