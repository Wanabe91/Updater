from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def make_project(tmp_path: Path) -> Callable[..., Path]:
    """Factory: create a temporary project with given files."""

    def _make(files: dict[str, str]) -> Path:
        for rel_path, content in files.items():
            file_path = tmp_path / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        return tmp_path

    return _make
