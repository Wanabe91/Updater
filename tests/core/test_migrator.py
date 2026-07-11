from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.code_fixer import CodeFixer
from app.core.migrator import Migrator
from app.db.repository import Repository
from tests.ai.test_code_fixer import StubClient


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "main.py").write_text(
        "import old_pkg\nold_pkg.get()\n", encoding="utf-8"
    )
    return root


def _migrator(project: Path, responses: list[str], **kwargs) -> Migrator:
    fixer = CodeFixer(StubClient(responses))
    return Migrator(project, code_fixer=fixer, **kwargs)


_IMPORT_RESPONSE = "import new_pkg\nold_pkg.get()\n"
_API_RESPONSE = (
    '{"migrated_code": "import new_pkg\\nnew_pkg.get()\\n",'
    ' "breaking_changes": ["get moved"]}'
)


class TestGenerateMigration:
    def test_generates_patches(self, project: Path) -> None:
        migrator = _migrator(project, [_IMPORT_RESPONSE, _API_RESPONSE])
        patches = migrator.generate_migration("old_pkg", "new_pkg")
        assert len(patches) == 2
        assert patches[-1].new_code == "import new_pkg\nnew_pkg.get()\n"

    def test_no_matching_files(self, project: Path) -> None:
        migrator = _migrator(project, [])
        assert migrator.generate_migration("unused_pkg", "new_pkg") == []


class TestApplyMigration:
    def test_dry_run_does_not_write(self, project: Path) -> None:
        migrator = _migrator(project, [_IMPORT_RESPONSE, _API_RESPONSE])
        patches = migrator.generate_migration("old_pkg", "new_pkg")
        result = migrator.apply_migration(patches, dry_run=True)
        assert result.backup_path is None
        assert result.files_changed == []
        content = (project / "main.py").read_text(encoding="utf-8")
        assert content == "import old_pkg\nold_pkg.get()\n"

    def test_apply_writes_and_backs_up(self, project: Path) -> None:
        migrator = _migrator(project, [_IMPORT_RESPONSE, _API_RESPONSE])
        patches = migrator.generate_migration("old_pkg", "new_pkg")
        result = migrator.apply_migration(
            patches, old_package="old_pkg", new_package="new_pkg"
        )
        assert result.backup_path is not None
        assert result.files_changed == [project / "main.py"]
        content = (project / "main.py").read_text(encoding="utf-8")
        assert content == "import new_pkg\nnew_pkg.get()\n"

    def test_rollback_restores(self, project: Path) -> None:
        migrator = _migrator(project, [_IMPORT_RESPONSE, _API_RESPONSE])
        patches = migrator.generate_migration("old_pkg", "new_pkg")
        migrator.apply_migration(patches)
        restored = migrator.rollback()
        assert restored is not None
        content = (project / "main.py").read_text(encoding="utf-8")
        assert content == "import old_pkg\nold_pkg.get()\n"

    def test_rollback_without_backup(self, project: Path) -> None:
        migrator = _migrator(project, [])
        assert migrator.rollback() is None

    def test_history_recorded(self, project: Path, tmp_path: Path) -> None:
        repo = Repository(tmp_path / "test.db")
        migrator = _migrator(
            project, [_IMPORT_RESPONSE, _API_RESPONSE], repository=repo
        )
        patches = migrator.generate_migration("old_pkg", "new_pkg")
        migrator.apply_migration(
            patches, old_package="old_pkg", new_package="new_pkg"
        )
        db_project = repo.get_project(project)
        assert db_project is not None
        history = repo.get_update_history(db_project.id)
        assert len(history) == 1
        assert history[0].action == "migrate"
        assert history[0].details["to"] == "new_pkg"
