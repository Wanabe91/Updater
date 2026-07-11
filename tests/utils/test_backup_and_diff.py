from __future__ import annotations

from pathlib import Path

import pytest

from app.utils.backup import BackupManager
from app.utils.diff import compute_diff, create_unified_diff


class TestDiff:
    def test_no_changes(self) -> None:
        result = compute_diff("a\nb\n", "a\nb\n")
        assert result.has_changes is False
        assert result.diff_text == ""

    def test_unified_diff(self) -> None:
        diff = create_unified_diff("a\nb\n", "a\nc\n", "test.txt")
        assert "-b" in diff
        assert "+c" in diff
        assert "a/test.txt" in diff


class TestBackupManager:
    def test_create_and_restore(self, tmp_path: Path) -> None:
        target = tmp_path / "sub" / "requirements.txt"
        target.parent.mkdir()
        target.write_text("requests==1.0.0\n", encoding="utf-8")

        manager = BackupManager(tmp_path)
        backup = manager.create_backup([target], tag="update")
        assert backup.is_dir()
        assert "update" in backup.name

        target.write_text("requests==2.0.0\n", encoding="utf-8")
        restored = manager.restore_backup(backup)
        assert restored == [target]
        assert target.read_text(encoding="utf-8") == "requests==1.0.0\n"

    def test_list_backups_sorted(self, tmp_path: Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        manager = BackupManager(tmp_path)
        first = manager.create_backup([target])
        second = manager.create_backup([target])
        backups = manager.list_backups()
        assert len(backups) == 2
        assert backups[0]["path"] == first
        assert manager.latest_backup()["path"] == second

    def test_list_empty(self, tmp_path: Path) -> None:
        assert BackupManager(tmp_path).list_backups() == []
        assert BackupManager(tmp_path).latest_backup() is None

    def test_cleanup_old(self, tmp_path: Path) -> None:
        target = tmp_path / "f.txt"
        target.write_text("x", encoding="utf-8")
        manager = BackupManager(tmp_path)
        for _ in range(4):
            manager.create_backup([target])
        removed = manager.cleanup_old_backups(keep=2)
        assert removed == 2
        assert len(manager.list_backups()) == 2

    def test_restore_missing_manifest(self, tmp_path: Path) -> None:
        manager = BackupManager(tmp_path)
        with pytest.raises(FileNotFoundError):
            manager.restore_backup(tmp_path / "nope")
