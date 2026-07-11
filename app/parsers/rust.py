from __future__ import annotations

import re
import tomllib
from pathlib import Path

import tomlkit

from app.parsers.base import BaseParser, Dependency, ParseResult

_CARGO_OP_RE = re.compile(r"^([~^>=<!]+|=)?\s*(.+)$")
_CARGO_SECTIONS = (
    ("dependencies", False),
    ("dev-dependencies", True),
    ("build-dependencies", False),
)


def _split_cargo_spec(spec: str) -> tuple[str, str]:
    spec = spec.split(",")[0].strip()
    if not spec or spec == "*":
        return spec, ""
    m = _CARGO_OP_RE.match(spec)
    if m:
        return m.group(2).strip(), m.group(1) or ""
    return spec, ""


def _cargo_spec_version(spec: object) -> str | None:
    if isinstance(spec, str):
        return spec
    if isinstance(spec, dict):
        version = spec.get("version")
        if isinstance(version, str):
            return version
    return None


def _parse_cargo_toml(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    data = tomllib.loads(content)

    for section, is_dev in _CARGO_SECTIONS:
        for name, spec in data.get(section, {}).items():
            raw = _cargo_spec_version(spec)
            if not raw:
                continue  # path/git/workspace dependencies
            version, specifier = _split_cargo_spec(raw)
            deps.append(
                Dependency(
                    name=name,
                    version=version,
                    version_specifier=specifier,
                    is_dev=is_dev,
                    source=source,
                )
            )
    return deps


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


def _update_cargo_toml(content: str, changes: dict[str, str]) -> tuple[str, list[str]]:
    doc = tomlkit.parse(content)
    changed: list[str] = []

    for section, _is_dev in _CARGO_SECTIONS:
        table = doc.get(section)
        if table is None:
            continue
        for name in table:
            if name not in changes:
                continue
            spec = table[name]
            if isinstance(spec, str):
                _version, op = _split_cargo_spec(spec)
                table[name] = f"{op}{changes[name]}"
                changed.append(name)
            elif isinstance(spec, dict):
                version = spec.get("version")
                if isinstance(version, str):
                    _version, op = _split_cargo_spec(version)
                    spec["version"] = f"{op}{changes[name]}"
                    changed.append(name)

    return tomlkit.dumps(doc), changed


class RustParser(BaseParser):
    @property
    def name(self) -> str:
        return "rust"

    @property
    def file_patterns(self) -> list[str]:
        return ["Cargo.toml", "Cargo.lock"]

    def parse(self, file_path: Path) -> ParseResult:
        errors: list[str] = []
        dependencies: list[Dependency] = []

        try:
            content = file_path.read_text(encoding="utf-8-sig")
            if file_path.name == "Cargo.toml":
                dependencies = _parse_cargo_toml(content, str(file_path))
            elif file_path.name == "Cargo.lock":
                dependencies = _parse_cargo_lock(content, str(file_path))
        except Exception as exc:
            errors.append(f"Failed to parse {file_path.name}: {exc}")

        return ParseResult(
            file_path=file_path,
            parser_name=self.name,
            dependencies=dependencies,
            errors=errors,
        )

    def supports_update(self, file_path: Path) -> bool:
        return file_path.name == "Cargo.toml"

    def update_versions(
        self, file_path: Path, content: str, changes: dict[str, str]
    ) -> tuple[str, list[str]]:
        if file_path.name == "Cargo.toml":
            return _update_cargo_toml(content, changes)
        raise NotImplementedError(
            f"Updating {file_path.name} is not supported yet"
        )
