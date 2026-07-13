from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from packaging.version import InvalidVersion, Version

from app.core.scanner import Scanner
from app.core.version_resolver import VersionResolver
from app.db.repository import Repository
from app.parsers import get_all_parsers
from app.utils.backup import BackupManager

if TYPE_CHECKING:
    from rich.progress import Progress, TaskID

logger = logging.getLogger(__name__)


@dataclass
class PlannedUpdate:
    package: str
    current_version: str
    new_version: str
    source: str
    ecosystem: str
    is_dev: bool = False


@dataclass
class FileChange:
    file_path: Path
    old_content: str
    new_content: str
    packages: list[str] = field(default_factory=list)


@dataclass
class UpdateResult:
    updated: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    backup_path: Path | None = None
    changes: list[FileChange] = field(default_factory=list)


def _is_newer(target: str, current: str) -> bool:
    if not target or target == current:
        return False
    try:
        return Version(target) > Version(current)
    except InvalidVersion:
        return True


class Updater:
    def __init__(
        self,
        project_path: Path,
        resolver: VersionResolver | None = None,
        repository: Repository | None = None,
        max_depth: int = 10,
    ) -> None:
        self.project_path = project_path.resolve()
        self._resolver = resolver or VersionResolver()
        self._repository = repository
        self._max_depth = max_depth
        self._backup = BackupManager(self.project_path)
        self._parsers = get_all_parsers()

    def _find_parser(self, file_path: Path):
        return next((p for p in self._parsers if p.can_parse(file_path)), None)

    def check_updates(
        self,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> list[PlannedUpdate]:
        scan = Scanner(self.project_path, max_depth=self._max_depth).scan()
        planned: list[PlannedUpdate] = []
        seen: set[tuple[str, str]] = set()

        resolvable = [
            dep for dep in scan.dependencies
            if dep.version and dep.version != "*"
            and self._resolver.supports(dep.ecosystem)
        ]

        if progress is not None and task_id is not None:
            progress.update(
                task_id,
                total=len(resolvable),
                completed=0,
                description="[cyan]Resolving[/cyan] registry versions",
            )

        for dep in scan.dependencies:
            if not dep.version or dep.version == "*":
                continue
            if not self._resolver.supports(dep.ecosystem):
                continue
            source_path = Path(dep.source)
            parser = self._find_parser(source_path)
            if parser is None or not parser.supports_update(source_path):
                continue
            key = (dep.source, dep.name)
            if key in seen:
                continue
            seen.add(key)

            if progress is not None and task_id is not None:
                progress.update(
                    task_id,
                    description=f"[cyan]Checking[/cyan] {dep.name}",
                )
            resolved = self._resolver.resolve(
                dep.name, dep.version, dep.ecosystem, dep.version_specifier
            )
            if resolved is None:
                if progress is not None and task_id is not None:
                    progress.update(
                        task_id,
                        description=f"[yellow]not found[/yellow] {dep.name}",
                        advance=1,
                    )
                continue
            # A pin ("==") always "satisfies" itself, so bump pins to the
            # latest release; range specifiers stay within their range.
            if dep.version_specifier in ("==", "==="):
                target = resolved.latest
            else:
                target = resolved.latest_compatible
            if _is_newer(target, dep.version):
                planned.append(
                    PlannedUpdate(
                        package=dep.name,
                        current_version=dep.version,
                        new_version=target,
                        source=dep.source,
                        ecosystem=dep.ecosystem,
                        is_dev=dep.is_dev,
                    )
                )
                if progress is not None and task_id is not None:
                    progress.update(
                        task_id,
                        description=(
                            f"[red]{dep.name}[/red] → {target} "
                            f"[dim](from {dep.version})[/dim]"
                        ),
                        advance=1,
                    )
            else:
                if progress is not None and task_id is not None:
                    progress.update(
                        task_id,
                        description=f"[green]{dep.name}[/green] up to date",
                        advance=1,
                    )
        return planned

    def _plan_changes(
        self, updates: list[PlannedUpdate]
    ) -> tuple[list[FileChange], list[dict]]:
        by_file: dict[str, list[PlannedUpdate]] = {}
        for update in updates:
            by_file.setdefault(update.source, []).append(update)

        changes: list[FileChange] = []
        failed: list[dict] = []
        for source, file_updates in by_file.items():
            file_path = Path(source)
            wanted = {u.package: u.new_version for u in file_updates}
            try:
                parser = self._find_parser(file_path)
                if parser is None or not parser.supports_update(file_path):
                    raise NotImplementedError(
                        f"No update support for {file_path.name}"
                    )
                old_content = file_path.read_text(encoding="utf-8-sig")
                new_content, changed = parser.update_versions(
                    file_path, old_content, wanted
                )
            except Exception as exc:
                failed.extend(
                    {"package": u.package, "source": source, "error": str(exc)}
                    for u in file_updates
                )
                continue

            missed = set(wanted) - set(changed)
            failed.extend(
                {
                    "package": name,
                    "source": source,
                    "error": "could not locate version to replace",
                }
                for name in missed
            )
            if changed and new_content != old_content:
                changes.append(
                    FileChange(
                        file_path=file_path,
                        old_content=old_content,
                        new_content=new_content,
                        packages=sorted(set(changed)),
                    )
                )
        return changes, failed

    def apply_updates(
        self, updates: list[PlannedUpdate], dry_run: bool = False
    ) -> UpdateResult:
        changes, failed = self._plan_changes(updates)
        result = UpdateResult(failed=failed, changes=changes)
        if dry_run or not changes:
            return result

        result.backup_path = self._backup.create_backup(
            [c.file_path for c in changes], tag="update"
        )

        by_key = {(u.source, u.package): u for u in updates}
        for change in changes:
            change.file_path.write_text(change.new_content, encoding="utf-8")
            for package in change.packages:
                update = by_key.get((str(change.file_path), package))
                entry = {
                    "package_name": package,
                    "old_version": update.current_version if update else "",
                    "new_version": update.new_version if update else "",
                    "action": "update",
                    "details": {"file": str(change.file_path)},
                }
                result.updated.append(entry)
                self._record_history(entry)

        return result

    def rollback(self) -> Path | None:
        latest = self._backup.latest_backup(tag="update")
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
            logger.warning("Failed to record update history: %s", exc)
