from pathlib import Path

import typer
from rich.console import Console

from app.cli.commands.history import app as history_app
from app.cli.commands.migrate import app as migrate_app
from app.cli.commands.scan import app as scan_app
from app.cli.commands.suggest import app as suggest_app
from app.cli.commands.tree import app as tree_app
from app.cli.commands.update import app as update_app

app = typer.Typer(
    name="updater",
    help="AI-powered dependency updater with code migration.",
    no_args_is_help=True,
)
console = Console()

app.add_typer(scan_app, name="scan")
app.add_typer(update_app, name="update")
app.add_typer(suggest_app, name="suggest")
app.add_typer(migrate_app, name="migrate")
app.add_typer(history_app, name="history")
app.add_typer(tree_app, name="tree")


@app.callback()
def main(
    project_path: Path | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to the project directory.",
        exists=True,
    ),
) -> None:
    pass


if __name__ == "__main__":
    app()
