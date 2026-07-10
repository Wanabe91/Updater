import typer

app = typer.Typer(help="Migrate code to new dependency APIs.")


@app.command()
def run(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
    package: str = typer.Option(None, "--package", "-P", help="Migrate a specific package."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying."),
) -> None:
    pass


@app.command()
def rollback() -> None:
    pass