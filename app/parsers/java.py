from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from app.parsers.base import BaseParser, Dependency, ParseResult

_PROP_RE = re.compile(r"\$\{([^}]+)\}")
_GRADLE_COORD_RE = re.compile(r"""["']([^"']+:[^"']+:[^"']+)["']""")
_GRADLE_MAP_RE = re.compile(
    r"""group\s*[:=]\s*["']([^"']+)["']\s*,?\s*"""
    r"""name\s*[:=]\s*["']([^"']+)["']\s*,?\s*"""
    r"""version\s*[:=]\s*["']([^"']+)["']"""
)
_GRADLE_TEST_CONF_RE = re.compile(
    r"\btest(Implementation|CompileOnly|Compile|Api|RuntimeOnly|Runtime)\b"
)


def _strip_ns(tag: str) -> str:
    idx = tag.find("}")
    if idx != -1:
        return tag[idx + 1 :]
    return tag


def _find_text(elem: ET.Element, tag: str) -> str:
    for child in elem:
        if _strip_ns(child.tag) == tag and child.text:
            return child.text.strip()
    return ""


def _resolve_version(version: str, properties: dict[str, str]) -> str:
    if not version:
        return ""
    for _ in range(5):
        m = _PROP_RE.search(version)
        if not m:
            break
        prop_name = m.group(1)
        prop_value = properties.get(prop_name)
        if prop_value is None:
            break
        version = version.replace(m.group(0), prop_value)
    return version


def _parse_pom_xml(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []
    root = ET.fromstring(content)

    properties: dict[str, str] = {}
    for elem in root.iter():
        if _strip_ns(elem.tag) == "properties":
            for prop in elem:
                if prop.text:
                    properties[_strip_ns(prop.tag)] = prop.text.strip()

    for elem in root.iter():
        if _strip_ns(elem.tag) != "dependency":
            continue

        group_id = _find_text(elem, "groupId")
        artifact_id = _find_text(elem, "artifactId")
        version = _find_text(elem, "version")
        scope = _find_text(elem, "scope")

        if not artifact_id:
            continue

        name = f"{group_id}:{artifact_id}" if group_id else artifact_id
        version = _resolve_version(version, properties)
        is_dev = scope in ("test", "provided")

        deps.append(
            Dependency(
                name=name,
                version=version,
                version_specifier="",
                is_dev=is_dev,
                source=source,
            )
        )

    return deps


def _parse_gradle(content: str, source: str) -> list[Dependency]:
    deps: list[Dependency] = []

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue

        is_dev = bool(_GRADLE_TEST_CONF_RE.search(stripped))

        for match in _GRADLE_COORD_RE.finditer(stripped):
            coord = match.group(1)
            parts = coord.split(":")
            if len(parts) >= 3:
                name = f"{parts[0]}:{parts[1]}"
                version = parts[2].split("@")[0]
                deps.append(
                    Dependency(
                        name=name,
                        version=version,
                        version_specifier="",
                        is_dev=is_dev,
                        source=source,
                    )
                )

        for match in _GRADLE_MAP_RE.finditer(stripped):
            deps.append(
                Dependency(
                    name=f"{match.group(1)}:{match.group(2)}",
                    version=match.group(3),
                    version_specifier="",
                    is_dev=is_dev,
                    source=source,
                )
            )

    return deps


class JavaParser(BaseParser):
    @property
    def name(self) -> str:
        return "java"

    @property
    def file_patterns(self) -> list[str]:
        return ["pom.xml", "build.gradle", "build.gradle.kts"]

    def parse(self, file_path: Path) -> ParseResult:
        errors: list[str] = []
        dependencies: list[Dependency] = []

        try:
            content = file_path.read_text(encoding="utf-8-sig")
            if file_path.name == "pom.xml":
                dependencies = _parse_pom_xml(content, str(file_path))
            elif file_path.name in ("build.gradle", "build.gradle.kts"):
                dependencies = _parse_gradle(content, str(file_path))
        except Exception as exc:
            errors.append(f"Failed to parse {file_path.name}: {exc}")

        return ParseResult(
            file_path=file_path,
            parser_name=self.name,
            dependencies=dependencies,
            errors=errors,
        )
