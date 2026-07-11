from __future__ import annotations

from pathlib import Path

import pytest

from app.core.updater import Updater
from app.core.version_resolver import VersionResolver
from app.db.repository import Repository
from tests.core.test_version_resolver import StubRegistry


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "requirements.txt").write_text(
        "requests==1.0.0\nflask==2.0.0\n", encoding="utf-8"
    )
    return root


def _updater(project: Path, versions: dict[str, list[str]], **kwargs) -> Updater:
    resolver = VersionResolver(registries={"python": StubRegistry(versions)})
    return Updater(project, resolver=resolver, **kwargs)


class TestCheckUpdates:
    def test_finds_outdated(self, project: Path) -> None:
        updater = _updater(
            project,
            {"requests": ["1.0.0", "2.0.0"], "flask": ["2.0.0"]},
        )
        planned = updater.check_updates()
        assert len(planned) == 1
        assert planned[0].package == "requests"
        assert planned[0].new_version == "2.0.0"

    def test_pin_bumps_to_latest(self, project: Path) -> None:
        (project / "requirements.txt").write_text(
            "requests==1.0.0\n", encoding="utf-8"
        )
        updater = _updater(project, {"requests": ["1.0.0", "1.5.0", "2.0.0"]})
        planned = updater.check_updates()
        assert len(planned) == 1
        assert planned[0].new_version == "2.0.0"

    def test_range_specifier_stays_in_range(self, project: Path) -> None:
        (project / "requirements.txt").write_text(
            "requests~=1.0.0\n", encoding="utf-8"
        )
        updater = _updater(
            project, {"requests": ["1.0.0", "1.0.5", "1.5.0", "2.0.0"]}
        )
        planned = updater.check_updates()
        assert len(planned) == 1
        assert planned[0].new_version == "1.0.5"

    def test_up_to_date_project(self, project: Path) -> None:
        updater = _updater(
            project, {"requests": ["1.0.0"], "flask": ["2.0.0"]}
        )
        assert updater.check_updates() == []


class TestApplyUpdates:
    def _plan(self, project: Path) -> tuple[Updater, list]:
        (project / "requirements.txt").write_text(
            "requests>=1.0.0\n", encoding="utf-8"
        )
        updater = _updater(project, {"requests": ["1.0.0", "2.0.0"]})
        return updater, updater.check_updates()

    def test_dry_run_does_not_write(self, project: Path) -> None:
        updater, planned = self._plan(project)
        result = updater.apply_updates(planned, dry_run=True)
        assert len(result.changes) == 1
        assert result.backup_path is None
        assert result.updated == []
        content = (project / "requirements.txt").read_text(encoding="utf-8")
        assert "requests>=1.0.0" in content

    def test_apply_writes_and_backs_up(self, project: Path) -> None:
        updater, planned = self._plan(project)
        result = updater.apply_updates(planned)
        assert len(result.updated) == 1
        assert result.updated[0]["package_name"] == "requests"
        assert result.backup_path is not None
        content = (project / "requirements.txt").read_text(encoding="utf-8")
        assert "requests>=2.0.0" in content

    def test_rollback_restores(self, project: Path) -> None:
        updater, planned = self._plan(project)
        updater.apply_updates(planned)
        restored = updater.rollback()
        assert restored is not None
        content = (project / "requirements.txt").read_text(encoding="utf-8")
        assert "requests>=1.0.0" in content

    def test_rollback_without_backup(self, project: Path) -> None:
        updater = _updater(project, {})
        assert updater.rollback() is None

    def test_history_recorded(self, project: Path, tmp_path: Path) -> None:
        repo = Repository(tmp_path / "test.db")
        (project / "requirements.txt").write_text(
            "requests>=1.0.0\n", encoding="utf-8"
        )
        updater = _updater(
            project, {"requests": ["1.0.0", "2.0.0"]}, repository=repo
        )
        updater.apply_updates(updater.check_updates())

        db_project = repo.get_project(project)
        assert db_project is not None
        history = repo.get_update_history(db_project.id)
        assert len(history) == 1
        assert history[0].package_name == "requests"
        assert history[0].new_version == "2.0.0"
