from __future__ import annotations

import configparser
import re
import tomllib
from pathlib import Path

import tomlkit

from app.parsers.base import BaseParser, Dependency, ParseResult

_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
_SPEC_RE = re.compile(r"(===|==|!=|~=|>=|<=|>|<)\s*([0-9][0-9a-zA-Z.\-+!]*)")
_TOML_OP_RE = re.compile(r"^([~^>=<!]+)?(.+)$")


def _strip_markers(line: str) -> str:
    idx = line.find(";")
    if idx != -1:
        line = line[:idx]
    return line.strip()


def _strip_inline_comment(line: str) -> str:
    idx = line.find(" #")
    if idx != -1:
        line = line[:idx]
    return line.strip()


def _parse_pep508(line: str, source: str = "") -> Dependency | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    line = _strip_markers(line)
    line = _strip_inline_comment(line)
    if not line:
        return None

    if line.startswith("-"):
        return None
    if "://" in line or line.startswith(("git+", "hg+", "svn+", "bzr+")):
        return None
    if line.startswith((".", "/")):
        return None

    match = _NAME_RE.match(line)
    if not match:
        return None
    name = match.group(1)
    rest = line[match.end() :].strip()

    if rest.startswith("["):
        end = rest.find("]")
        if end != -1:
            rest = rest[end + 1 :].strip()

    if not rest:
        return Dependency(name=name, version="", version_specifier="", source=source)

    specs = _SPEC_RE.findall(rest)
    if not specs:
        return Dependency(name=name, version=rest, version_specifier="", source=source)

    return Dependency(
        name=name,
        version=specs[0][1],
        version_specifier=specs[0][0],
        source=source,
    )


