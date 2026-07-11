from __future__ import annotations

from rich.console import Console


def print_unified_diff(console: Console, diff_text: str) -> None:
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            console.print(f"[green]{line}[/green]", highlight=False)
        elif line.startswith("-") and not line.startswith("---"):
            console.print(f"[red]{line}[/red]", highlight=False)
        else:
            console.print(f"[dim]{line}[/dim]", highlight=False)
    console.print()
