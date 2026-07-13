from __future__ import annotations

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from app.cli.progress import add_task, make_ai_progress, make_registry_progress


class TestMakeAiProgress:
    def test_returns_progress_instance(self) -> None:
        progress = make_ai_progress()
        assert isinstance(progress, Progress)

    def test_has_token_and_elapsed_columns(self) -> None:
        progress = make_ai_progress()
        column_types = {type(c) for c in progress.columns}
        assert SpinnerColumn in column_types
        assert BarColumn in column_types
        assert MofNCompleteColumn in column_types
        assert TextColumn in column_types
        assert TimeElapsedColumn in column_types


class TestMakeRegistryProgress:
    def test_returns_progress_without_token_columns(self) -> None:
        progress = make_registry_progress()
        assert isinstance(progress, Progress)
        column_types = {type(c) for c in progress.columns}
        assert SpinnerColumn in column_types
        assert MofNCompleteColumn in column_types
        assert TimeElapsedColumn in column_types


class TestAddTask:
    def test_creates_task_with_token_and_elapsed_fields(self) -> None:
        progress = make_ai_progress()
        task_id = add_task(progress, "Working", total=5)
        task = progress.tasks[task_id]
        assert task.total == 5
        assert task.fields.get("tokens") == ""
        assert task.fields.get("elapsed") == ""

    def test_supports_indeterminate_total(self) -> None:
        progress = make_ai_progress()
        task_id = add_task(progress, "Scanning")
        task = progress.tasks[task_id]
        assert task.total is None
