from __future__ import annotations

from pathlib import Path

from app.parsers.base import BaseParser, ParseResult


class NodeJsParser(BaseParser):

    @property
    def name(self) -> str:
        return "nodejs"

    @property
    def file_patterns(self) -> list[str]:
        return ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"]

    def parse(self, file_path: Path) -> ParseResult:
        raise NotImplementedError

    def write(self, file_path: Path, result: ParseResult) -> None:
        raise NotImplementedError