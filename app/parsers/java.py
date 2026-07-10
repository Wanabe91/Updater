from __future__ import annotations

from pathlib import Path

from app.parsers.base import BaseParser, ParseResult


class JavaParser(BaseParser):

    @property
    def name(self) -> str:
        return "java"

    @property
    def file_patterns(self) -> list[str]:
        return ["pom.xml", "build.gradle", "build.gradle.kts"]

    def parse(self, file_path: Path) -> ParseResult:
        raise NotImplementedError

    def write(self, file_path: Path, result: ParseResult) -> None:
        raise NotImplementedError