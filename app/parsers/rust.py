from __future__ import annotations

from pathlib import Path

from app.parsers.base import BaseParser, ParseResult


class RustParser(BaseParser):

    @property
    def name(self) -> str:
        return "rust"

    @property
    def file_patterns(self) -> list[str]:
        return ["Cargo.toml", "Cargo.lock"]

    def parse(self, file_path: Path) -> ParseResult:
        raise NotImplementedError

    def write(self, file_path: Path, result: ParseResult) -> None:
        raise NotImplementedError