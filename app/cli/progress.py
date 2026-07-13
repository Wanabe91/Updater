from __future__ import annotations

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)


def make_ai_progress() -> Progress:
    """Progress bar with per-step description, tokens and elapsed time."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[tokens]}[/dim]"),
        TextColumn("[dim]{task.fields[elapsed]}[/dim]"),
        TimeElapsedColumn(),
        transient=True,
    )


def make_registry_progress() -> Progress:
    """Progress bar for registry resolution (no tokens column)."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        transient=True,
    )


def add_task(
    progress: Progress,
    description: str,
    total: float | None = None,
) -> TaskID:
    """Add a task with the standard token/elapsed fields pre-filled."""
    return progress.add_task(
        description,
        total=total,
        tokens="",
        elapsed="",
    )
