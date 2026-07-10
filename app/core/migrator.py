from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MigrationResult:
    files_changed: list[Path] = field(default_factory=list)
    patches: list[dict] = field(default_factory=list)
    success: bool = True


class Migrator:
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path

    def generate_migration(
        self,
        old_package: str,
        new_package: str,
        old_version: str,
        new_version: str,
    ) -> list[dict]:
        raise NotImplementedError

    def apply_migration(self, patches: list[dict], dry_run: bool = False) -> MigrationResult:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError