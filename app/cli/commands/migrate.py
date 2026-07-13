from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from app.cli.progress import add_task, make_ai_progress
from app.cli.render import print_unified_diff
from app.config import settings
from app.core.migrator import Migrator
from app.db.repository import Repository
from app.utils.diff import create_unified_diff

app = typer.Typer(help="Migrate code to new dependency APIs.")
console = Console()


@app.command()
def run(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
    package: str = typer.Option(..., "--package", "-P", help="Package to migrate away from."),
    to: str = typer.Option(..., "--to", "-t", help="Package to migrate to."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying."),
) -> None:
    """Rewrite project code from one package to another using AI."""
    path = Path(project_path).resolve()
    if not path.is_dir():
        console.print(f"[red]Error:[/red] '{path}' is not a directory.")
        raise typer.Exit(1)

    migrator = Migrator(path, repository=Repository(settings.db_path))

    try:
        with make_ai_progress() as progress:
            task = add_task(
                progress,
                f"[cyan]Scanning[/cyan] files for '[bold]{package}[/bold]'",
            )
            patches = migrator.generate_migration(
                package, to, progress=progress, task_id=task
            )
            stats = progress.tasks[task]
            scanned_files = int(stats.total or 0)
            elapsed = stats.finished_time or 0.0
    except Exception as exc:
        console.print(
            f"[red]Migration generation failed:[/red] {exc}\n"
            "[dim]Check UPDATER_OPENAI_API_KEY (or .env) and retry.[/dim]"
        )
        raise typer.Exit(1) from exc

    if not patches:
        console.print(
            f"[yellow]No files using '{package}' needed changes.[/yellow]"
        )
        if scanned_files:
            console.print(
                f"[dim]Scanned {scanned_files} file(s) · "
                f"{elapsed:.1f}s · 0 patches[/dim]"
            )
        return

    console.print(
        f"\n[bold]{len(patches)}[/bold] patches for migration "
        f"[cyan]{package}[/cyan] -> [green]{to}[/green]:\n"
    )
    for patch in patches:
        label = _relative(patch.file_path, path)
        if patch.description:
            console.print(f"[bold]{label}[/bold] — {patch.description}")
        diff = create_unified_diff(patch.old_code, patch.new_code, label)
        print_unified_diff(console, diff)

    console.print(
        f"[dim]Scanned {scanned_files} file(s) · "
        f"{len(patches)} patches · {elapsed:.1f}s[/dim]"
    )

    if dry_run:
        console.print("[bold]Dry run — no files were modified.[/bold]")
        return

    result = migrator.apply_migration(patches, old_package=package, new_package=to)
    console.print(f"[green]Migrated {len(result.files_changed)} files.[/green]")
    if result.backup_path:
        console.print(f"[dim]Backup: {result.backup_path}[/dim]")


@app.command()
def rollback(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
) -> None:
    """Restore code files from the most recent migration backup."""
    path = Path(project_path).resolve()
    migrator = Migrator(path, repository=Repository(settings.db_path))
    restored = migrator.rollback()
    if restored is None:
        console.print("[yellow]No migration backups found.[/yellow]")
        raise typer.Exit(1)
    console.print(f"[green]Restored files from backup:[/green] {restored}")


def _relative(source: Path, base: Path) -> str:
    try:
        return str(source.relative_to(base))
    except ValueError:
        return str(source)
