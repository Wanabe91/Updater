from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from app.parsers import get_all_parsers
from app.parsers.base import BaseParser

_SKIP_DIRS: frozenset[str] = frozenset({
    ".venv",
    "venv",
    "node_modules",
    ".git",
    "__pycache__",
    ".updater",
    ".idea",
    "dist",
    "build",
    ".eggs",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "htmlcov",
    "target",
    ".tox",
})


@dataclass
class ScanResult:
    project_path: Path
    parsers_used: list[str] = field(default_factory=list)
    dependencies: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Scanner:
    def __init__(self, project_path: Path, max_depth: int = 10) -> None:
        self.project_path = project_path.resolve()
        self._max_depth = max_depth
        self._parsers: list[BaseParser] = []

    def register_parser(self, parser: BaseParser) -> None:
        self._parsers.append(parser)

    def _detect_parsers(self) -> list[BaseParser]:
        return get_all_parsers()

    def _iter_files(self) -> Iterator[Path]:
        base_depth = len(self.project_path.parts)
        for root, dirs, _files in os.walk(self.project_path):
            root_path = Path(root)
            current_depth = len(root_path.parts) - base_depth
            if current_depth >= self._max_depth:
                dirs.clear()
            dirs[:] = [
                d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")
            ]
            for filename in _files:
                yield root_path / filename

    def scan(self) -> ScanResult:
        if not self._parsers:
            for parser in self._detect_parsers():
                self.register_parser(parser)

        result = ScanResult(project_path=self.project_path)
        parsers_used: set[str] = set()

        for file_path in self._iter_files():
            for parser in self._parsers:
                if not parser.can_parse(file_path):
                    continue
                try:
                    parse_result = parser.parse(file_path)
                    parsers_used.add(parser.name)
                    for dep in parse_result.dependencies:
                        result.dependencies.append(
                            {
                                "name": dep.name,
                                "version": dep.version,
                                "version_specifier": dep.version_specifier,
                                "is_dev": dep.is_dev,
                                "source": dep.source,
                                "ecosystem": parser.name,
                            }
                        )
                    result.errors.extend(parse_result.errors)
                except Exception as exc:
                    result.errors.append(f"Error parsing {file_path}: {exc}")
                break

        result.parsers_used = sorted(parsers_used)
        return result
