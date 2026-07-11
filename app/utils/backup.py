from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

_MANIFEST_NAME = "manifest.json"
_FILES_DIR = "files"


class BackupManager:
    def __init__(self, project_path: Path, backup_dir: Path | None = None) -> None:
        self.project_path = project_path.resolve()
        self.backup_dir = backup_dir or self.project_path / ".updater" / "backups"

    def create_backup(self, files: list[Path], tag: str | None = None) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        name = f"{timestamp}-{tag}" if tag else timestamp
        dest = self.backup_dir / name
        counter = 1
        while dest.exists():
            dest = self.backup_dir / f"{name}-{counter}"
            counter += 1

        relative_files: list[str] = []
        files_root = dest / _FILES_DIR
        for file_path in files:
            resolved = file_path.resolve()
            rel = resolved.relative_to(self.project_path)
            target = files_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved, target)
            relative_files.append(rel.as_posix())

        manifest = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "tag": tag,
            "files": relative_files,
        }
        (dest / _MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        return dest

    def restore_backup(self, backup_path: Path) -> list[Path]:
        manifest_path = backup_path / _MANIFEST_NAME
        if not manifest_path.is_file():
            raise FileNotFoundError(f"No manifest found in {backup_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        restored: list[Path] = []
        for rel in manifest.get("files", []):
            source = backup_path / _FILES_DIR / rel
            target = self.project_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            restored.append(target)
        return restored

    def list_backups(self) -> list[dict]:
        if not self.backup_dir.is_dir():
            return []
        backups: list[dict] = []
        for entry in sorted(self.backup_dir.iterdir()):
            manifest_path = entry / _MANIFEST_NAME
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            manifest["path"] = entry
            backups.append(manifest)
        return backups

    def latest_backup(self, tag: str | None = None) -> dict | None:
        backups = self.list_backups()
        if tag is not None:
            backups = [b for b in backups if b.get("tag") == tag]
        return backups[-1] if backups else None

    def cleanup_old_backups(self, keep: int = 10) -> int:
        backups = self.list_backups()
        removed = 0
        for manifest in backups[:-keep] if keep > 0 else backups:
            shutil.rmtree(manifest["path"], ignore_errors=True)
            removed += 1
        return removed
