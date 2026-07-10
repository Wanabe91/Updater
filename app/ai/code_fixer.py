from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.ai.client import AIClient


@dataclass
class CodePatch:
    file_path: Path
    old_code: str
    new_code: str
    description: str = ""


class CodeFixer:
    def __init__(self, ai_client: AIClient) -> None:
        self.ai_client = ai_client

    def fix_imports(
        self,
        file_path: Path,
        old_package: str,
        new_package: str,
    ) -> Optional[CodePatch]:
        raise NotImplementedError

    def fix_api_usage(
        self,
        file_path: Path,
        old_package: str,
        old_version: str,
        new_package: str,
        new_version: str,
    ) -> list[CodePatch]:
        raise NotImplementedError

    def generate_patches(
        self,
        project_path: Path,
        old_package: str,
        new_package: str,
    ) -> list[CodePatch]:
        raise NotImplementedError