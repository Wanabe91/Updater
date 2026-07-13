from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.ai.client import AIClient, extract_json
from app.parsers.base import Dependency

if TYPE_CHECKING:
    from rich.progress import Progress, TaskID

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    package: str
    current_version: str
    suggested_package: str
    suggested_version: str
    reason: str
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "original_package": self.package,
            "suggested_package": self.suggested_package,
            "reason": self.reason,
            "confidence": self.confidence,
        }


class Analyzer:
    def __init__(
        self,
        ai_client: AIClient | None = None,
        min_confidence: float = 0.8,
        max_packages: int = 10,
    ) -> None:
        self._client = ai_client or AIClient()
        self._min_confidence = min_confidence
        self._max_packages = max_packages

    def analyze_package(
        self,
        package: str,
        version: str,
        ecosystem: str = "python",
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> list[Suggestion]:
        if progress is not None and task_id is not None:
            progress.update(
                task_id,
                description=f"[cyan]Analyzing[/cyan] {package}",
                tokens="",
                elapsed="",
            )
        response = self._client.suggest_alternative(package, version, ecosystem)
        tokens = response.total_tokens
        elapsed_str = f"{response.elapsed:.1f}s"
        if not response.success:
            logger.warning(
                "Suggestion request failed for %s: %s", package, response.error
            )
            if progress is not None and task_id is not None:
                progress.update(
                    task_id,
                    description=f"[red]failed[/red] {package} — {response.error}",
                    tokens=f"{tokens} tok" if tokens else "",
                    elapsed=elapsed_str,
                    advance=1,
                )
            return []

        try:
            data = json.loads(extract_json(response.content))
        except ValueError:
            logger.warning("Unparseable suggestion response for %s", package)
            if progress is not None and task_id is not None:
                progress.update(
                    task_id,
                    description=f"[yellow]bad JSON[/yellow] {package}",
                    tokens=f"{tokens} tok" if tokens else "",
                    elapsed=elapsed_str,
                    advance=1,
                )
            return []

        suggestions: list[Suggestion] = []
        for alt in data.get("alternatives", []):
            if not isinstance(alt, dict):
                continue
            name = str(alt.get("name", "")).strip()
            if not name or name.lower() == package.lower():
                continue
            try:
                confidence = float(alt.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            if confidence < self._min_confidence:
                continue
            suggestions.append(
                Suggestion(
                    package=package,
                    current_version=version,
                    suggested_package=name,
                    suggested_version=str(alt.get("version", "")),
                    reason=str(alt.get("reason", "")),
                    confidence=confidence,
                )
            )
        suggestions.sort(key=lambda s: s.confidence, reverse=True)

        if progress is not None and task_id is not None:
            progress.update(
                task_id,
                description=(
                    f"[green]{package}[/green] — "
                    f"{len(suggestions)} alt"
                    f"{f' · {tokens} tok' if tokens else ''} · {elapsed_str}"
                ),
                tokens=f"{tokens} tok" if tokens else "",
                elapsed=elapsed_str,
                advance=1,
            )
        return suggestions

    def analyze_project(
        self,
        dependencies: list[Dependency],
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> list[Suggestion]:
        suggestions: list[Suggestion] = []
        seen: set[str] = set()
        for dep in dependencies:
            if dep.is_dev or dep.name in seen:
                continue
            if len(seen) >= self._max_packages:
                logger.info(
                    "Package limit (%d) reached, skipping the rest",
                    self._max_packages,
                )
                break
            seen.add(dep.name)
            suggestions.extend(
                self.analyze_package(
                    dep.name,
                    dep.version,
                    dep.ecosystem or "python",
                    progress=progress,
                    task_id=task_id,
                )
            )
        return suggestions
