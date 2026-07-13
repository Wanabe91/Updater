from __future__ import annotations

import json

from app.ai.client import AIResponse
from app.core.analyzer import Analyzer
from app.parsers.base import Dependency


class StubAIClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses
        self.calls: list[str] = []

    def suggest_alternative(
        self, package: str, version: str, ecosystem: str
    ) -> AIResponse:
        self.calls.append(package)
        content = self._responses.get(package)
        if content is None:
            return AIResponse(content="", model="stub", success=False, error="boom")
        return AIResponse(content=content, model="stub")


def _alternatives_json(*alts: dict) -> str:
    return json.dumps({"alternatives": list(alts)})


class TestAnalyzePackage:
    def test_parses_and_sorts_by_confidence(self) -> None:
        client = StubAIClient(
            {
                "requests": _alternatives_json(
                    {
                        "name": "httpx",
                        "version": "0.28.0",
                        "reason": "async",
                        "confidence": 0.9,
                    },
                    {
                        "name": "aiohttp",
                        "version": "3.9.0",
                        "reason": "server too",
                        "confidence": 0.7,
                    },
                )
            }
        )
        analyzer = Analyzer(ai_client=client, min_confidence=0.5)
        suggestions = analyzer.analyze_package("requests", "2.31.0")
        assert [s.suggested_package for s in suggestions] == ["httpx", "aiohttp"]
        assert suggestions[0].package == "requests"
        assert suggestions[0].confidence == 0.9

    def test_filters_low_confidence(self) -> None:
        client = StubAIClient(
            {
                "requests": _alternatives_json(
                    {"name": "httpx", "confidence": 0.3},
                    {"name": "aiohttp", "confidence": 0.8},
                )
            }
        )
        analyzer = Analyzer(ai_client=client, min_confidence=0.5)
        suggestions = analyzer.analyze_package("requests", "2.31.0")
        assert [s.suggested_package for s in suggestions] == ["aiohttp"]

    def test_skips_self_suggestion(self) -> None:
        client = StubAIClient(
            {"requests": _alternatives_json({"name": "Requests", "confidence": 0.9})}
        )
        analyzer = Analyzer(ai_client=client)
        assert analyzer.analyze_package("requests", "2.31.0") == []

    def test_failed_response(self) -> None:
        analyzer = Analyzer(ai_client=StubAIClient({}))
        assert analyzer.analyze_package("requests", "2.31.0") == []

    def test_invalid_json(self) -> None:
        client = StubAIClient({"requests": "sorry, no JSON here"})
        analyzer = Analyzer(ai_client=client)
        assert analyzer.analyze_package("requests", "2.31.0") == []

    def test_invalid_confidence_treated_as_zero(self) -> None:
        client = StubAIClient(
            {"requests": _alternatives_json({"name": "httpx", "confidence": "high"})}
        )
        analyzer = Analyzer(ai_client=client, min_confidence=0.5)
        assert analyzer.analyze_package("requests", "2.31.0") == []


class TestAnalyzeProject:
    def test_skips_dev_and_duplicates(self) -> None:
        client = StubAIClient(
            {
                "requests": _alternatives_json({"name": "httpx", "confidence": 0.9}),
                "pytest": _alternatives_json({"name": "nose", "confidence": 0.9}),
            }
        )
        analyzer = Analyzer(ai_client=client)
        deps = [
            Dependency(name="requests", version="2.31.0", ecosystem="python"),
            Dependency(name="requests", version="2.31.0", ecosystem="python"),
            Dependency(name="pytest", version="8.0.0", is_dev=True, ecosystem="python"),
        ]
        suggestions = analyzer.analyze_project(deps)
        assert client.calls == ["requests"]
        assert [s.suggested_package for s in suggestions] == ["httpx"]

    def test_respects_max_packages(self) -> None:
        client = StubAIClient(
            {
                "a": _alternatives_json({"name": "x", "confidence": 0.9}),
                "b": _alternatives_json({"name": "y", "confidence": 0.9}),
            }
        )
        analyzer = Analyzer(ai_client=client, max_packages=1)
        deps = [
            Dependency(name="a", version="1.0", ecosystem="python"),
            Dependency(name="b", version="1.0", ecosystem="python"),
        ]
        analyzer.analyze_project(deps)
        assert client.calls == ["a"]


class FakeTask:
    def __init__(self) -> None:
        self.description = ""
        self.completed = 0.0
        self.total: float | None = None


class FakeProgress:
    def __init__(self) -> None:
        self.tasks: dict[int, FakeTask] = {}
        self.updates: list[tuple] = []

    def update(self, task_id: int, **fields) -> None:
        self.updates.append((task_id, fields))
        task = self.tasks.setdefault(task_id, FakeTask())
        if "description" in fields:
            task.description = fields["description"]
        if "total" in fields:
            task.total = fields["total"]
        if "advance" in fields:
            task.completed += fields["advance"]


class TestAnalyzePackageProgress:
    def test_progress_advances_once_per_call(self) -> None:
        client = StubAIClient(
            {"requests": _alternatives_json({"name": "httpx", "confidence": 0.9})}
        )
        analyzer = Analyzer(ai_client=client, min_confidence=0.5)
        progress = FakeProgress()
        task_id = 1
        progress.tasks[task_id] = FakeTask()

        analyzer.analyze_package(
            "requests", "2.31.0", progress=progress, task_id=task_id
        )

        advances = [u[1].get("advance", 0) for u in progress.updates]
        assert sum(advances) == 1
        assert progress.tasks[task_id].completed == 1

    def test_progress_marks_failed_request(self) -> None:
        analyzer = Analyzer(ai_client=StubAIClient({}), min_confidence=0.5)
        progress = FakeProgress()
        task_id = 1
        progress.tasks[task_id] = FakeTask()

        analyzer.analyze_package(
            "requests", "2.31.0", progress=progress, task_id=task_id
        )

        descriptions = [u[1].get("description", "") for u in progress.updates]
        assert any("failed" in d for d in descriptions)


class TestAnalyzeProjectProgress:
    def test_progress_advances_for_each_unique_non_dev_package(self) -> None:
        client = StubAIClient(
            {
                "requests": _alternatives_json({"name": "httpx", "confidence": 0.9}),
                "flask": _alternatives_json({"name": "fastapi", "confidence": 0.9}),
            }
        )
        analyzer = Analyzer(ai_client=client, min_confidence=0.5, max_packages=10)
        deps = [
            Dependency(name="requests", version="2.31.0", ecosystem="python"),
            Dependency(name="requests", version="2.31.0", ecosystem="python"),
            Dependency(name="flask", version="3.0.0", ecosystem="python"),
            Dependency(name="pytest", version="8.0.0", is_dev=True, ecosystem="python"),
        ]
        progress = FakeProgress()
        task_id = 1
        progress.tasks[task_id] = FakeTask()

        analyzer.analyze_project(deps, progress=progress, task_id=task_id)

        advances = [u[1].get("advance", 0) for u in progress.updates]
        assert sum(advances) == 2
        assert client.calls == ["requests", "flask"]
