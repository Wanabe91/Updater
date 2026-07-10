from __future__ import annotations

import tomllib
from pathlib import Path

from app.parsers.base import BaseParser, Dependency, ParseResult


def _parse_cargo_lock(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    data = tomllib.loads(content)

    for package in data.get("package", []):
        name = package.get("name", "")
        version = package.get("version", "")
        if not name or not version:
            continue
        deps.append(
            Dependency(
                name=name,
                version=version,
                version_specifier="=",
                source=source,
            )
        )

    return deps


class RustParser(BaseParser):
    @property
    def name(self) -> str:
        return "rust"

    @property
    def file_patterns(self) -> list[str]:
        return ["Cargo.lock"]

    def parse(self, file_path: Path) -> ParseResult:
        errors: list[str] = []
        dependencies: list[Dependency] = []

        try:
            content = file_path.read_text(encoding="utf-8-sig")
            dependencies = _parse_cargo_lock(content, str(file_path))
        except Exception as exc:
            errors.append(f"Failed to parse {file_path.name}: {exc}")

        return ParseResult(
            file_path=file_path,
            parser_name=self.name,
            dependencies=dependencies,
            errors=errors,
        )

    def write(self, file_path: Path, result: ParseResult) -> None:
        raise NotImplementedError
