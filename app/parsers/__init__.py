from __future__ import annotations

from app.parsers.base import BaseParser, Dependency, ParseResult
from app.parsers.golang import GolangParser
from app.parsers.java import JavaParser
from app.parsers.nodejs import NodeJsParser
from app.parsers.python import PythonParser
from app.parsers.rust import RustParser


def get_all_parsers() -> list[BaseParser]:
    return [
        PythonParser(),
        NodeJsParser(),
        RustParser(),
        GolangParser(),
        JavaParser(),
    ]


__all__ = [
    "BaseParser",
    "Dependency",
    "ParseResult",
    "get_all_parsers",
    "PythonParser",
    "NodeJsParser",
    "RustParser",
    "GolangParser",
    "JavaParser",
]
