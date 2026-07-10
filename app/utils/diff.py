from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DiffResult:
    file_path: Path
    hunks: list[dict]
    has_changes: bool = False


def compute_diff(original: str, modified: str, file_path: Path = Path()) -> DiffResult:
    raise NotImplementedError


def apply_patch(content: str, patch: str) -> str:
    raise NotImplementedError


def create_unified_diff(original: str, modified: str, file_path: str = "") -> str:
    raise NotImplementedError