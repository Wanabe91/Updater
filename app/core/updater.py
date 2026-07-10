from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class UpdateResult:
    updated: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    backup_path: Optional[Path] = None


class Updater:
    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path

    def check_updates(self) -> list[dict]:
        raise NotImplementedError

    def apply_updates(self, updates: list[dict], dry_run: bool = False) -> UpdateResult:
        raise NotImplementedError

    def rollback(self, backup_path: Path) -> None:
        raise NotImplementedError