import typer

app = typer.Typer(help="Scan project for dependencies.")


@app.command()
def run(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
) -> None:
    pass


@app.command()
def list_parsers() -> None:
    pass