from __future__ import annotations

import re
from pathlib import Path

from app.parsers.base import BaseParser, Dependency, ParseResult

_GOMOD_REQUIRE_RE = re.compile(
    r"^\s*(\S+)\s+(v\S+)\s*(?://\s*(indirect))?"
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

        if stripped == "require (" or stripped.startswith("require ("):
            in_require = True
            continue

        if in_require:
            m = _GOMOD_REQUIRE_RE.match(stripped)
            if m:
                is_indirect = m.group(3) == "indirect"
                deps.append(
                    Dependency(
                        name=m.group(1),
                        version=m.group(2),
                        version_specifier="",
                        is_dev=is_indirect,
                        source=source,
                    )
                )
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

        m = re.match(r"require\s+(\S+)\s+(v\S+)", stripped)
        if m:
            deps.append(
                Dependency(
                    name=m.group(1),
                    version=m.group(2),
                    version_specifier="",
                    is_dev=False,
                    source=source,
                )
            )

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

    def write(self, file_path: Path, result: ParseResult) -> None:
        raise NotImplementedError
