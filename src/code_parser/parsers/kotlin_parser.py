"""Kotlin language parser using tree-sitter."""

import tree_sitter_kotlin as ts_kotlin
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


class KotlinParseContext(ParseContext):
    """Extended context for Kotlin parsing with type resolution."""

    def __init__(self, file_path: str, source_bytes: bytes) -> None:
        super().__init__(file_path, source_bytes)
        # Import map: short_name -> full_path
        # e.g., "RiskAssessmentService" -> "com.toasttab.service.ccfraud.service.RiskAssessmentService"
        self.imports: dict[str, str] = {}
        # Field/parameter types: field_name -> type_name
        # e.g., "riskAssessmentService" -> "RiskAssessmentService"
        self.field_types: dict[str, str] = {}
        # Methods in current class (for resolving same-class calls)
        self.class_methods: set[str] = set()
        # Current class qualified name (for resolving sibling methods)
        self.current_class_qualified_name: str | None = None
        # Package declaration (for same-package type resolution)
        # e.g., "com.toasttab.service.ccfraud.service"
        self.package_name: str | None = None

    def clear_class_context(self) -> None:
        """Clear class-specific context when exiting a class."""
        self.field_types.clear()
        self.class_methods.clear()
        self.current_class_qualified_name = None


class KotlinParser(LanguageParser):
    """
    Parser for Kotlin source code.
    
    Extracts classes, objects, functions, and call references
    using tree-sitter-kotlin. Resolves call targets to full
    qualified paths using import and type information.
    """

    def __init__(self) -> None:
        self._language = Language(ts_kotlin.language())
        self._parser = Parser(self._language)

    @property
    def language(self) -> CodeLanguage:
        return CodeLanguage.KOTLIN

    @property
    def file_extensions(self) -> frozenset[str]:
        return frozenset({".kt", ".kts"})

    def parse(self, source_code: str, file_path: str, content_hash: str) -> ParsedFile:
        """Parse Kotlin source code and extract symbols and references."""
        source_bytes = source_code.encode("utf-8")
        tree = self._parser.parse(source_bytes)

        ctx = KotlinParseContext(file_path, source_bytes)
        
        # First pass: collect imports
        self._collect_imports(tree.root_node, ctx)
        
        # Second pass: process everything
        self._process_node(tree.root_node, ctx)

        return ParsedFile(
            relative_path=file_path,
            language=self.language,
            content_hash=content_hash,
            symbols=tuple(ctx.symbols),
            references=tuple(ctx.references),
            errors=tuple(ctx.errors),
        )

    def _collect_imports(self, node: Node, ctx: KotlinParseContext) -> None:
        """First pass: collect package declaration and all imports."""
        # Collect package declaration
        if node.type == "package_header":
            for child in node.children:
                if child.type == "qualified_identifier":
                    ctx.package_name = self._get_node_text(child, ctx.source_bytes)
        
        # Collect imports
        if node.type == "import":
            for child in node.children:
                if child.type == "qualified_identifier":
                    import_path = self._get_node_text(child, ctx.source_bytes)
                    short_name = import_path.split(".")[-1]
                    ctx.imports[short_name] = import_path
        
        for child in node.children:
            self._collect_imports(child, ctx)

    def _process_node(self, node: Node, ctx: KotlinParseContext) -> None:
        """Recursively process AST nodes."""
        node_type = node.type
        
        # Class declaration (includes interface, data class, enum)
        if node_type == "class_declaration":
            self._process_class(node, ctx)
            return
        
        # Object declaration (Kotlin singleton)
        if node_type == "object_declaration":
            self._process_object(node, ctx)
            return
        
        # Companion object
        if node_type == "companion_object":
            self._process_companion_object(node, ctx)
            return
        
        # Function declaration
        if node_type == "function_declaration":
            self._process_function(node, ctx)
            return
        
        # Import (already collected, but still create symbol)
        if node_type == "import":
            self._process_import(node, ctx)
        
        # Call expression
        if node_type == "call_expression":
            self._process_call(node, ctx)
        
        # Recurse into children
        for child in node.children:
            self._process_node(child, ctx)

    def _process_class(self, node: Node, ctx: KotlinParseContext) -> None:
        """Extract class/interface/enum declaration."""
        name = None
        is_interface = False
        modifiers = []
        
        for child in node.children:
            if child.type == "identifier":
                name = self._get_node_text(child, ctx.source_bytes)
            elif child.type == "interface":
                is_interface = True
            elif child.type == "modifiers":
                modifiers = self._get_node_text(child, ctx.source_bytes).split()
        
        if not name:
            return

        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        # Determine kind
        if is_interface:
            kind = SymbolKind.INTERFACE
        elif "enum" in modifiers:
            kind = SymbolKind.ENUM
        else:
            kind = SymbolKind.CLASS

        # Extract inheritance from delegation_specifiers
        for child in node.children:
            if child.type == "delegation_specifiers":
                self._extract_inheritance(child, qualified_name, ctx)

        # Extract signature (everything before the body)
        signature = self._extract_signature_before_body(node, ctx.source_bytes, "class_body")
        
        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        if modifiers:
            metadata["modifiers"] = modifiers
        
        # Extract annotations
        annotations = self._extract_annotations(node, ctx.source_bytes)
        if annotations:
            metadata["annotations"] = annotations
        
        # Extract KDoc
        kdoc = self._extract_kdoc(node, ctx.source_bytes)
        if kdoc:
            metadata["kdoc"] = kdoc

        ctx.add_symbol(
            Symbol(
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
        )

        # Set up class context
        ctx.current_class_qualified_name = qualified_name
        ctx.field_types.clear()
        ctx.class_methods.clear()
        
        # Collect constructor parameters (fields)
        self._collect_constructor_params(node, ctx)
        
        # Collect property declarations
        for child in node.children:
            if child.type == "class_body":
                self._collect_properties(child, ctx)
                self._collect_method_names(child, ctx)

        # Process class body
        ctx.push_scope(qualified_name)
        for child in node.children:
            if child.type == "class_body":
                for body_child in child.children:
                    self._process_node(body_child, ctx)
        ctx.pop_scope()
        
        # Clear class context
        ctx.clear_class_context()

    def _collect_constructor_params(self, class_node: Node, ctx: KotlinParseContext) -> None:
        """Collect constructor parameters and their types."""
        for child in class_node.children:
            if child.type == "primary_constructor":
                for param_container in child.children:
                    if param_container.type == "class_parameters":
                        for param in param_container.children:
                            if param.type == "class_parameter":
                                self._extract_param_type(param, ctx)

    def _extract_param_type(self, param_node: Node, ctx: KotlinParseContext) -> None:
        """Extract parameter name and type."""
        name = None
        type_name = None
        for child in param_node.children:
            if child.type == "identifier":
                name = self._get_node_text(child, ctx.source_bytes)
            elif child.type == "user_type":
                type_name = self._get_node_text(child, ctx.source_bytes)
        
        if name and type_name:
            ctx.field_types[name] = type_name

    def _collect_properties(self, class_body: Node, ctx: KotlinParseContext) -> None:
        """Collect property declarations and their types."""
        for child in class_body.children:
            if child.type == "property_declaration":
                name = None
                type_name = None
                for prop_child in child.children:
                    if prop_child.type == "variable_declaration":
                        for vc in prop_child.children:
                            if vc.type == "identifier":
                                name = self._get_node_text(vc, ctx.source_bytes)
                    elif prop_child.type == "user_type":
                        type_name = self._get_node_text(prop_child, ctx.source_bytes)
                
                if name and type_name:
                    ctx.field_types[name] = type_name

    def _collect_method_names(self, class_body: Node, ctx: KotlinParseContext) -> None:
        """Collect method names in the current class."""
        for child in class_body.children:
            if child.type == "function_declaration":
                for fc in child.children:
                    if fc.type == "identifier":
                        method_name = self._get_node_text(fc, ctx.source_bytes)
                        ctx.class_methods.add(method_name)
                        break

    def _process_object(self, node: Node, ctx: KotlinParseContext) -> None:
        """Extract object declaration (Kotlin singleton)."""
        name = None
        for child in node.children:
            if child.type == "identifier":
                name = self._get_node_text(child, ctx.source_bytes)
                break
        
        if not name:
            return

        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {"is_object": True}
        annotations = self._extract_annotations(node, ctx.source_bytes)
        if annotations:
            metadata["annotations"] = annotations
        kdoc = self._extract_kdoc(node, ctx.source_bytes)
        if kdoc:
            metadata["kdoc"] = kdoc

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.CLASS,
                source_code=source_code,
                parent_qualified_name=ctx.current_scope,
                metadata=metadata,
                start_line=start_line,
                end_line=end_line,
                start_column=start_column,
                end_column=end_column,
            )
        )

        # Process object body
        ctx.push_scope(qualified_name)
        for child in node.children:
            if child.type == "class_body":
                for body_child in child.children:
                    self._process_node(body_child, ctx)
        ctx.pop_scope()

    def _process_companion_object(self, node: Node, ctx: KotlinParseContext) -> None:
        """Extract companion object."""
        name = "Companion"
        
        for child in node.children:
            if child.type == "identifier":
                name = self._get_node_text(child, ctx.source_bytes)
                break

        source_code = self._get_node_text(node, ctx.source_bytes)

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {"is_companion": True}
        annotations = self._extract_annotations(node, ctx.source_bytes)
        if annotations:
            metadata["annotations"] = annotations
        kdoc = self._extract_kdoc(node, ctx.source_bytes)
        if kdoc:
            metadata["kdoc"] = kdoc

        ctx.add_symbol(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=SymbolKind.CLASS,
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
        for child in node.children:
            if child.type == "class_body":
                for body_child in child.children:
                    self._process_node(body_child, ctx)
        ctx.pop_scope()

    def _process_function(self, node: Node, ctx: KotlinParseContext) -> None:
        """Extract function declaration."""
        name = None
        modifiers = []
        
        for child in node.children:
            if child.type == "identifier":
                name = self._get_node_text(child, ctx.source_bytes)
            elif child.type == "modifiers":
                modifiers = self._get_node_text(child, ctx.source_bytes).split()
        
        if not name:
            return

        source_code = self._get_node_text(node, ctx.source_bytes)

        is_method = ctx.current_scope is not None
        kind = SymbolKind.METHOD if is_method else SymbolKind.FUNCTION

        if ctx.current_scope:
            qualified_name = f"{ctx.current_scope}.{name}"
        else:
            qualified_name = self._build_qualified_name(ctx.file_path, name)

        signature = self._extract_signature_before_body(node, ctx.source_bytes, "function_body")
        
        # Extract position information
        start_line, end_line, start_column, end_column = self._extract_position(node)
        
        # Extract enhanced metadata
        metadata: dict[str, str | int | bool | list] = {}
        if modifiers:
            metadata["modifiers"] = modifiers
        
        # Extract annotations
        annotations = self._extract_annotations(node, ctx.source_bytes)
        if annotations:
            metadata["annotations"] = annotations
        
        # Extract return type
        return_type = self._extract_return_type(node, ctx.source_bytes)
        if return_type:
            metadata["return_type"] = return_type
        
        # Extract parameters
        parameters = self._extract_parameters(node, ctx.source_bytes)
        if parameters:
            metadata["parameters"] = parameters
        
        # Extract KDoc
        kdoc = self._extract_kdoc(node, ctx.source_bytes)
        if kdoc:
            metadata["kdoc"] = kdoc

        ctx.add_symbol(
            Symbol(
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
        )

        # Add MEMBER reference from parent class/object to this method for traversal
        if is_method and ctx.current_scope:
            parent_path, parent_name = self._split_scope(ctx.current_scope)
            method_path, method_name = self._split_scope(qualified_name)
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
        for child in node.children:
            if child.type == "function_body":
                self._process_node(child, ctx)
        ctx.pop_scope()

    def _process_import(self, node: Node, ctx: KotlinParseContext) -> None:
        """Extract import statement."""
        source_code = self._get_node_text(node, ctx.source_bytes)
        
        import_path = None
        for child in node.children:
            if child.type == "qualified_identifier":
                import_path = self._get_node_text(child, ctx.source_bytes)
                break
        
        if not import_path:
            return

        qualified_name = self._build_qualified_name(ctx.file_path, f"import:{import_path}")
        
        ctx.add_symbol(
            Symbol(
                name=import_path.split(".")[-1],
                qualified_name=qualified_name,
                kind=SymbolKind.IMPORT,
                source_code=source_code,
            )
        )

        # For imports: source is the file, target is the imported symbol
        source_file_path = self._file_path_to_dot_notation(ctx.file_path)
        target_class_path = ".".join(import_path.split(".")[:-1]) if "." in import_path else import_path
        target_name = import_path.split(".")[-1]
        
        ctx.add_reference(
            Reference(
                source_file_path=source_file_path,
                source_symbol_name="<file>",  # File-level import
                target_file_path=target_class_path,
                target_symbol_name=target_name,
                reference_type=ReferenceType.IMPORT,
            )
        )

    def _process_call(self, node: Node, ctx: KotlinParseContext) -> None:
        """Extract function call as reference with resolved path and symbol name."""
        if not ctx.current_scope:
            return

        # Get the called expression
        call_target = None
        for child in node.children:
            if child.type == "identifier":
                call_target = self._get_node_text(child, ctx.source_bytes)
                break
            elif child.type == "navigation_expression":
                call_target = self._get_node_text(child, ctx.source_bytes)
                break

        if not call_target:
            return

        # Resolve the call target to path and symbol name
        target_path, target_symbol_name = self._resolve_call_target(call_target, ctx)

        # Extract source path and name from current scope
        source_path, source_name = self._split_scope(ctx.current_scope)

        ctx.add_reference(
            Reference(
                source_file_path=source_path,
                source_symbol_name=source_name,
                target_file_path=target_path,
                target_symbol_name=target_symbol_name,
                reference_type=ReferenceType.CALL,
            )
        )
        
        # NEW: Extract identifiers from method arguments (for DSL patterns)
        # Example: .process(unlinkedRefundFraudProcessor) -> creates reference to processor class
        self._process_call_arguments(node, ctx)

    def _process_call_arguments(self, node: Node, ctx: KotlinParseContext) -> None:
        """
        Extract identifiers from call arguments and create references to them.
        
        For DSL patterns like:
          .process(unlinkedRefundFraudProcessor)  -> creates ref to processor class
          .filter(myPredicate)                    -> creates ref to predicate class
        
        This allows tracing business logic in declarative frameworks (Camel, Spring DSL, etc.).
        """
        if not ctx.current_scope:
            return
            
        # Find value_arguments node
        for child in node.children:
            if child.type == "value_arguments":
                self._extract_argument_identifiers(child, ctx)
    
    def _extract_argument_identifiers(self, node: Node, ctx: KotlinParseContext) -> None:
        """Recursively extract identifier nodes from arguments and create references."""
        # Check for both simple_identifier and identifier (tree-sitter uses "identifier" for simple args)
        if node.type in ("simple_identifier", "identifier"):
            identifier_name = self._get_node_text(node, ctx.source_bytes)
            
            # Skip keywords, literals, and common primitives
            skip_keywords = {"true", "false", "null", "this", "it", "super"}
            if identifier_name in skip_keywords:
                return
            
            # Check if it's a field/parameter with a known type
            if identifier_name in ctx.field_types:
                type_name = ctx.field_types[identifier_name]
                target_path = self._resolve_type_to_path(type_name, ctx)
                
                source_path, source_name = self._split_scope(ctx.current_scope)
                ctx.add_reference(
                    Reference(
                        source_file_path=source_path,
                        source_symbol_name=source_name,
                        target_file_path=target_path,
                        target_symbol_name=type_name,
                        reference_type=ReferenceType.CALL,  # Arguments are implicitly called/used
                    )
                )
        
        # Recurse into children to handle nested expressions
        for child in node.children:
            self._extract_argument_identifiers(child, ctx)
    
    def _resolve_type_to_path(self, type_name: str, ctx: KotlinParseContext) -> str:
        """
        Resolve a type name to its full qualified path using imports and package context.
        
        Args:
            type_name: Simple type name (e.g., "UnlinkedRefundFraudProcessor")
            ctx: Parse context with imports and package info
            
        Returns:
            Fully qualified path (e.g., "com.toasttab...UnlinkedRefundFraudProcessor")
        """
        # Check if it's in imports (most common for injected beans/fields)
        if type_name in ctx.imports:
            return ctx.imports[type_name]
        
        # Check if it's in the same package (no import needed)
        if ctx.package_name:
            return f"{ctx.package_name}.{type_name}"
        
        # Fall back to just the type name (will still create reference for searching)
        return type_name
    
    def _resolve_call_target(
        self, call_target: str, ctx: KotlinParseContext
    ) -> tuple[str, str]:
        """
        Resolve a call target to (path, symbol_name).
        
        Returns:
            tuple of (target_path, target_symbol_name) for use with get_symbol_details API
        
        Examples:
            - "makeResponse" (same class method) 
              -> ("...RiskAssessmentResource", "makeResponse")
            - "riskAssessmentService.generateAssessment" 
              -> ("com.toasttab...RiskAssessmentService", "generateAssessment")
            - "logger.info" (can't resolve) 
              -> ("logger", "info")
        """
        # Check if it's a navigation expression (object.method)
        if "." in call_target:
            # Split into parts - handle chained calls like Response.ok(data).build
            parts = call_target.split(".")
            first_part = parts[0]
            
            # Remove any method call syntax from first part
            first_part_clean = first_part.split("(")[0]
            
            # Get the method name (last part, without args)
            method_name = parts[-1].split("(")[0]
            
            # Check if first part is a known field/parameter
            if first_part_clean in ctx.field_types:
                type_name = ctx.field_types[first_part_clean]
                # Look up the type in imports first
                if type_name in ctx.imports:
                    full_path = ctx.imports[type_name]
                    return (full_path, method_name)
                # If not in imports, assume same package (no import needed)
                elif ctx.package_name:
                    full_path = f"{ctx.package_name}.{type_name}"
                    return (full_path, method_name)
                # Fall back to just the type name
                return (type_name, method_name)
            
            # Check if first part is directly in imports (static call)
            if first_part_clean in ctx.imports:
                full_path = ctx.imports[first_part_clean]
                return (full_path, method_name)
            
            # Can't resolve - return as-is (first part as path, last as method)
            return (first_part_clean, method_name)
        
        # Simple call (no dot) - check if it's a sibling method
        method_name = call_target.split("(")[0]
        
        if method_name in ctx.class_methods and ctx.current_class_qualified_name:
            # It's a call to a sibling method in the same class
            # Path is the class, symbol is the method
            return (ctx.current_class_qualified_name, method_name)
        
        # Check if it's an imported function (top-level function)
        if method_name in ctx.imports:
            # For imported functions, the import path IS the full path
            # Split to get package path and function name
            import_path = ctx.imports[method_name]
            if "." in import_path:
                # Package path without the function name
                package_path = import_path.rsplit(".", 1)[0]
                return (package_path, method_name)
            return (import_path, method_name)
        
        # Can't resolve - return method name as both path and name
        return (method_name, method_name)

    def _extract_inheritance(self, node: Node, class_qualified_name: str, ctx: KotlinParseContext) -> None:
        """Extract superclass/interface references from delegation specifiers."""
        source_path, source_name = self._split_scope(class_qualified_name)
        
        for child in node.children:
            if child.type == "delegation_specifier":
                type_name = self._find_identifier_recursive(child, ctx.source_bytes)
                if type_name:
                    # Try to resolve the type to its import path
                    if type_name in ctx.imports:
                        target_path = ctx.imports[type_name]
                    else:
                        target_path = type_name
                    
                    # Split target path if it's a full import path
                    if "." in target_path:
                        target_file_path = ".".join(target_path.split(".")[:-1])
                        target_symbol = target_path.split(".")[-1]
                    else:
                        target_file_path = target_path
                        target_symbol = target_path
                    
                    ctx.add_reference(
                        Reference(
                            source_file_path=source_path,
                            source_symbol_name=source_name,
                            target_file_path=target_file_path,
                            target_symbol_name=target_symbol,
                            reference_type=ReferenceType.INHERITANCE,
                        )
                    )

    def _find_identifier_recursive(self, node: Node, source_bytes: bytes) -> str | None:
        """Find first identifier in a node tree."""
        if node.type == "identifier":
            return self._get_node_text(node, source_bytes)
        for child in node.children:
            result = self._find_identifier_recursive(child, source_bytes)
            if result:
                return result
        return None

    def _extract_signature_before_body(self, node: Node, source_bytes: bytes, body_type: str) -> str:
        """Extract signature (everything before the body)."""
        for child in node.children:
            if child.type == body_type:
                return source_bytes[node.start_byte:child.start_byte].decode("utf-8").strip()
        text = self._get_node_text(node, source_bytes)
        if "{" in text:
            return text[:text.index("{")].strip()
        return text.strip()

    def _get_node_text(self, node: Node, source_bytes: bytes) -> str:
        """Extract text from node."""
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    
    def _extract_annotations(self, node: Node, source_bytes: bytes) -> list[str]:
        """Extract annotations from a node."""
        annotations: list[str] = []
        for child in node.children:
            if child.type == "modifiers":
                for modifier_child in child.children:
                    if modifier_child.type == "annotation":
                        ann_text = self._get_node_text(modifier_child, source_bytes)
                        if not ann_text.startswith("@"):
                            ann_text = "@" + ann_text
                        annotations.append(ann_text)
        return annotations
    
    def _extract_return_type(self, node: Node, source_bytes: bytes) -> str | None:
        """Extract return type from a function declaration."""
        for child in node.children:
            if child.type == "type":
                return self._get_node_text(child, source_bytes)
        return None
    
    def _extract_parameters(self, node: Node, source_bytes: bytes) -> list[dict[str, str | None]]:
        """Extract parameter information from a function declaration."""
        parameters: list[dict[str, str | None]] = []
        for child in node.children:
            if child.type == "function_value_parameters":
                for param_child in child.children:
                    if param_child.type == "parameter":
                        name = None
                        type_name = None
                        default = None
                        for pc in param_child.children:
                            if pc.type == "identifier":
                                name = self._get_node_text(pc, source_bytes)
                            elif pc.type == "type":
                                type_name = self._get_node_text(pc, source_bytes)
                            elif pc.type == "default_value":
                                default = self._get_node_text(pc, source_bytes)
                        
                        if name:
                            param_info: dict[str, str | None] = {
                                "name": name,
                                "type": type_name,
                                "default": default,
                            }
                            parameters.append(param_info)
        return parameters
    
    def _extract_kdoc(self, node: Node, source_bytes: bytes) -> str | None:
        """Extract KDoc comment preceding a node."""
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
        
        # Check previous siblings for KDoc
        for i in range(node_index - 1, -1, -1):
            prev_sibling = parent.children[i]
            if prev_sibling.type == "kdoc":
                return self._get_node_text(prev_sibling, source_bytes).strip()
            elif prev_sibling.type == "line_comment":
                comment_text = self._get_node_text(prev_sibling, source_bytes)
                if comment_text.strip().startswith("/**"):
                    # Extract KDoc content
                    lines = comment_text.split("\n")
                    kdoc_lines = []
                    for line in lines:
                        line = line.strip()
                        line = line.removeprefix("/**").removesuffix("*/").strip()
                        line = line.removeprefix("*").strip()
                        if line:
                            kdoc_lines.append(line)
                    if kdoc_lines:
                        return "\n".join(kdoc_lines)
        
        return None

    def _file_path_to_dot_notation(self, file_path: str) -> str:
        """
        Convert file path to dot notation.
        
        Example: "src/main/kotlin/com/toasttab/MyClass.kt" 
                 -> "src.main.kotlin.com.toasttab.MyClass"
        """
        # Remove extension
        path = file_path
        for ext in self.file_extensions:
            if path.endswith(ext):
                path = path[:-len(ext)]
                break
        # Convert slashes to dots
        return path.replace("/", ".").replace("\\", ".")

    def _split_scope(self, qualified_name: str) -> tuple[str, str]:
        """
        Split a qualified name into (path, symbol_name).
        
        Example: "com.toasttab.MyClass.MyClass.myMethod"
                 -> ("com.toasttab.MyClass.MyClass", "myMethod")
        """
        if "." in qualified_name:
            parts = qualified_name.rsplit(".", 1)
            return (parts[0], parts[1])
        return (qualified_name, qualified_name)
