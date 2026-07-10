from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.parsers.base import BaseParser


@dataclass
class ScanResult:
    project_path: Path
    parsers_used: list[str] = field(default_factory=list)
    dependencies: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Scanner:
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self._parsers: list[BaseParser] = []

    def register_parser(self, parser: BaseParser) -> None:
        self._parsers.append(parser)

    def _detect_parsers(self) -> list[BaseParser]:
        raise NotImplementedError

    def scan(self) -> ScanResult:
        raise NotImplementedError