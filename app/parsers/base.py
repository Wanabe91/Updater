from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Dependency:
    name: str
    version: str
    version_specifier: str = ""
    is_dev: bool = False
    source: str = ""


@dataclass
class ParseResult:
    file_path: Path
    parser_name: str
    dependencies: list[Dependency] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class BaseParser(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def file_patterns(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        raise NotImplementedError

    @abstractmethod
    def write(self, file_path: Path, result: ParseResult) -> None:
        raise NotImplementedError

    def can_parse(self, file_path: Path) -> bool:
        return any(file_path.name == pattern for pattern in self.file_patterns)