from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DiffResult:
    file_path: Path
    diff_text: str
    has_changes: bool = False


def create_unified_diff(original: str, modified: str, file_path: str = "") -> str:
    label = file_path or "file"
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=f"a/{label}",
            tofile=f"b/{label}",
        )
    )


def compute_diff(original: str, modified: str, file_path: Path = Path()) -> DiffResult:
    diff_text = create_unified_diff(original, modified, str(file_path))
    return DiffResult(
        file_path=file_path,
        diff_text=diff_text,
        has_changes=bool(diff_text),
    )
