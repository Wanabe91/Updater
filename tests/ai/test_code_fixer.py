from __future__ import annotations

from pathlib import Path

from app.ai.client import AIResponse
from app.ai.code_fixer import CodeFixer, _strip_code_fences


class StubClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    def chat(self, messages: list[dict], temperature: float = 0.2) -> AIResponse:
        self.calls.append(messages)
        return AIResponse(content=self._responses.pop(0), model="stub")


class TestStripCodeFences:
    def test_plain_text_unchanged(self) -> None:
        assert _strip_code_fences("import os\n") == "import os"

    def test_fenced_block(self) -> None:
        assert _strip_code_fences("```python\nimport os\n```") == "import os"

    def test_fence_without_language(self) -> None:
        assert _strip_code_fences("```\nimport os\n```") == "import os"

    def test_unclosed_fence(self) -> None:
        assert _strip_code_fences("```python\nimport os") == "import os"


class TestFixImports:
    def test_strips_fences_from_response(self, tmp_path: Path) -> None:
        target = tmp_path / "main.py"
        target.write_text("import old_pkg\n", encoding="utf-8")
        client = StubClient(["```python\nimport new_pkg\n```"])

        patch = CodeFixer(client).fix_imports(target, "old_pkg", "new_pkg")

        assert patch is not None
        assert patch.new_code == "import new_pkg\n"

    def test_no_change_returns_none(self, tmp_path: Path) -> None:
        target = tmp_path / "main.py"
        target.write_text("import old_pkg\n", encoding="utf-8")
        client = StubClient(["import old_pkg\n"])

        patch = CodeFixer(client).fix_imports(target, "old_pkg", "new_pkg")

        assert patch is None


class TestFixApiUsage:
    def test_breaking_changes_list_joined(self, tmp_path: Path) -> None:
        target = tmp_path / "main.py"
        target.write_text("old_pkg.call()\n", encoding="utf-8")
        client = StubClient(
            [
                '{"migrated_code": "new_pkg.call()",'
                ' "breaking_changes": ["renamed", "new signature"]}'
            ]
        )

        patches = CodeFixer(client).fix_api_usage(
            target, "old_pkg", "1.0", "new_pkg", "2.0"
        )

        assert len(patches) == 1
        assert patches[0].new_code == "new_pkg.call()"
        assert patches[0].description == "renamed; new signature"

    def test_invalid_json_returns_empty(self, tmp_path: Path) -> None:
        target = tmp_path / "main.py"
        target.write_text("old_pkg.call()\n", encoding="utf-8")
        client = StubClient(["not json at all"])

        patches = CodeFixer(client).fix_api_usage(
            target, "old_pkg", "1.0", "new_pkg", "2.0"
        )

        assert patches == []


class TestGeneratePatches:
    def test_api_fix_uses_import_patched_source(self, tmp_path: Path) -> None:
        target = tmp_path / "main.py"
        target.write_text("import old_pkg\nold_pkg.call()\n", encoding="utf-8")
        client = StubClient(
            [
                "import new_pkg\nold_pkg.call()\n",
                '{"migrated_code": "import new_pkg\\nnew_pkg.call()\\n",'
                ' "breaking_changes": []}',
            ]
        )

        patches = CodeFixer(client).generate_patches(tmp_path, "old_pkg", "new_pkg")

        assert len(patches) == 2
        assert patches[1].old_code == "import new_pkg\nold_pkg.call()\n"
        assert "old_pkg" in client.calls[1][1]["content"]

    def test_skips_files_without_package(self, tmp_path: Path) -> None:
        (tmp_path / "unrelated.py").write_text("print('hi')\n", encoding="utf-8")
        client = StubClient([])

        patches = CodeFixer(client).generate_patches(tmp_path, "old_pkg", "new_pkg")

        assert patches == []
        assert client.calls == []


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
        if "completed" in fields:
            task.completed = fields["completed"]
        if "advance" in fields:
            task.completed += fields["advance"]


class TestGeneratePatchesProgress:
    def test_progress_updates_describe_each_stage(self, tmp_path: Path) -> None:
        target = tmp_path / "main.py"
        target.write_text("import old_pkg\nold_pkg.call()\n", encoding="utf-8")
        client = StubClient(
            [
                "import new_pkg\nold_pkg.call()\n",
                '{"migrated_code": "import new_pkg\\nnew_pkg.call()\\n",'
                ' "breaking_changes": []}',
            ]
        )
        progress = FakeProgress()
        task_id = 1
        progress.tasks[task_id] = FakeTask()

        CodeFixer(client).generate_patches(
            tmp_path, "old_pkg", "new_pkg",
            progress=progress, task_id=task_id,
        )

        descriptions = [u[1].get("description", "") for u in progress.updates]
        assert any("Scanning" in d for d in descriptions)
        assert any("Migrating" in d for d in descriptions)
        assert any("main.py" in d and "imports" in d for d in descriptions)
        assert any("main.py" in d and "API" in d for d in descriptions)

    def test_progress_total_set_to_matching_file_count(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("import old_pkg\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("import old_pkg\n", encoding="utf-8")
        (tmp_path / "skip.py").write_text("print('no')\n", encoding="utf-8")
        client = StubClient(
            [
                "import new_pkg\n",
                '{"migrated_code": "import new_pkg\\n", "breaking_changes": []}',
                "import new_pkg\n",
                '{"migrated_code": "import new_pkg\\n", "breaking_changes": []}',
            ]
        )
        progress = FakeProgress()
        task_id = 1
        progress.tasks[task_id] = FakeTask()

        CodeFixer(client).generate_patches(
            tmp_path, "old_pkg", "new_pkg",
            progress=progress, task_id=task_id,
        )

        total_updates = [u[1] for u in progress.updates if "total" in u[1]]
        assert total_updates, "expected a total update after scanning"
        assert total_updates[-1]["total"] == 2
