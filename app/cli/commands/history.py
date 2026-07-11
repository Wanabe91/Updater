from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from app.config import settings
from app.db.repository import Repository

app = typer.Typer(help="View dependency change history.")
console = Console()


@app.command()
def log(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of entries to show."),
) -> None:
    """Show the update history for a project."""
    path = Path(project_path).resolve()
    repo = Repository(settings.db_path)
    project = repo.get_project(path)
    if project is None:
        console.print(
            f"[yellow]No history for '{path}'. Run a scan or update first.[/yellow]"
        )
        return

    entries = repo.get_update_history(project.id, limit=limit)
    if not entries:
        console.print("[yellow]No updates recorded yet.[/yellow]")
        return

    table = Table(title=f"Update history for {project.name}")
    table.add_column("Date", style="dim")
    table.add_column("Action", style="blue")
    table.add_column("Package", style="cyan")
    table.add_column("From", style="magenta")
    table.add_column("To", style="green")
    table.add_column("Result", justify="center")

    for entry in entries:
        table.add_row(
            entry.created_at.strftime("%Y-%m-%d %H:%M"),
            entry.action,
            entry.package_name,
            entry.old_version or "-",
            entry.new_version or "-",
            "[green]ok[/green]" if entry.success else "[red]failed[/red]",
        )

    console.print(table)


@app.command()
def deps(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
) -> None:
    """Show the last saved dependency snapshot."""
    path = Path(project_path).resolve()
    repo = Repository(settings.db_path)
    project = repo.get_project(path)
    if project is None:
        console.print(f"[yellow]No snapshot for '{path}'. Run a scan first.[/yellow]")
        return

    records = repo.get_dependencies(project.id)
    if not records:
        console.print("[yellow]Snapshot is empty.[/yellow]")
        return

    table = Table(title=f"Last snapshot for {project.name}")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="magenta")
    table.add_column("Latest", style="blue")
    table.add_column("Ecosystem", style="green")
    table.add_column("Scanned", style="dim")

    for rec in records:
        table.add_row(
            rec.name,
            rec.version or "-",
            rec.latest_version or "-",
            rec.ecosystem,
            rec.scanned_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)
