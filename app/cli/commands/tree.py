from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from app.config import settings
from app.core.dependency_tree import TreeBuilder, TreeRenderer
from app.db.repository import Repository

app = typer.Typer(help="Display dependency tree.")
console = Console()


@app.command()
def show(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
    depth: int = typer.Option(3, "--depth", "-d", help="Max depth of the tree."),
    package: str = typer.Option(None, "--filter", "-f", help="Show tree for a specific package."),
    outdated: bool = typer.Option(False, "--outdated", help="Highlight outdated packages."),
) -> None:
    """Show the transitive dependency tree (resolved via PyPI metadata)."""
    path = Path(project_path).resolve()
    if not path.is_dir():
        console.print(f"[red]Error:[/red] '{path}' is not a directory.")
        raise typer.Exit(1)

    builder = TreeBuilder(path, scan_max_depth=settings.max_depth)
    with console.status("Resolving dependency tree via PyPI..."):
        tree = builder.build(depth=depth, package=package)

    if not tree.children:
        message = (
            f"'{package}' is not a dependency of this project."
            if package
            else "No Python dependencies found."
        )
        console.print(f"[yellow]{message}[/yellow]")
        raise typer.Exit(1 if package else 0)

    console.print(TreeRenderer().render(tree, show_outdated=outdated))
    console.print(f"\n[dim]{len(tree.flatten())} packages in the tree.[/dim]")

    _save_tree(path, tree.to_dict())


def _save_tree(path: Path, tree_data: dict) -> None:
    try:
        repo = Repository(settings.db_path)
        project = repo.get_or_create_project(path)
        repo.save_tree(project.id, tree_data)
    except Exception as exc:
        console.print(f"[dim]Could not save tree: {exc}[/dim]")
