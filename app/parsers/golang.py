from __future__ import annotations

from pathlib import Path

from app.parsers.base import BaseParser, ParseResult


class GolangParser(BaseParser):

    @property
    def name(self) -> str:
        return "golang"

    @property
    def file_patterns(self) -> list[str]:
        return ["go.mod", "go.sum"]

    def parse(self, file_path: Path) -> ParseResult:
        raise NotImplementedError

    def write(self, file_path: Path, result: ParseResult) -> None:
        raise NotImplementedError