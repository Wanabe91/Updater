from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from app.core.scanner import Scanner
from app.parsers import get_all_parsers

app = typer.Typer(help="Scan project for dependencies.")
console = Console()


@app.command()
def run(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
) -> None:
    """Scan a project for dependencies."""
    path = Path(project_path).resolve()
    if not path.is_dir():
        console.print(f"[red]Error:[/red] '{path}' is not a directory.")
        raise typer.Exit(1)

    scanner = Scanner(path)
    result = scanner.scan()

    if not result.dependencies:
        console.print("[yellow]No dependencies found.[/yellow]")
        return

    table = Table(title=f"Dependencies in {path.name}")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Version", style="magenta")
    table.add_column("Specifier", style="green")
    table.add_column("Dev", justify="center")
    table.add_column("Ecosystem", style="blue")
    table.add_column("Source", style="dim", overflow="fold")

    for dep in sorted(result.dependencies, key=lambda d: (d["ecosystem"], d["name"])):
        try:
            source_display = str(Path(dep["source"]).relative_to(path))
        except (ValueError, KeyError, TypeError):
            source_display = dep.get("source", "")

        table.add_row(
            dep["name"],
            dep["version"],
            dep["version_specifier"],
            "[green]yes[/green]" if dep["is_dev"] else "",
            dep["ecosystem"],
            source_display,
        )

    console.print(table)
    console.print(
        f"\n[bold]{len(result.dependencies)}[/bold] dependencies found "
        f"using parsers: [bold]{', '.join(result.parsers_used)}[/bold]"
    )
    if result.errors:
        console.print(f"[red]Errors ({len(result.errors)}):[/red]")
        for err in result.errors:
            console.print(f"  [red]-[/red] {err}")


@app.command(name="list-parsers")
def list_parsers() -> None:
    """List all available dependency parsers."""
    table = Table(title="Available Parsers")
    table.add_column("Name", style="cyan")
    table.add_column("File Patterns", style="green")

    for parser in get_all_parsers():
        table.add_row(parser.name, ", ".join(parser.file_patterns))

    console.print(table)
