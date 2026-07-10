from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DependencyNode:
    name: str
    version: str
    latest_version: Optional[str] = None
    is_outdated: bool = False
    has_conflict: bool = False
    children: list[DependencyNode] = field(default_factory=list)


@dataclass
class DependencyTree:
    root_name: str
    children: list[DependencyNode] = field(default_factory=list)

    def find(self, name: str) -> Optional[DependencyNode]:
        raise NotImplementedError

    def flatten(self) -> list[DependencyNode]:
        raise NotImplementedError


class TreeBuilder:
    def __init__(self, project_path: str) -> None:
        self.project_path = project_path

    def build(self, depth: Optional[int] = None) -> DependencyTree:
        raise NotImplementedError


class TreeRenderer:
    def __init__(self) -> None:
        pass

    def render(self, tree: DependencyTree, show_outdated: bool = False) -> str:
        raise NotImplementedError