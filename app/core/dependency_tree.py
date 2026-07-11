from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from packaging.version import InvalidVersion, Version
from rich.tree import Tree

from app.core.scanner import Scanner
from app.core.version_resolver import PyPIClient
from app.parsers.python import _parse_pep508

logger = logging.getLogger(__name__)


@dataclass
class DependencyNode:
    name: str
    version: str
    latest_version: str | None = None
    is_outdated: bool = False
    has_conflict: bool = False
    children: list[DependencyNode] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "latest_version": self.latest_version,
            "is_outdated": self.is_outdated,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class DependencyTree:
    root_name: str
    children: list[DependencyNode] = field(default_factory=list)

    def find(self, name: str) -> DependencyNode | None:
        target = name.lower()
        for node in self.flatten():
            if node.name.lower() == target:
                return node
        return None

    def flatten(self) -> list[DependencyNode]:
        nodes: list[DependencyNode] = []
        stack = list(reversed(self.children))
        while stack:
            node = stack.pop()
            nodes.append(node)
            stack.extend(reversed(node.children))
        return nodes

    def to_dict(self) -> dict:
        return {
            "root_name": self.root_name,
            "children": [child.to_dict() for child in self.children],
        }


def _is_outdated(current: str, latest: str | None) -> bool:
    if not current or not latest:
        return False
    try:
        return Version(latest) > Version(current)
    except InvalidVersion:
        return False


def _runtime_requirements(requires_dist: list[str]) -> list[tuple[str, str]]:
    """Extract (name, version) pairs, skipping extras-only requirements."""
    requirements: list[tuple[str, str]] = []
    for req_str in requires_dist:
        marker = req_str.split(";", 1)[1] if ";" in req_str else ""
        if "extra" in marker:
            continue
        dep = _parse_pep508(req_str)
        if dep:
            requirements.append((dep.name, dep.version))
    return requirements


class TreeBuilder:
    def __init__(
        self,
        project_path: Path | str,
        registry: PyPIClient | None = None,
        max_depth: int = 3,
        scan_max_depth: int = 10,
    ) -> None:
        self.project_path = Path(project_path).resolve()
        self._registry = registry or PyPIClient()
        self._max_depth = max_depth
        self._scan_max_depth = scan_max_depth
        self._meta_cache: dict[str, dict | None] = {}

    def build(
        self, depth: int | None = None, package: str | None = None
    ) -> DependencyTree:
        max_depth = depth if depth is not None else self._max_depth
        scan = Scanner(self.project_path, max_depth=self._scan_max_depth).scan()

        seen: set[str] = set()
        roots = []
        for dep in scan.dependencies:
            if dep.ecosystem != "python":
                continue
            key = dep.name.lower()
            if key in seen:
                continue
            seen.add(key)
            roots.append(dep)
        if package:
            roots = [d for d in roots if d.name.lower() == package.lower()]

        tree = DependencyTree(root_name=self.project_path.name)
        for dep in roots:
            tree.children.append(
                self._build_node(
                    dep.name, dep.version, max_depth - 1, {dep.name.lower()}
                )
            )
        return tree

    def _get_metadata(self, package: str) -> dict | None:
        key = package.lower()
        if key not in self._meta_cache:
            try:
                self._meta_cache[key] = self._registry.get_metadata(package)
            except httpx.HTTPError as exc:
                logger.warning("Failed to fetch metadata for %s: %s", package, exc)
                self._meta_cache[key] = None
        return self._meta_cache[key]

    def _build_node(
        self, name: str, version: str, remaining: int, path: set[str]
    ) -> DependencyNode:
        node = DependencyNode(name=name, version=version)
        meta = self._get_metadata(name)
        if meta is None:
            return node

        node.latest_version = meta["version"] or None
        node.is_outdated = _is_outdated(version, node.latest_version)

        if remaining > 0:
            for child_name, child_version in _runtime_requirements(
                meta["requires_dist"]
            ):
                child_key = child_name.lower()
                if child_key in path:
                    node.has_conflict = True  # cycle detected
                    continue
                node.children.append(
                    self._build_node(
                        child_name,
                        child_version,
                        remaining - 1,
                        path | {child_key},
                    )
                )
        return node


class TreeRenderer:
    def render(self, tree: DependencyTree, show_outdated: bool = False) -> Tree:
        root = Tree(f"[bold]{tree.root_name}[/bold]")
        for node in tree.children:
            self._render_node(root, node, show_outdated)
        return root

    def _render_node(
        self, parent: Tree, node: DependencyNode, show_outdated: bool
    ) -> None:
        label = f"[cyan]{node.name}[/cyan]"
        if node.version:
            label += f" [magenta]{node.version}[/magenta]"
        if show_outdated and node.is_outdated:
            label += f" [red](outdated, latest {node.latest_version})[/red]"
        branch = parent.add(label)
        for child in node.children:
            self._render_node(branch, child, show_outdated)
