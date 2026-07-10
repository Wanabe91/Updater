from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


class BackupManager:
    def __init__(self, project_path: Path, backup_dir: Optional[Path] = None) -> None:
        self.project_path = project_path
        self.backup_dir = backup_dir or project_path / ".updater" / "backups"

    def create_backup(self, files: list[Path], tag: Optional[str] = None) -> Path:
        raise NotImplementedError

    def restore_backup(self, backup_path: Path) -> None:
        raise NotImplementedError

    def list_backups(self) -> list[dict]:
        raise NotImplementedError

    def cleanup_old_backups(self, keep: int = 10) -> None:
        raise NotImplementedError