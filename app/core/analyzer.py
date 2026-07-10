from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Suggestion:
    package: str
    current_version: str
    suggested_package: str
    suggested_version: str
    reason: str
    confidence: float = 0.0


class Analyzer:
    def __init__(self) -> None:
        pass

    def analyze_package(self, package: str, version: str) -> Optional[Suggestion]:
        raise NotImplementedError

    def analyze_project(self, dependencies: list[dict]) -> list[Suggestion]:
        raise NotImplementedError