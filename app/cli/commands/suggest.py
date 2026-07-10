import typer

app = typer.Typer(help="Suggest better dependency alternatives.")


@app.command()
def run(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
    package: str = typer.Option(None, "--package", "-P", help="Analyze a specific package."),
) -> None:
    pass