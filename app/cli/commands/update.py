import typer

app = typer.Typer(help="Update project dependencies.")


@app.command()
def check(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
) -> None:
    pass


@app.command()
def apply(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying."),
) -> None:
    pass


@app.command()
def rollback(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
) -> None:
    pass