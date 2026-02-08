"""Python language parser using tree-sitter."""

import tree_sitter_python as ts_python
from tree_sitter import Language, Parser, Node

from code_parser.core import (
    Language as CodeLanguage,
    ParsedFile,
    Reference,
    ReferenceType,
    Symbol,
    SymbolKind,
)
from code_parser.parsers.base import LanguageParser, ParseContext


class PythonParser(LanguageParser):
    """
    Parser for Python source code.
    
    Extracts functions, classes, methods, imports, and call references
    using tree-sitter-python.
    """

    def __init__(self) -> None:
        self._language = Language(ts_python.language())
        self._parser = Parser(self._language)

    @property
    def language(self) -> CodeLanguage:
        return CodeLanguage.PYTHON

    @property
    def file_extensions(self) -> frozenset[str]:
        return frozenset({".py"})

    def parse(self, source_code: str, file_path: str, content_hash: str) -> ParsedFile:
        """Parse Python source code and extract symbols and references."""
        source_bytes = source_code.encode("utf-8")
        tree = self._parser.parse(source_bytes)

        ctx = ParseContext(file_path, source_bytes)

        # Process the AST
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
        """Recursively process AST nodes to extract symbols and references."""
        match node.type:
            case "function_definition":
                self._process_function(node, ctx)
            case "class_definition":
                self._process_class(node, ctx)
            case "import_statement":
                self._process_import(node, ctx)
            case "import_from_statement":
                self._process_import_from(node, ctx)
            case "call":
                self._process_call(node, ctx)
            case _:
                # Recurse into children for other node types
                for child in node.children:
                    self._process_node(child, ctx)

    def _process_function(self, node: Node, ctx: ParseContext) -> None:
        """Extract function or method definition."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)
        
        # Determine if this is a method (inside a class) or standalone function
        is_method = ctx.current_scope is not None and self._is_inside_class(ctx)
        kind = SymbolKind.METHOD if is_method else SymbolKind.FUNCTION

        # Build qualified name
        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        # Extract signature
        signature = self._extract_function_signature(node, ctx.source_bytes)

        # Extract decorators as metadata
        # Check if the function is inside a decorated_definition node
        parent_node = node.parent
        decorators = []
        source_node = node  # Default to function node
        
        if parent_node and parent_node.type == "decorated_definition":
            decorators = self._extract_decorators(parent_node, ctx.source_bytes)
            # Extract source from parent to include decorators
            source_node = parent_node
        
        # Extract source code (including decorators if present)
        source_code = self._get_node_text(source_node, ctx.source_bytes)
        
        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(source_node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        if decorators:
            metadata["decorators"] = decorators
        
        # Extract type hints from signature
        return_type = self._extract_return_type(node, ctx.source_bytes)
        if return_type:
            metadata["return_type"] = return_type
        
        # Extract parameter information
        parameters = self._extract_parameters(node, ctx.source_bytes)
        if parameters:
            metadata["parameters"] = parameters
        
        # Extract docstring
        docstring = self._extract_docstring(node, ctx.source_bytes)
        if docstring:
            metadata["docstring"] = docstring

        symbol = Symbol(
            name=name,
            qualified_name=qualified_name,
            kind=kind,
            source_code=source_code,
            signature=signature,
            parent_qualified_name=ctx.current_scope,
            metadata=metadata,
            start_line=start_line,
            end_line=end_line,
            start_column=start_column,
            end_column=end_column,
        )
        ctx.add_symbol(symbol)

        # Add MEMBER reference from parent class to this method for traversal
        if is_method and ctx.current_scope:
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

        # Process function body for calls
        ctx.push_scope(qualified_name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_class(self, node: Node, ctx: ParseContext) -> None:
        """Extract class definition and its members."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        name = self._get_node_text(name_node, ctx.source_bytes)

        # Build qualified name
        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        # Get source path and name for references
        source_path, source_name = self._split_qualified_name(qualified_name)

        # Extract base classes for inheritance references
        bases = self._extract_base_classes(node, ctx)
        for base_name in bases:
            ctx.add_reference(
                Reference(
                    source_file_path=source_path,
                    source_symbol_name=source_name,
                    target_file_path=base_name,
                    target_symbol_name=base_name,
                    reference_type=ReferenceType.INHERITANCE,
                )
            )

        # Extract signature (class name + bases)
        signature = self._extract_class_signature(node, ctx.source_bytes)

        # Extract decorators as metadata
        # Check if the class is inside a decorated_definition node
        parent_node = node.parent
        decorators = []
        source_node = node  # Default to class node
        
        if parent_node and parent_node.type == "decorated_definition":
            decorators = self._extract_decorators(parent_node, ctx.source_bytes)
            # Extract source from parent to include decorators
            source_node = parent_node
        
        # Extract source code (including decorators if present)
        source_code = self._get_node_text(source_node, ctx.source_bytes)
        
        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(source_node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        if decorators:
            metadata["decorators"] = decorators
        
        # Extract base classes info
        if bases:
            metadata["base_classes"] = bases
        
        # Extract docstring
        docstring = self._extract_docstring(node, ctx.source_bytes)
        if docstring:
            metadata["docstring"] = docstring

        symbol = Symbol(
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
        ctx.add_symbol(symbol)

        # Process class body
        ctx.push_scope(qualified_name)
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_import(self, node: Node, ctx: ParseContext) -> None:
        """Extract import statement."""
        source_code = self._get_node_text(node, ctx.source_bytes)

        for child in node.children:
            if child.type == "dotted_name":
                module_name = self._get_node_text(child, ctx.source_bytes)
                self._add_import_symbol_and_reference(module_name, source_code, ctx)
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                if name_node:
                    module_name = self._get_node_text(name_node, ctx.source_bytes)
                    self._add_import_symbol_and_reference(module_name, source_code, ctx)

    def _process_import_from(self, node: Node, ctx: ParseContext) -> None:
        """Extract from ... import ... statement."""
        source_code = self._get_node_text(node, ctx.source_bytes)

        # Get the module being imported from
        module_node = node.child_by_field_name("module_name")
        if not module_node:
            return

        module_name = self._get_node_text(module_node, ctx.source_bytes)

        # Get imported names
        for child in node.children:
            if child.type in ("dotted_name", "identifier"):
                if child != module_node:
                    imported_name = self._get_node_text(child, ctx.source_bytes)
                    full_name = f"{module_name}.{imported_name}"
                    self._add_import_symbol_and_reference(full_name, source_code, ctx)
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                if name_node:
                    imported_name = self._get_node_text(name_node, ctx.source_bytes)
                    full_name = f"{module_name}.{imported_name}"
                    self._add_import_symbol_and_reference(full_name, source_code, ctx)

    def _add_import_symbol_and_reference(
        self, module_name: str, source_code: str, ctx: ParseContext
    ) -> None:
        """Add both an import symbol and a reference for an import."""
        # Create import symbol
        qualified_name = self._build_qualified_name(ctx.file_path, f"import:{module_name}")

        symbol = Symbol(
            name=module_name,
            qualified_name=qualified_name,
            kind=SymbolKind.IMPORT,
            source_code=source_code,
            parent_qualified_name=ctx.current_scope,
        )
        ctx.add_symbol(symbol)

        # Create import reference
        source_file_path = self._file_path_to_dot_notation(ctx.file_path)
        
        # Split module name into path and name
        if "." in module_name:
            target_path = ".".join(module_name.split(".")[:-1])
            target_name = module_name.split(".")[-1]
        else:
            target_path = module_name
            target_name = module_name

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
        """Extract function/method call as a reference."""
        func_node = node.child_by_field_name("function")
        if not func_node:
            return

        # Get the called function name
        call_name = self._resolve_call_name(func_node, ctx.source_bytes)
        if not call_name:
            return

        # Only record calls if we're inside a function/method scope
        if ctx.current_scope:
            source_path, source_name = self._split_qualified_name(ctx.current_scope)
            
            # Split call name into target path and name
            if "." in call_name:
                target_path = ".".join(call_name.split(".")[:-1])
                target_name = call_name.split(".")[-1]
            else:
                target_path = source_path  # Same module call
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

        # Continue processing arguments for nested calls
        args = node.child_by_field_name("arguments")
        if args:
            for child in args.children:
                self._process_node(child, ctx)

    def _resolve_call_name(self, node: Node, source_bytes: bytes) -> str | None:
        """Resolve the name of a called function."""
        match node.type:
            case "identifier":
                return self._get_node_text(node, source_bytes)
            case "attribute":
                # Handle method calls like obj.method()
                return self._get_node_text(node, source_bytes)
            case _:
                return None

    def _extract_function_signature(self, node: Node, source_bytes: bytes) -> str:
        """Extract function signature (def name(params) -> return_type)."""
        parts = []

        # Get decorators
        for child in node.children:
            if child.type == "decorator":
                parts.append(self._get_node_text(child, source_bytes))

        # Get the def line (up to the colon)
        name_node = node.child_by_field_name("name")
        params_node = node.child_by_field_name("parameters")
        return_type = node.child_by_field_name("return_type")

        if name_node and params_node:
            sig = f"def {self._get_node_text(name_node, source_bytes)}{self._get_node_text(params_node, source_bytes)}"
            if return_type:
                sig += f" -> {self._get_node_text(return_type, source_bytes)}"
            parts.append(sig)

        return "\n".join(parts)

    def _extract_class_signature(self, node: Node, source_bytes: bytes) -> str:
        """Extract class signature (class Name(bases))."""
        parts = []

        # Get decorators
        for child in node.children:
            if child.type == "decorator":
                parts.append(self._get_node_text(child, source_bytes))

        # Get the class line
        name_node = node.child_by_field_name("name")
        if name_node:
            sig = f"class {self._get_node_text(name_node, source_bytes)}"

            # Add base classes if present
            superclass = node.child_by_field_name("superclasses")
            if superclass:
                sig += self._get_node_text(superclass, source_bytes)

            parts.append(sig)

        return "\n".join(parts)

    def _extract_base_classes(self, node: Node, ctx: ParseContext) -> list[str]:
        """Extract base class names from a class definition."""
        bases: list[str] = []
        superclass_node = node.child_by_field_name("superclasses")
        if not superclass_node:
            return bases

        for child in superclass_node.children:
            if child.type in ("identifier", "attribute"):
                base_name = self._get_node_text(child, ctx.source_bytes)
                bases.append(base_name)

        return bases

    def _extract_decorators(self, node: Node, source_bytes: bytes) -> list[str]:
        """Extract decorator names from a function/class definition."""
        decorators: list[str] = []
        for child in node.children:
            if child.type == "decorator":
                # Get just the decorator name/path (identifier, attribute, or call)
                # Need to include the @ symbol for pattern matching
                for subchild in child.children:
                    if subchild.type in ("identifier", "attribute", "call"):
                        dec_text = self._get_node_text(subchild, source_bytes)
                        # Prepend @ if not present
                        if not dec_text.startswith("@"):
                            dec_text = "@" + dec_text
                        decorators.append(dec_text)
                        break
        return decorators
    
    def _extract_return_type(self, node: Node, source_bytes: bytes) -> str | None:
        """Extract return type annotation from a function definition."""
        return_type_node = node.child_by_field_name("return_type")
        if return_type_node:
            return self._get_node_text(return_type_node, source_bytes)
        return None
    
    def _extract_parameters(self, node: Node, source_bytes: bytes) -> list[dict[str, str | None]]:
        """Extract parameter information from a function definition."""
        parameters: list[dict[str, str | None]] = []
        params_node = node.child_by_field_name("parameters")
        if not params_node:
            return parameters
        
        for child in params_node.children:
            if child.type == "typed_parameter":
                # Parameter with type annotation
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                default_node = child.child_by_field_name("default")
                
                param_info: dict[str, str | None] = {
                    "name": self._get_node_text(name_node, source_bytes) if name_node else None,
                    "type": self._get_node_text(type_node, source_bytes) if type_node else None,
                    "default": self._get_node_text(default_node, source_bytes) if default_node else None,
                }
                parameters.append(param_info)
            elif child.type == "identifier":
                # Simple parameter without type annotation
                param_info = {
                    "name": self._get_node_text(child, source_bytes),
                    "type": None,
                    "default": None,
                }
                parameters.append(param_info)
        
        return parameters
    
    def _extract_docstring(self, node: Node, source_bytes: bytes) -> str | None:
        """Extract docstring from a function or class definition."""
        body = node.child_by_field_name("body")
        if not body or not body.children:
            return None
        
        # Docstring is typically the first statement in the body
        first_stmt = body.children[0]
        if first_stmt.type == "expression_statement":
            # Check if it's a string literal
            for child in first_stmt.children:
                if child.type in ("string", "concatenated_string"):
                    docstring_text = self._get_node_text(child, source_bytes)
                    # Remove quotes (simple approach - handles triple quotes)
                    docstring_text = docstring_text.strip()
                    if docstring_text.startswith('"""'):
                        docstring_text = docstring_text[3:]
                    elif docstring_text.startswith("'''"):
                        docstring_text = docstring_text[3:]
                    elif docstring_text.startswith('"'):
                        docstring_text = docstring_text[1:]
                    elif docstring_text.startswith("'"):
                        docstring_text = docstring_text[1:]
                    
                    if docstring_text.endswith('"""'):
                        docstring_text = docstring_text[:-3]
                    elif docstring_text.endswith("'''"):
                        docstring_text = docstring_text[:-3]
                    elif docstring_text.endswith('"'):
                        docstring_text = docstring_text[:-1]
                    elif docstring_text.endswith("'"):
                        docstring_text = docstring_text[:-1]
                    
                    return docstring_text.strip()
        
        return None

    def _is_inside_class(self, ctx: ParseContext) -> bool:
        """Check if current scope is a class."""
        # This is a simplification - in practice we'd track scope types
        return ctx.current_scope is not None

    def _get_node_text(self, node: Node, source_bytes: bytes) -> str:
        """Extract text content from a tree-sitter node."""
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
