from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from app.cli.progress import add_task, make_registry_progress
from app.cli.render import print_unified_diff
from app.config import settings
from app.core.scanner import Scanner
from app.core.updater import Updater
from app.core.version_resolver import VersionResolver
from app.db.repository import Repository
from app.utils.diff import create_unified_diff

app = typer.Typer(help="Update project dependencies.")
console = Console()


@app.command()
def check(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
) -> None:
    """Check for newer versions of project dependencies."""
    path = Path(project_path).resolve()
    if not path.is_dir():
        console.print(f"[red]Error:[/red] '{path}' is not a directory.")
        raise typer.Exit(1)

    scanner = Scanner(path, max_depth=settings.max_depth)
    result = scanner.scan()

    if not result.dependencies:
        console.print("[yellow]No dependencies found.[/yellow]")
        return

    resolver = VersionResolver()
    supported = [d for d in result.dependencies if resolver.supports(d.ecosystem)]
    skipped = len(result.dependencies) - len(supported)

    if not supported:
        console.print(
            "[yellow]No dependencies from supported ecosystems found.[/yellow]"
        )
        return

    with make_registry_progress() as progress:
        task = add_task(
            progress,
            "[cyan]Resolving[/cyan] registry versions",
            total=len(supported),
        )
        resolved = resolver.resolve_batch(
            supported, progress=progress, task_id=task
        )
        stats = progress.tasks[task]
        elapsed = stats.finished_time or 0.0

    table = Table(title=f"Updates for {path.name}")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Current", style="magenta")
    table.add_column("Compatible", style="green")
    table.add_column("Latest", style="blue")
    table.add_column("Status", justify="center")

    outdated_count = 0
    for res in sorted(resolved, key=lambda r: r.package):
        if res.is_outdated:
            outdated_count += 1
            status = "[red]outdated[/red]"
        elif not res.current:
            status = "[dim]unpinned[/dim]"
        else:
            status = "[green]up to date[/green]"

        table.add_row(
            res.package,
            res.current or "-",
            res.latest_compatible,
            res.latest,
            status,
        )

    console.print(table)
    console.print(
        f"\n[bold]{outdated_count}[/bold] of [bold]{len(resolved)}[/bold] "
        f"dependencies are outdated."
    )
    if skipped:
        console.print(
            f"[dim]{skipped} dependencies skipped "
            f"(ecosystem not supported by the resolver yet).[/dim]"
        )
    unresolved = len(supported) - len(resolved) - _duplicate_count(supported)
    if unresolved > 0:
        console.print(
            f"[dim]{unresolved} dependencies could not be resolved "
            f"(not found in the registry).[/dim]"
        )
    console.print(
        f"[dim]Resolved {len(supported)} packages · "
        f"{outdated_count} outdated · {elapsed:.1f}s[/dim]"
    )

    _save_snapshot(path, result.dependencies, resolved)


def _save_snapshot(path: Path, dependencies: list, resolved: list) -> None:
    resolved_by_name = {r.package: r for r in resolved}
    records = []
    for dep in dependencies:
        record = dep.to_dict()
        res = resolved_by_name.get(dep.name)
        if res is not None:
            record["latest_version"] = res.latest
            record["is_outdated"] = res.is_outdated
        records.append(record)
    try:
        repo = Repository(settings.db_path)
        project = repo.get_or_create_project(path)
        repo.save_dependencies(project.id, records)
    except Exception as exc:
        console.print(f"[dim]Could not save snapshot: {exc}[/dim]")


def _duplicate_count(dependencies: list) -> int:
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    for dep in dependencies:
        key = (dep.ecosystem, dep.name)
        if key in seen:
            duplicates += 1
        seen.add(key)
    return duplicates


@app.command()
def apply(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying."),
) -> None:
    """Update manifest files to the latest compatible versions."""
    path = Path(project_path).resolve()
    if not path.is_dir():
        console.print(f"[red]Error:[/red] '{path}' is not a directory.")
        raise typer.Exit(1)

    updater = Updater(
        path,
        repository=Repository(settings.db_path),
        max_depth=settings.max_depth,
    )
    with make_registry_progress() as progress:
        task = add_task(
            progress,
            "[cyan]Resolving[/cyan] registry versions",
        )
        planned = updater.check_updates(progress=progress, task_id=task)
        stats = progress.tasks[task]
        elapsed = stats.finished_time or 0.0

    if not planned:
        console.print("[green]All dependencies are already up to date.[/green]")
        console.print(
            f"[dim]Resolved {int(stats.total or 0)} packages · "
            f"0 outdated · {elapsed:.1f}s[/dim]"
        )
        return

    table = Table(title="Planned updates")
    table.add_column("Name", style="cyan")
    table.add_column("From", style="magenta")
    table.add_column("To", style="green")
    table.add_column("File", style="dim", overflow="fold")
    for update in sorted(planned, key=lambda u: u.package):
        table.add_row(
            update.package,
            update.current_version,
            update.new_version,
            _relative(update.source, path),
        )
    console.print(table)
    console.print(
        f"[dim]Resolved {int(stats.total or 0)} packages · "
        f"{len(planned)} outdated · {elapsed:.1f}s[/dim]"
    )

    result = updater.apply_updates(planned, dry_run=dry_run)

    if dry_run:
        console.print("\n[bold]Dry run — no files were modified.[/bold]\n")
        for change in result.changes:
            diff = create_unified_diff(
                change.old_content,
                change.new_content,
                _relative(str(change.file_path), path),
            )
            print_unified_diff(console, diff)
    else:
        console.print(
            f"\n[green]Updated {len(result.updated)} packages "
            f"in {len(result.changes)} files.[/green]"
        )
        if result.backup_path:
            console.print(f"[dim]Backup: {result.backup_path}[/dim]")

    if result.failed:
        console.print(f"[red]Failed ({len(result.failed)}):[/red]")
        for failure in result.failed:
            console.print(
                f"  [red]-[/red] {failure['package']} "
                f"({_relative(failure['source'], path)}): {failure['error']}"
            )


@app.command()
def rollback(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
) -> None:
    """Restore manifest files from the most recent backup."""
    path = Path(project_path).resolve()
    updater = Updater(path, repository=Repository(settings.db_path))
    restored = updater.rollback()
    if restored is None:
        console.print("[yellow]No backups found.[/yellow]")
        raise typer.Exit(1)
    console.print(f"[green]Restored files from backup:[/green] {restored}")


def _relative(source: str, base: Path) -> str:
    try:
        return str(Path(source).relative_to(base))
    except ValueError:
        return source
