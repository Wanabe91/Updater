from __future__ import annotations

from pathlib import Path

from app.parsers.base import BaseParser, ParseResult


class PythonParser(BaseParser):

    @property
    def name(self) -> str:
        return "python"

    @property
    def file_patterns(self) -> list[str]:
        return ["requirements.txt", "Pipfile", "pyproject.toml", "setup.cfg"]

    def parse(self, file_path: Path) -> ParseResult:
        raise NotImplementedError

    def write(self, file_path: Path, result: ParseResult) -> None:
        raise NotImplementedError