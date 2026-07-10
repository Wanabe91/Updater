import typer

app = typer.Typer(help="View dependency change history.")


@app.command()
def log(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of entries to show."),
) -> None:
    pass


@app.command()
def diff(
    revision: str = typer.Argument(..., help="Revision to compare."),
) -> None:
    pass