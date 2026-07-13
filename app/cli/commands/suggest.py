from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, TaskID
from rich.table import Table

from app.cli.progress import add_task, make_ai_progress
from app.config import settings
from app.core.analyzer import Analyzer, Suggestion
from app.core.scanner import Scanner
from app.db.repository import Repository

app = typer.Typer(help="Suggest better dependency alternatives.")
console = Console()


@app.command()
def run(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
    package: str = typer.Option(None, "--package", "-P", help="Analyze a specific package."),
    max_packages: int = typer.Option(10, "--max", help="Max packages to analyze."),
    min_confidence: float = typer.Option(
        0.8, "--min-confidence", help="Minimum confidence to show a suggestion."
    ),
) -> None:
    """Ask the AI for better alternatives to project dependencies."""
    path = Path(project_path).resolve()
    if not path.is_dir():
        console.print(f"[red]Error:[/red] '{path}' is not a directory.")
        raise typer.Exit(1)

    result = Scanner(path, max_depth=settings.max_depth).scan()
    if not result.dependencies:
        console.print("[yellow]No dependencies found.[/yellow]")
        return

    try:
        analyzer = Analyzer(
            min_confidence=min_confidence, max_packages=max_packages
        )
    except Exception as exc:
        console.print(
            f"[red]Could not initialize the AI client:[/red] {exc}\n"
            "[dim]Set UPDATER_OPENAI_API_KEY (or configure .env) and retry.[/dim]"
        )
        raise typer.Exit(1) from exc

    if package:
        matches = [d for d in result.dependencies if d.name == package]
        if not matches:
            console.print(
                f"[red]Error:[/red] '{package}' is not a dependency of this project."
            )
            raise typer.Exit(1)
        dep = matches[0]
        with make_ai_progress() as progress:
            task = add_task(progress, f"[cyan]Analyzing[/cyan] {package}", total=1)
            suggestions = analyzer.analyze_package(
                dep.name, dep.version, dep.ecosystem or "python",
                progress=progress, task_id=task,
            )
            summary = _summarize(suggestions, [task], progress)
    else:
        unique = list({d.name for d in result.dependencies if not d.is_dev})
        total_to_analyze = min(max_packages, len(unique))
        with make_ai_progress() as progress:
            task = add_task(
                progress,
                "[cyan]Analyzing[/cyan] project dependencies",
                total=total_to_analyze,
            )
            suggestions = analyzer.analyze_project(
                result.dependencies, progress=progress, task_id=task
            )
            summary = _summarize(suggestions, [task], progress)

    console.print()
    if not suggestions:
        console.print("[green]No better alternatives suggested.[/green]")
        console.print(summary)
        return

    table = Table(title=f"Suggestions for {path.name}")
    table.add_column("Package", style="cyan")
    table.add_column("Current", style="magenta")
    table.add_column("Alternative", style="green")
    table.add_column("Version", style="blue")
    table.add_column("Confidence", justify="right")
    table.add_column("Reason", overflow="fold")

    for s in suggestions:
        table.add_row(
            s.package,
            s.current_version or "-",
            s.suggested_package,
            s.suggested_version or "-",
            f"{s.confidence:.0%}",
            s.reason,
        )
    console.print(table)
    console.print(summary)

    _save_suggestions(path, suggestions)


def _summarize(
    suggestions: list[Suggestion],
    task_ids: list[TaskID],
    progress: Progress,
) -> str:
    tasks = [progress.tasks[ti] for ti in task_ids]
    total_calls = sum(t.completed for t in tasks)
    return (
        f"[dim]Analyzed {int(total_calls)} packages · "
        f"{len(suggestions)} alternatives found · "
        f"avg {sum(t.finished_time or 0 for t in tasks) / max(len(tasks), 1):.1f}s[/dim]"
    )


def _save_suggestions(path: Path, suggestions: list[Suggestion]) -> None:
    try:
        repo = Repository(settings.db_path)
        project = repo.get_or_create_project(path)
        for suggestion in suggestions:
            repo.save_suggestion(project.id, suggestion.to_dict())
    except Exception as exc:
        console.print(f"[dim]Could not save suggestions: {exc}[/dim]")
