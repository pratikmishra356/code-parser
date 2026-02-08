#!/usr/bin/env python3
"""Debug script to see actual tree-sitter-kotlin AST node types."""

import sys
import tree_sitter_kotlin as ts_kotlin
from tree_sitter import Language, Parser

def print_tree(node, source: bytes, indent: int = 0, max_depth: int = 4):
    """Print AST tree structure."""
    if indent > max_depth:
        return
    
    text = source[node.start_byte:node.end_byte].decode()[:60].replace('\n', '\\n')
    print(f"{'  ' * indent}{node.type}: {text!r}")
    
    for child in node.children:
        print_tree(child, source, indent + 1, max_depth)

def main():
    # Sample Kotlin code
    sample_code = '''
package com.example

import kotlinx.coroutines.flow.Flow

interface MyInterface {
    fun doSomething(): String
}

data class User(val name: String, val age: Int)

class MyService(private val repository: Repository) : MyInterface {
    
    override fun doSomething(): String {
        return helper()
    }
    
    private fun helper(): String {
        val result = repository.fetch()
        return result.toString()
    }
    
    companion object {
        const val TAG = "MyService"
    }
}

fun topLevelFunction(x: Int): Int {
    return x * 2
}

object Singleton {
    fun getInstance(): Singleton = this
}
'''
    
    language = Language(ts_kotlin.language())
    parser = Parser(language)
    
    source_bytes = sample_code.encode('utf-8')
    tree = parser.parse(source_bytes)
    
    print("=" * 80)
    print("Tree-sitter-kotlin AST structure:")
    print("=" * 80)
    print_tree(tree.root_node, source_bytes, max_depth=5)
    
    print("\n" + "=" * 80)
    print("Key node types found:")
    print("=" * 80)
    
    def collect_types(node, types=None):
        if types is None:
            types = set()
        types.add(node.type)
        for child in node.children:
            collect_types(child, types)
        return types
    
    all_types = sorted(collect_types(tree.root_node))
    for t in all_types:
        print(f"  - {t}")

if __name__ == "__main__":
    main()

