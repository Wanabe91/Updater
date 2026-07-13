from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from app.ai.client import AIClient
from app.ai.code_fixer import CodeFixer, CodePatch
from app.db.repository import Repository
from app.utils.backup import BackupManager

if TYPE_CHECKING:
    from rich.progress import Progress, TaskID

logger = logging.getLogger(__name__)


@dataclass
class MigrationResult:
    files_changed: list[Path] = field(default_factory=list)
    patches: list[CodePatch] = field(default_factory=list)
    backup_path: Path | None = None
    success: bool = True


class Migrator:
    def __init__(
        self,
        project_path: Path,
        code_fixer: CodeFixer | None = None,
        repository: Repository | None = None,
    ) -> None:
        self.project_path = project_path.resolve()
        self._code_fixer = code_fixer
        self._repository = repository
        self._backup = BackupManager(self.project_path)

    @property
    def _fixer(self) -> CodeFixer:
        # Created lazily so rollback works without AI credentials.
        if self._code_fixer is None:
            self._code_fixer = CodeFixer(AIClient())
        return self._code_fixer

    def generate_migration(
        self,
        old_package: str,
        new_package: str,
        old_version: str = "",
        new_version: str = "",
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> list[CodePatch]:
        return self._fixer.generate_patches(
            self.project_path,
            old_package,
            new_package,
            old_version=old_version,
            new_version=new_version,
            progress=progress,
            task_id=task_id,
        )

    def apply_migration(
        self,
        patches: list[CodePatch],
        dry_run: bool = False,
        old_package: str = "",
        new_package: str = "",
    ) -> MigrationResult:
        result = MigrationResult(patches=patches)
        if dry_run or not patches:
            return result

        unique_files = list(dict.fromkeys(p.file_path for p in patches))
        result.backup_path = self._backup.create_backup(unique_files, tag="migrate")

        for patch in patches:
            patch.file_path.write_text(patch.new_code, encoding="utf-8")
            if patch.file_path not in result.files_changed:
                result.files_changed.append(patch.file_path)

        self._record_history(
            {
                "package_name": old_package or "(migration)",
                "old_version": "",
                "new_version": "",
                "action": "migrate",
                "details": {
                    "to": new_package,
                    "files": [str(p) for p in result.files_changed],
                },
            }
        )
        return result

    def rollback(self) -> Path | None:
        latest = self._backup.latest_backup(tag="migrate")
        if latest is None:
            return None
        restored = self._backup.restore_backup(latest["path"])
        self._record_history(
            {
                "package_name": "*",
                "action": "rollback",
                "details": {
                    "backup": str(latest["path"]),
                    "files": [str(p) for p in restored],
                },
            }
        )
        return latest["path"]

    def _record_history(self, entry: dict) -> None:
        if self._repository is None:
            return
        try:
            project = self._repository.get_or_create_project(self.project_path)
            self._repository.save_update(project.id, entry)
        except Exception as exc:
            logger.warning("Failed to record migration history: %s", exc)
