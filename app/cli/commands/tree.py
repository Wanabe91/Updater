import typer

app = typer.Typer(help="Display dependency tree.")


@app.command()
def show(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
    depth: int = typer.Option(None, "--depth", "-d", help="Max depth of the tree."),
    package: str = typer.Option(None, "--filter", "-f", help="Show tree for a specific package."),
    outdated: bool = typer.Option(False, "--outdated", help="Highlight outdated packages."),
) -> None:
    pass