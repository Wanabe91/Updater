from __future__ import annotations

import re
from pathlib import Path

from app.parsers.base import BaseParser, Dependency, ParseResult

_GOMOD_REQUIRE_RE = re.compile(
    r"^\s*(\S+)\s+(v\S+)\s*(?://\s*(indirect))?"
)


def _dep_from_require(m: re.Match[str], source: str) -> Dependency:
    return Dependency(
        name=m.group(1),
        version=m.group(2),
        version_specifier="",
        is_dev=m.group(3) == "indirect",
        source=source,
    )


def _parse_go_mod(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    in_require = False
    in_exclude = False
    in_replace = False
    in_retract = False

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        if stripped.startswith(")") :
            in_require = False
            in_exclude = False
            in_replace = False
            in_retract = False
            continue

        if in_exclude or in_replace or in_retract:
            continue

        if stripped.startswith("require ("):
            in_require = True
            continue

        if in_require:
            m = _GOMOD_REQUIRE_RE.match(stripped)
            if m:
                deps.append(_dep_from_require(m, source))
            continue

        if stripped.startswith("module ") or stripped.startswith("go "):
            continue

        if stripped.startswith("exclude"):
            if "(" in stripped:
                in_exclude = True
            continue

        if stripped.startswith("replace"):
            if "(" in stripped:
                in_replace = True
            continue

        if stripped.startswith("retract"):
            if "(" in stripped:
                in_retract = True
            continue

        if stripped.startswith("require "):
            m = _GOMOD_REQUIRE_RE.match(stripped[len("require "):])
            if m:
                deps.append(_dep_from_require(m, source))

    return deps


def _parse_go_sum(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    seen: set[str] = set()

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        parts = stripped.split()
        if len(parts) < 2:
            continue

        module_path = parts[0]
        version = parts[1]

        if version.endswith("/go.mod"):
            continue

        key = f"{module_path}@{version}"
        if key in seen:
            continue
        seen.add(key)

        deps.append(
            Dependency(
                name=module_path,
                version=version,
                version_specifier="=",
                is_dev=False,
                source=source,
            )
        )

    return deps


def _update_go_mod(content: str, changes: dict[str, str]) -> tuple[str, list[str]]:
    changed: list[str] = []
    out_lines: list[str] = []
    in_require = False
    in_skip = False

    for line in content.splitlines(keepends=True):
        stripped = line.strip()
        new_line = line

        if stripped.startswith(")"):
            in_require = False
            in_skip = False
        elif stripped.startswith("require ("):
            in_require = True
        elif (
            stripped.startswith(("exclude", "replace", "retract"))
            and "(" in stripped
        ):
            in_skip = True
        elif not in_skip and not stripped.startswith("//"):
            candidate = None
            if in_require:
                candidate = stripped
            elif stripped.startswith("require "):
                candidate = stripped[len("require "):]
            if candidate:
                m = _GOMOD_REQUIRE_RE.match(candidate)
                if m and m.group(1) in changes:
                    new_line = line.replace(m.group(2), changes[m.group(1)], 1)
                    changed.append(m.group(1))

        out_lines.append(new_line)
    return "".join(out_lines), changed


class GolangParser(BaseParser):
    @property
    def name(self) -> str:
        return "golang"

    @property
    def file_patterns(self) -> list[str]:
        return ["go.mod", "go.sum"]

    def parse(self, file_path: Path) -> ParseResult:
        errors: list[str] = []
        dependencies: list[Dependency] = []

        try:
            content = file_path.read_text(encoding="utf-8-sig")
            if file_path.name == "go.mod":
                dependencies = _parse_go_mod(content, str(file_path))
            elif file_path.name == "go.sum":
                dependencies = _parse_go_sum(content, str(file_path))
        except Exception as exc:
            errors.append(f"Failed to parse {file_path.name}: {exc}")

        return ParseResult(
            file_path=file_path,
            parser_name=self.name,
            dependencies=dependencies,
            errors=errors,
        )

    def supports_update(self, file_path: Path) -> bool:
        return file_path.name == "go.mod"

    def update_versions(
        self, file_path: Path, content: str, changes: dict[str, str]
    ) -> tuple[str, list[str]]:
        if file_path.name == "go.mod":
            return _update_go_mod(content, changes)
        raise NotImplementedError(
            f"Updating {file_path.name} is not supported yet"
        )
