"""Minimal Python syntax inspection used before executing generated tests."""

from __future__ import annotations

import ast
from typing import Any


def inspect_python(source: str) -> dict[str, Any]:
    """Parse Python source and report syntax validity and top-level symbols.

    A syntax error is returned as data so callers can feed it through the same
    model repair path as a pytest failure. Unexpected input types are rejected.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "valid": False,
            "error": f"SyntaxError: {exc.msg} (line {exc.lineno}, column {exc.offset})",
            "functions": [],
            "classes": [],
        }

    return {
        "valid": True,
        "error": "",
        "functions": [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ],
        "classes": [node.name for node in tree.body if isinstance(node, ast.ClassDef)],
    }
