from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Dependency:
    name: str
    version: str
    version_specifier: str = ""
    is_dev: bool = False
    source: str = ""
    ecosystem: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


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

    def can_parse(self, file_path: Path) -> bool:
        return any(file_path.name == pattern for pattern in self.file_patterns)

    def supports_update(self, file_path: Path) -> bool:
        return False

    def update_versions(
        self, file_path: Path, content: str, changes: dict[str, str]
    ) -> tuple[str, list[str]]:
        """Return updated file content and the names of packages changed."""
        raise NotImplementedError
