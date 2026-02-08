#!/usr/bin/env python3
"""Test if decorators are being extracted by the Python parser."""

from code_parser.parsers.python_parser import PythonParser

test_code = """
from flask import Blueprint
bp = Blueprint('auth', __name__)

@bp.route("/login", methods=["POST"])
@global_exception_handler
def login():
    return "Hello"
"""

parser = PythonParser()
parsed = parser.parse_file(test_code.encode())

print(f"Found {len(parsed.symbols)} symbols:")
for symbol in parsed.symbols:
    print(f"\n  Name: {symbol.name}")
    print(f"  Kind: {symbol.kind}")
    print(f"  Metadata: {symbol.metadata}")
    print(f"  Signature: {symbol.signature}")