def _parse_requirements(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    for line in content.splitlines():
        dep = _parse_pep508(line, source)
        if dep:
            deps.append(dep)
    return deps


def _split_toml_version(spec: str) -> tuple[str, str]:
    spec = spec.split(",")[0].strip()
    if not spec or spec == "*":
        return spec, ""
    m = _TOML_OP_RE.match(spec)
    if m:
        return m.group(2), m.group(1) or ""
    return spec, ""


def _parse_toml_dep(
    name: str, spec: object, source: str, is_dev: bool
) -> Dependency | None:
    version = ""
    version_specifier = ""

    if isinstance(spec, str):
        version, version_specifier = _split_toml_version(spec)
    elif isinstance(spec, dict):
        ver = spec.get("version", "")
        if isinstance(ver, str):
            version, version_specifier = _split_toml_version(ver)
    else:
        return None

    return Dependency(
        name=name,
        version=version,
        version_specifier=version_specifier,
        is_dev=is_dev,
        source=source,
    )


def _parse_pyproject_toml(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    data = tomllib.loads(content)

    project = data.get("project", {})
    for req_str in project.get("dependencies", []):
        dep = _parse_pep508(req_str, source)
        if dep:
            deps.append(dep)

    for _group, reqs in project.get("optional-dependencies", {}).items():
        for req_str in reqs:
            dep = _parse_pep508(req_str, source)
            if dep:
                dep.is_dev = True
                deps.append(dep)

    tool = data.get("tool", {})
    poetry = tool.get("poetry", {})
    for name, spec in poetry.get("dependencies", {}).items():
        if name == "python":
            continue
        dep = _parse_toml_dep(name, spec, source, is_dev=False)
        if dep:
            deps.append(dep)

    for _group_name, group_data in poetry.get("group", {}).items():
        for name, spec in group_data.get("dependencies", {}).items():
            if name == "python":
                continue
            dep = _parse_toml_dep(name, spec, source, is_dev=True)
            if dep:
                deps.append(dep)

    for name, spec in poetry.get("dev-dependencies", {}).items():
        dep = _parse_toml_dep(name, spec, source, is_dev=True)
        if dep:
            deps.append(dep)

    return deps


def _parse_pipfile(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    data = tomllib.loads(content)

    for name, spec in data.get("packages", {}).items():
        dep = _parse_toml_dep(name, spec, source, is_dev=False)
        if dep:
            deps.append(dep)

    for name, spec in data.get("dev-packages", {}).items():
        dep = _parse_toml_dep(name, spec, source, is_dev=True)
        if dep:
            deps.append(dep)

    return deps


def _parse_setup_cfg(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    parser = configparser.ConfigParser()
    parser.read_string(content)

    if parser.has_section("options"):
        install_requires = parser.get("options", "install_requires", fallback="")
        for line in install_requires.splitlines():
            dep = _parse_pep508(line, source)
            if dep:
                deps.append(dep)

    if parser.has_section("options.extras_require"):
        for _group, reqs in parser.items("options.extras_require"):
            for line in reqs.splitlines():
                dep = _parse_pep508(line, source)
                if dep:
                    dep.is_dev = True
                    deps.append(dep)

    return deps


def _replace_spec_version(text: str, new_version: str) -> str | None:
    """Replace the first version constraint in a PEP 508 fragment."""
    m = _SPEC_RE.search(text)
    if not m:
        return None
    return text[: m.start(2)] + new_version + text[m.end(2) :]


def _update_requirements(
    content: str, changes: dict[str, str]
) -> tuple[str, list[str]]:
    changed: list[str] = []
    new_lines: list[str] = []
    for line in content.splitlines(keepends=True):
        dep = _parse_pep508(line)
        if dep and dep.name in changes and dep.version_specifier:
            cutoff = len(line)
            for sep in (";", " #"):
                idx = line.find(sep)
                if idx != -1:
                    cutoff = min(cutoff, idx)
            replaced = _replace_spec_version(line[:cutoff], changes[dep.name])
            if replaced is not None:
                line = replaced + line[cutoff:]
                changed.append(dep.name)
        new_lines.append(line)
    return "".join(new_lines), changed


def _update_pep508_array(array, changes: dict[str, str], changed: list[str]) -> None:
    for i, item in enumerate(array):
        req = str(item)
        dep = _parse_pep508(req)
        if dep and dep.name in changes:
            replaced = _replace_spec_version(req, changes[dep.name])
            if replaced is not None:
                array[i] = replaced
                changed.append(dep.name)


def _update_poetry_table(table, changes: dict[str, str], changed: list[str]) -> None:
    if table is None:
        return
    for name in table:
        if name == "python" or name not in changes:
            continue
        spec = table[name]
        if isinstance(spec, str):
            m = _TOML_OP_RE.match(spec)
            op = (m.group(1) or "") if m else ""
            table[name] = f"{op}{changes[name]}"
            changed.append(name)
        elif isinstance(spec, dict):
            version = spec.get("version")
            if isinstance(version, str):
                m = _TOML_OP_RE.match(version)
                op = (m.group(1) or "") if m else ""
                spec["version"] = f"{op}{changes[name]}"
                changed.append(name)


def _update_pyproject(content: str, changes: dict[str, str]) -> tuple[str, list[str]]:
    doc = tomlkit.parse(content)
    changed: list[str] = []

    project = doc.get("project")
    if project is not None:
        deps = project.get("dependencies")
        if deps is not None:
            _update_pep508_array(deps, changes, changed)
        optional = project.get("optional-dependencies")
        if optional is not None:
            for group in optional.values():
                _update_pep508_array(group, changes, changed)

    tool = doc.get("tool")
    poetry = tool.get("poetry") if tool is not None else None
    if poetry is not None:
        _update_poetry_table(poetry.get("dependencies"), changes, changed)
        groups = poetry.get("group")
        if groups is not None:
            for group in groups.values():
                _update_poetry_table(group.get("dependencies"), changes, changed)
        _update_poetry_table(poetry.get("dev-dependencies"), changes, changed)

    return tomlkit.dumps(doc), changed


class PythonParser(BaseParser):
    @property
    def name(self) -> str:
        return "python"

    @property
    def file_patterns(self) -> list[str]:
        return ["requirements.txt", "Pipfile", "pyproject.toml", "setup.cfg"]

    def parse(self, file_path: Path) -> ParseResult:
        errors: list[str] = []
        dependencies: list[Dependency] = []

        try:
            content = file_path.read_text(encoding="utf-8-sig")
            if file_path.name == "requirements.txt":
                dependencies = _parse_requirements(content, str(file_path))
            elif file_path.name == "pyproject.toml":
                dependencies = _parse_pyproject_toml(content, str(file_path))
            elif file_path.name == "Pipfile":
                dependencies = _parse_pipfile(content, str(file_path))
            elif file_path.name == "setup.cfg":
                dependencies = _parse_setup_cfg(content, str(file_path))
        except Exception as exc:
            errors.append(f"Failed to parse {file_path.name}: {exc}")

        return ParseResult(
            file_path=file_path,
            parser_name=self.name,
            dependencies=dependencies,
            errors=errors,
        )

    def supports_update(self, file_path: Path) -> bool:
        return file_path.name in ("requirements.txt", "pyproject.toml")

    def update_versions(
        self, file_path: Path, content: str, changes: dict[str, str]
    ) -> tuple[str, list[str]]:
        if file_path.name == "requirements.txt":
            return _update_requirements(content, changes)
        if file_path.name == "pyproject.toml":
            return _update_pyproject(content, changes)
        raise NotImplementedError(
            f"Updating {file_path.name} is not supported yet"
        )
