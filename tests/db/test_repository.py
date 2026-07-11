from __future__ import annotations

from pathlib import Path

import pytest

from app.db.repository import Repository


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    return Repository(tmp_path / "db" / "test.db")


def _dep(name: str, version: str = "1.0.0", **kwargs) -> dict:
    return {
        "name": name,
        "version": version,
        "version_specifier": kwargs.get("version_specifier", "=="),
        "is_dev": kwargs.get("is_dev", False),
        "source": kwargs.get("source", "requirements.txt"),
        "ecosystem": kwargs.get("ecosystem", "python"),
        **{k: v for k, v in kwargs.items() if k in ("latest_version", "is_outdated")},
    }


class TestProject:
    def test_creates_parent_dir(self, tmp_path: Path) -> None:
        repo = Repository(tmp_path / "nested" / "dir" / "test.db")
        assert repo.db_path.parent.is_dir()

    def test_get_or_create_is_idempotent(self, repo: Repository, tmp_path: Path) -> None:
        first = repo.get_or_create_project(tmp_path)
        second = repo.get_or_create_project(tmp_path)
        assert first.id == second.id
        assert second.name == tmp_path.name

    def test_get_project_missing(self, repo: Repository, tmp_path: Path) -> None:
        assert repo.get_project(tmp_path / "nope") is None


class TestDependencies:
    def test_save_and_get(self, repo: Repository, tmp_path: Path) -> None:
        project = repo.get_or_create_project(tmp_path)
        repo.save_dependencies(
            project.id,
            [_dep("requests"), _dep("flask", latest_version="3.0.0", is_outdated=True)],
        )
        records = repo.get_dependencies(project.id)
        assert [r.name for r in records] == ["flask", "requests"]
        flask = records[0]
        assert flask.latest_version == "3.0.0"
        assert flask.is_outdated is True
        assert flask.source_file == "requirements.txt"

    def test_snapshot_is_replaced(self, repo: Repository, tmp_path: Path) -> None:
        project = repo.get_or_create_project(tmp_path)
        repo.save_dependencies(project.id, [_dep("old-package")])
        repo.save_dependencies(project.id, [_dep("new-package")])
        records = repo.get_dependencies(project.id)
        assert [r.name for r in records] == ["new-package"]

    def test_snapshots_are_per_project(self, repo: Repository, tmp_path: Path) -> None:
        a = repo.get_or_create_project(tmp_path / "a")
        b = repo.get_or_create_project(tmp_path / "b")
        repo.save_dependencies(a.id, [_dep("only-in-a")])
        repo.save_dependencies(b.id, [_dep("only-in-b")])
        assert [r.name for r in repo.get_dependencies(a.id)] == ["only-in-a"]


class TestUpdateHistory:
    def test_save_and_get(self, repo: Repository, tmp_path: Path) -> None:
        project = repo.get_or_create_project(tmp_path)
        repo.save_update(
            project.id,
            {
                "package_name": "requests",
                "old_version": "1.0.0",
                "new_version": "2.0.0",
                "action": "update",
                "details": {"file": "requirements.txt"},
            },
        )
        entries = repo.get_update_history(project.id)
        assert len(entries) == 1
        assert entries[0].package_name == "requests"
        assert entries[0].success is True
        assert entries[0].details == {"file": "requirements.txt"}

    def test_limit_and_order(self, repo: Repository, tmp_path: Path) -> None:
        project = repo.get_or_create_project(tmp_path)
        for i in range(5):
            repo.save_update(
                project.id,
                {"package_name": f"pkg{i}", "new_version": "1.0.0"},
            )
        entries = repo.get_update_history(project.id, limit=2)
        assert len(entries) == 2
        assert entries[0].package_name == "pkg4"


class TestSuggestionsAndTrees:
    def test_save_suggestion(self, repo: Repository, tmp_path: Path) -> None:
        project = repo.get_or_create_project(tmp_path)
        record = repo.save_suggestion(
            project.id,
            {
                "original_package": "requests",
                "suggested_package": "httpx",
                "reason": "async support",
                "confidence": 0.9,
            },
        )
        assert record.id is not None
        assert record.accepted is None

    def test_save_and_get_latest_tree(self, repo: Repository, tmp_path: Path) -> None:
        project = repo.get_or_create_project(tmp_path)
        repo.save_tree(project.id, {"root": "first"})
        repo.save_tree(project.id, {"root": "second"})
        latest = repo.get_latest_tree(project.id)
        assert latest is not None
        assert latest.tree_data == {"root": "second"}

    def test_latest_tree_missing(self, repo: Repository, tmp_path: Path) -> None:
        project = repo.get_or_create_project(tmp_path)
        assert repo.get_latest_tree(project.id) is None
