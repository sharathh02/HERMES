"""
HERMES AST Parser Module
Extracts syntactic and structural metadata from Python source code:
- Module docstrings, imports, dependencies
- Classes, inheritance, class attributes
- Methods and functions with signatures, type annotations, and docstrings
- Documentation debt and coverage metrics
- Line number mappings for source grounding
"""

import ast
from typing import Dict, Any, List, Optional


class CodeVisitor(ast.NodeVisitor):
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.lines = source_code.splitlines()
        self.module_docstring: Optional[str] = None
        self.imports: List[Dict[str, Any]] = []
        self.classes: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.documentation_debt: List[Dict[str, Any]] = []
        self.total_definitions = 0
        self.documented_definitions = 0

    def visit_Module(self, node: ast.Module):
        self.module_docstring = ast.get_docstring(node)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append({
                "module": alias.name,
                "asname": alias.asname,
                "line": node.lineno
            })

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        for alias in node.names:
            self.imports.append({
                "module": mod,
                "name": alias.name,
                "asname": alias.asname,
                "line": node.lineno
            })

    def _parse_arguments(self, args: ast.arguments) -> List[Dict[str, Any]]:
        parsed_args = []
        # Calculate defaults offset
        defaults = [None] * (len(args.args) - len(args.defaults)) + args.defaults

        for arg, default in zip(args.args, defaults):
            default_val = None
            if default is not None:
                try:
                    default_val = ast.unparse(default)
                except Exception:
                    default_val = "..."

            type_hint = None
            if arg.annotation:
                try:
                    type_hint = ast.unparse(arg.annotation)
                except Exception:
                    type_hint = "Any"

            parsed_args.append({
                "name": arg.arg,
                "type": type_hint,
                "default": default_val
            })
        return parsed_args

    def _get_return_annotation(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[str]:
        if node.returns:
            try:
                return ast.unparse(node.returns)
            except Exception:
                return "Any"
        return None

    def visit_ClassDef(self, node: ast.ClassDef):
        self.total_definitions += 1
        docstring = ast.get_docstring(node)
        if docstring:
            self.documented_definitions += 1
        else:
            self.documentation_debt.append({
                "type": "class",
                "name": node.name,
                "line": node.lineno,
                "message": f"Class '{node.name}' has no docstring definition."
            })

        bases = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                bases.append("object")

        class_methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.total_definitions += 1
                method_doc = ast.get_docstring(item)
                if method_doc:
                    self.documented_definitions += 1
                else:
                    self.documentation_debt.append({
                        "type": "method",
                        "name": f"{node.name}.{item.name}",
                        "line": item.lineno,
                        "message": f"Method '{item.name}' in class '{node.name}' is missing docstrings."
                    })

                class_methods.append({
                    "name": item.name,
                    "is_async": isinstance(item, ast.AsyncFunctionDef),
                    "docstring": method_doc,
                    "parameters": self._parse_arguments(item.args),
                    "return_type": self._get_return_annotation(item),
                    "line_start": item.lineno,
                    "line_end": getattr(item, 'end_lineno', item.lineno)
                })

        self.classes.append({
            "name": node.name,
            "bases": bases,
            "docstring": docstring,
            "line_start": node.lineno,
            "line_end": getattr(node, 'end_lineno', node.lineno),
            "methods": class_methods
        })

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Top-level functions only (methods handled in visit_ClassDef)
        if not isinstance(getattr(node, 'parent', None), ast.ClassDef):
            self._handle_top_level_func(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if not isinstance(getattr(node, 'parent', None), ast.ClassDef):
            self._handle_top_level_func(node, is_async=True)

    def _handle_top_level_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool):
        self.total_definitions += 1
        docstring = ast.get_docstring(node)
        if docstring:
            self.documented_definitions += 1
        else:
            self.documentation_debt.append({
                "type": "function",
                "name": node.name,
                "line": node.lineno,
                "message": f"Top-level function '{node.name}' is missing documentation."
            })

        self.functions.append({
            "name": node.name,
            "is_async": is_async,
            "docstring": docstring,
            "parameters": self._parse_arguments(node.args),
            "return_type": self._get_return_annotation(node),
            "line_start": node.lineno,
            "line_end": getattr(node, 'end_lineno', node.lineno)
        })


def analyze_python_source(code_str: str, file_name: str = "source.py") -> Dict[str, Any]:
    """
    Parse Python code string and extract rich structural summary.
    Returns structured dictionary with classes, functions, imports, documentation debt,
    and coverage percentage.
    """
    try:
        tree = ast.parse(code_str, filename=file_name)
    except SyntaxError as e:
        return {
            "error": f"SyntaxError at line {e.lineno}: {e.msg}",
            "is_valid": False,
            "file_name": file_name
        }

    # Add parent pointers to differentiate methods from standalone functions
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent

    visitor = CodeVisitor(code_str)
    visitor.visit(tree)

    coverage_pct = 0.0
    if visitor.total_definitions > 0:
        coverage_pct = round((visitor.documented_definitions / visitor.total_definitions) * 100, 1)

    return {
        "is_valid": True,
        "file_name": file_name,
        "total_lines": len(code_str.splitlines()),
        "module_docstring": visitor.module_docstring,
        "imports": visitor.imports,
        "classes": visitor.classes,
        "functions": visitor.functions,
        "documentation_debt": visitor.documentation_debt,
        "metrics": {
            "total_symbols": visitor.total_definitions,
            "documented_symbols": visitor.documented_definitions,
            "undocumented_symbols": len(visitor.documentation_debt),
            "doc_coverage_percent": coverage_pct
        }
    }
