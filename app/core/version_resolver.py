from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ResolvedVersion:
    package: str
    current: str
    latest: str
    latest_compatible: str
    is_prerelease: bool = False


class VersionResolver:
    def __init__(self) -> None:
        pass

    def resolve(self, package: str, current_version: str) -> Optional[ResolvedVersion]:
        raise NotImplementedError

    def resolve_batch(self, packages: list[dict]) -> list[ResolvedVersion]:
        raise NotImplementedError