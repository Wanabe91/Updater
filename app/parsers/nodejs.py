from __future__ import annotations

import json
import re
from pathlib import Path

from app.parsers.base import BaseParser, Dependency, ParseResult

_NPM_OP_RE = re.compile(r"^(\^|~|>=|<=|>|<|=|v)?\s*(.+)$")
_NPM_SKIP_PREFIXES = (
    "git+",
    "git:",
    "git://",
    "http://",
    "https://",
    "file:",
    "link:",
    "workspace:",
    "workspace~",
    "github:",
    "npm:",
    "couchbase:",
)
_PNPM_PKG_RE = re.compile(r"^/(.+?)[@/]([^@/:()]+):\s*$")
_GRADLE_COORD_RE = re.compile(r"""["']([^"']+:[^"']+:[^"']+)["']""")
_GRADLE_MAP_RE = re.compile(
    r"""group\s*[:=]\s*["']([^"']+)["']\s*,?\s*"""
    r"""name\s*[:=]\s*["']([^"']+)["']\s*,?\s*"""
    r"""version\s*[:=]\s*["']([^"']+)["']"""
)
_GRADLE_TEST_CONF_RE = re.compile(
    r"\btest(Implementation|CompileOnly|Compile|Api|RuntimeOnly|Runtime)\b"
)


def _parse_npm_spec(spec: str) -> tuple[str, str]:
    spec = spec.strip()
    if not spec:
        return "", ""
    if spec == "*":
        return "*", ""
    if spec == "latest":
        return "latest", ""
    if spec.lower().startswith(_NPM_SKIP_PREFIXES):
        return "", ""

    if "||" in spec:
        spec = spec.split("||")[0].strip()

    parts = spec.split()
    if len(parts) > 1:
        spec = parts[0]

    m = _NPM_OP_RE.match(spec)
    if m:
        op = m.group(1) or ""
        ver = m.group(2).strip()
        if op in ("v", "="):
            op = ""
        return ver, op

    return spec, ""


def _make_npm_dep(
    name: str, spec: str, source: str, is_dev: bool
) -> Dependency | None:
    version, version_specifier = _parse_npm_spec(spec)
    if not version:
        return None
    return Dependency(
        name=name,
        version=version,
        version_specifier=version_specifier,
        is_dev=is_dev,
        source=source,
    )


def _parse_package_json(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    data = json.loads(content)

    for name, spec in data.get("dependencies", {}).items():
        dep = _make_npm_dep(name, spec, source, is_dev=False)
        if dep:
            deps.append(dep)

    for name, spec in data.get("devDependencies", {}).items():
        dep = _make_npm_dep(name, spec, source, is_dev=True)
        if dep:
            deps.append(dep)

    for name, spec in data.get("peerDependencies", {}).items():
        dep = _make_npm_dep(name, spec, source, is_dev=False)
        if dep:
            deps.append(dep)

    for name, spec in data.get("optionalDependencies", {}).items():
        dep = _make_npm_dep(name, spec, source, is_dev=False)
        if dep:
            deps.append(dep)

    return deps


def _parse_package_lock(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    data = json.loads(content)

    packages = data.get("packages", {})
    for pkg_path, pkg_info in packages.items():
        if not pkg_path or not pkg_path.startswith("node_modules/"):
            continue
        if pkg_info.get("link") or pkg_info.get("extraneous"):
            continue
        version = pkg_info.get("version", "")
        if not version:
            continue
        name = pkg_path[len("node_modules/"):]
        deps.append(
            Dependency(
                name=name,
                version=version,
                version_specifier="=",
                is_dev=bool(pkg_info.get("dev")),
                source=source,
            )
        )

    if not deps:
        for name, info in data.get("dependencies", {}).items():
            version = info.get("version", "")
            if not version:
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


def _parse_yarn_lock(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    current_name: str | None = None
    current_version: str | None = None

    def _flush() -> None:
        nonlocal current_name, current_version
        if current_name and current_version:
            deps.append(
                Dependency(
                    name=current_name,
                    version=current_version,
                    version_specifier="=",
                    source=source,
                )
            )
        current_name = None
        current_version = None

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            _flush()
            continue

        if not line.startswith(" ") and ":" in line:
            _flush()
            header = stripped.rstrip(":").strip()
            first_spec = header.split(",")[0].strip()
            at_idx = first_spec.rfind("@")
            if at_idx > 0:
                current_name = first_spec[:at_idx]
            else:
                current_name = first_spec
            current_version = None
        elif current_name and stripped.startswith("version "):
            if '"' in stripped:
                current_version = stripped.split('"')[1]
            else:
                parts = stripped.split(None, 1)
                if len(parts) > 1:
                    current_version = parts[1]

    _flush()
    return deps


def _parse_pnpm_lock(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    in_packages = False

    for line in content.splitlines():
        if line.strip().startswith("packages:"):
            in_packages = True
            continue

        if not in_packages:
            continue

        stripped = line.strip()
        if stripped and not stripped.startswith("/") and not line.startswith(" "):
            in_packages = False
            continue

        m = _PNPM_PKG_RE.match(stripped)
        if m:
            name = m.group(1)
            version = m.group(2)
            deps.append(
                Dependency(
                    name=name,
                    version=version,
                    version_specifier="=",
                    source=source,
                )
            )

    return deps


class NodeJsParser(BaseParser):
    @property
    def name(self) -> str:
        return "nodejs"

    @property
    def file_patterns(self) -> list[str]:
        return ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"]

    def parse(self, file_path: Path) -> ParseResult:
        errors: list[str] = []
        dependencies: list[Dependency] = []

        try:
            content = file_path.read_text(encoding="utf-8-sig")
            if file_path.name == "package.json":
                dependencies = _parse_package_json(content, str(file_path))
            elif file_path.name == "package-lock.json":
                dependencies = _parse_package_lock(content, str(file_path))
            elif file_path.name == "yarn.lock":
                dependencies = _parse_yarn_lock(content, str(file_path))
            elif file_path.name == "pnpm-lock.yaml":
                dependencies = _parse_pnpm_lock(content, str(file_path))
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
