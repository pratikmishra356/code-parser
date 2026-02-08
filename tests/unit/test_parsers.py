"""Tests for language parsers."""

import pytest

from code_parser.core import Language, ReferenceType, SymbolKind
from code_parser.parsers.python_parser import PythonParser
from code_parser.parsers.java_parser import JavaParser
from code_parser.parsers.javascript_parser import JavaScriptParser
from code_parser.parsers.rust_parser import RustParser


class TestPythonParser:
    """Tests for Python parser."""

    @pytest.fixture
    def parser(self) -> PythonParser:
        return PythonParser()

    def test_language(self, parser: PythonParser):
        assert parser.language == Language.PYTHON

    def test_file_extensions(self, parser: PythonParser):
        assert ".py" in parser.file_extensions

    def test_parse_function(self, parser: PythonParser):
        code = "def hello(name: str) -> str:\n    return f'Hello, {name}!'"
        result = parser.parse(code, "test.py", "abc123")

        assert result.language == Language.PYTHON
        assert len(result.symbols) == 1
        assert result.symbols[0].name == "hello"
        assert result.symbols[0].kind == SymbolKind.FUNCTION

    def test_parse_class(self, parser: PythonParser):
        code = """
class MyClass:
    def __init__(self):
        pass
    
    def method(self):
        pass
"""
        result = parser.parse(code, "test.py", "abc123")

        # Should have class + 2 methods
        class_symbols = [s for s in result.symbols if s.kind == SymbolKind.CLASS]
        method_symbols = [s for s in result.symbols if s.kind == SymbolKind.METHOD]

        assert len(class_symbols) == 1
        assert class_symbols[0].name == "MyClass"
        assert len(method_symbols) == 2

    def test_parse_imports(self, parser: PythonParser):
        code = "import os\nfrom pathlib import Path"
        result = parser.parse(code, "test.py", "abc123")

        import_symbols = [s for s in result.symbols if s.kind == SymbolKind.IMPORT]
        assert len(import_symbols) >= 2

    def test_parse_call_references(self, parser: PythonParser):
        code = """
def caller():
    result = callee()
    return result

def callee():
    return 42
"""
        result = parser.parse(code, "test.py", "abc123")

        call_refs = [r for r in result.references if r.reference_type == ReferenceType.CALL]
        assert len(call_refs) >= 1
        assert any(r.target_qualified_name == "callee" for r in call_refs)

    def test_parse_inheritance(self, parser: PythonParser, sample_python_code: str):
        result = parser.parse(sample_python_code, "sample.py", "abc123")

        inheritance_refs = [
            r for r in result.references if r.reference_type == ReferenceType.INHERITANCE
        ]
        # DataProcessor inherits from BaseProcessor
        assert len(inheritance_refs) >= 1


class TestJavaParser:
    """Tests for Java parser."""

    @pytest.fixture
    def parser(self) -> JavaParser:
        return JavaParser()

    def test_language(self, parser: JavaParser):
        assert parser.language == Language.JAVA

    def test_file_extensions(self, parser: JavaParser):
        assert ".java" in parser.file_extensions

    def test_parse_class(self, parser: JavaParser, sample_java_code: str):
        result = parser.parse(sample_java_code, "DataService.java", "abc123")

        class_symbols = [s for s in result.symbols if s.kind == SymbolKind.CLASS]
        assert len(class_symbols) == 1
        assert class_symbols[0].name == "DataService"

    def test_parse_methods(self, parser: JavaParser, sample_java_code: str):
        result = parser.parse(sample_java_code, "DataService.java", "abc123")

        method_symbols = [s for s in result.symbols if s.kind == SymbolKind.METHOD]
        # Constructor + fetchAll + process
        assert len(method_symbols) >= 2


class TestJavaScriptParser:
    """Tests for JavaScript parser."""

    @pytest.fixture
    def parser(self) -> JavaScriptParser:
        return JavaScriptParser()

    def test_language(self, parser: JavaScriptParser):
        assert parser.language == Language.JAVASCRIPT

    def test_file_extensions(self, parser: JavaScriptParser):
        assert ".js" in parser.file_extensions
        assert ".mjs" in parser.file_extensions

    def test_parse_class(self, parser: JavaScriptParser, sample_javascript_code: str):
        result = parser.parse(sample_javascript_code, "manager.js", "abc123")

        class_symbols = [s for s in result.symbols if s.kind == SymbolKind.CLASS]
        assert len(class_symbols) == 1
        assert class_symbols[0].name == "DataManager"

    def test_parse_arrow_function(self, parser: JavaScriptParser, sample_javascript_code: str):
        result = parser.parse(sample_javascript_code, "manager.js", "abc123")

        func_symbols = [s for s in result.symbols if s.kind == SymbolKind.FUNCTION]
        assert any(s.name == "formatResult" for s in func_symbols)


class TestRustParser:
    """Tests for Rust parser."""

    @pytest.fixture
    def parser(self) -> RustParser:
        return RustParser()

    def test_language(self, parser: RustParser):
        assert parser.language == Language.RUST

    def test_file_extensions(self, parser: RustParser):
        assert ".rs" in parser.file_extensions

    def test_parse_struct(self, parser: RustParser, sample_rust_code: str):
        result = parser.parse(sample_rust_code, "config.rs", "abc123")

        struct_symbols = [s for s in result.symbols if s.kind == SymbolKind.STRUCT]
        assert len(struct_symbols) == 1
        assert struct_symbols[0].name == "Config"

    def test_parse_impl(self, parser: RustParser, sample_rust_code: str):
        result = parser.parse(sample_rust_code, "config.rs", "abc123")

        impl_symbols = [s for s in result.symbols if s.kind == SymbolKind.IMPL]
        assert len(impl_symbols) >= 1

    def test_parse_functions(self, parser: RustParser, sample_rust_code: str):
        result = parser.parse(sample_rust_code, "config.rs", "abc123")

        func_symbols = [s for s in result.symbols if s.kind == SymbolKind.FUNCTION]
        func_names = [s.name for s in func_symbols]
        assert "process_config" in func_names or "main" in func_names

