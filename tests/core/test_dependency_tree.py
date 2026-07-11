from __future__ import annotations

from pathlib import Path

import pytest

from app.core.dependency_tree import (
    DependencyNode,
    DependencyTree,
    TreeBuilder,
    TreeRenderer,
)


class StubMetadataRegistry:
    def __init__(self, metadata: dict[str, dict]) -> None:
        self._metadata = metadata
        self.calls: list[str] = []

    def get_metadata(self, package: str) -> dict | None:
        self.calls.append(package)
        return self._metadata.get(package.lower())


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "requirements.txt").write_text("alpha==1.0.0\n", encoding="utf-8")
    return root


def _builder(project: Path, metadata: dict[str, dict], **kwargs) -> TreeBuilder:
    return TreeBuilder(project, registry=StubMetadataRegistry(metadata), **kwargs)


class TestTreeBuilder:
    def test_builds_transitive_tree(self, project: Path) -> None:
        metadata = {
            "alpha": {"version": "2.0.0", "requires_dist": ["beta>=1.0"]},
            "beta": {"version": "1.5.0", "requires_dist": []},
        }
        tree = _builder(project, metadata).build()
        assert tree.root_name == "project"
        assert len(tree.children) == 1
        alpha = tree.children[0]
        assert alpha.name == "alpha"
        assert alpha.is_outdated is True
        assert alpha.latest_version == "2.0.0"
        assert [c.name for c in alpha.children] == ["beta"]

    def test_depth_limit(self, project: Path) -> None:
        metadata = {
            "alpha": {"version": "1.0.0", "requires_dist": ["beta"]},
            "beta": {"version": "1.0.0", "requires_dist": ["gamma"]},
            "gamma": {"version": "1.0.0", "requires_dist": []},
        }
        tree = _builder(project, metadata).build(depth=2)
        alpha = tree.children[0]
        beta = alpha.children[0]
        assert beta.children == []  # gamma cut off by depth

    def test_cycle_detection(self, project: Path) -> None:
        metadata = {
            "alpha": {"version": "1.0.0", "requires_dist": ["beta"]},
            "beta": {"version": "1.0.0", "requires_dist": ["alpha"]},
        }
        tree = _builder(project, metadata).build(depth=5)
        alpha = tree.children[0]
        beta = alpha.children[0]
        assert beta.children == []
        assert beta.has_conflict is True

    def test_extras_requirements_skipped(self, project: Path) -> None:
        metadata = {
            "alpha": {
                "version": "1.0.0",
                "requires_dist": [
                    "beta>=1.0",
                    'test-helper>=2.0; extra == "test"',
                ],
            },
            "beta": {"version": "1.0.0", "requires_dist": []},
        }
        tree = _builder(project, metadata).build()
        alpha = tree.children[0]
        assert [c.name for c in alpha.children] == ["beta"]

    def test_metadata_cached(self, project: Path) -> None:
        (project / "requirements.txt").write_text(
            "alpha==1.0.0\ngamma==1.0.0\n", encoding="utf-8"
        )
        registry = StubMetadataRegistry(
            {
                "alpha": {"version": "1.0.0", "requires_dist": ["shared"]},
                "gamma": {"version": "1.0.0", "requires_dist": ["shared"]},
                "shared": {"version": "1.0.0", "requires_dist": []},
            }
        )
        TreeBuilder(project, registry=registry).build()
        assert registry.calls.count("shared") == 1

    def test_package_filter(self, project: Path) -> None:
        (project / "requirements.txt").write_text(
            "alpha==1.0.0\ngamma==1.0.0\n", encoding="utf-8"
        )
        metadata = {
            "alpha": {"version": "1.0.0", "requires_dist": []},
            "gamma": {"version": "1.0.0", "requires_dist": []},
        }
        tree = _builder(project, metadata).build(package="gamma")
        assert [c.name for c in tree.children] == ["gamma"]

    def test_unknown_package_is_leaf(self, project: Path) -> None:
        tree = _builder(project, {}).build()
        alpha = tree.children[0]
        assert alpha.latest_version is None
        assert alpha.children == []


class TestTreeNavigation:
    def _tree(self) -> DependencyTree:
        return DependencyTree(
            root_name="demo",
            children=[
                DependencyNode(
                    name="a",
                    version="1.0",
                    children=[DependencyNode(name="b", version="2.0")],
                ),
                DependencyNode(name="c", version="3.0"),
            ],
        )

    def test_flatten_order(self) -> None:
        names = [n.name for n in self._tree().flatten()]
        assert names == ["a", "b", "c"]

    def test_find(self) -> None:
        tree = self._tree()
        assert tree.find("B") is not None
        assert tree.find("B").version == "2.0"
        assert tree.find("missing") is None


class TestTreeRenderer:
    def test_renders_rich_tree(self) -> None:
        tree = DependencyTree(
            root_name="demo",
            children=[
                DependencyNode(
                    name="a",
                    version="1.0",
                    latest_version="2.0",
                    is_outdated=True,
                )
            ],
        )
        rendered = TreeRenderer().render(tree, show_outdated=True)
        assert rendered.label == "[bold]demo[/bold]"
        assert "outdated" in rendered.children[0].label
