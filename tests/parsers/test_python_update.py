from __future__ import annotations

from pathlib import Path

import pytest

from app.parsers.python import PythonParser


@pytest.fixture
def parser() -> PythonParser:
    return PythonParser()


class TestUpdateRequirements:
    def test_updates_pinned_version(self, parser: PythonParser) -> None:
        content = "requests==1.0.0\nflask==2.0.0\n"
        new, changed = parser.update_versions(
            Path("requirements.txt"), content, {"requests": "2.31.0"}
        )
        assert new == "requests==2.31.0\nflask==2.0.0\n"
        assert changed == ["requests"]

    def test_preserves_comments_and_markers(self, parser: PythonParser) -> None:
        content = (
            "# main deps\n"
            'requests==1.0.0 ; python_version >= "3.8"  # http client\n'
        )
        new, changed = parser.update_versions(
            Path("requirements.txt"), content, {"requests": "2.0.0"}
        )
        assert (
            'requests==2.0.0 ; python_version >= "3.8"  # http client' in new
        )
        assert "# main deps" in new
        assert changed == ["requests"]

    def test_preserves_extras_and_specifier(self, parser: PythonParser) -> None:
        content = "uvicorn[standard]>=0.20.0\n"
        new, changed = parser.update_versions(
            Path("requirements.txt"), content, {"uvicorn": "0.30.0"}
        )
        assert new == "uvicorn[standard]>=0.30.0\n"
        assert changed == ["uvicorn"]

    def test_unknown_package_untouched(self, parser: PythonParser) -> None:
        content = "requests==1.0.0\n"
        new, changed = parser.update_versions(
            Path("requirements.txt"), content, {"flask": "3.0.0"}
        )
        assert new == content
        assert changed == []

    def test_unpinned_line_untouched(self, parser: PythonParser) -> None:
        content = "requests\n"
        new, changed = parser.update_versions(
            Path("requirements.txt"), content, {"requests": "2.0.0"}
        )
        assert new == content
        assert changed == []


class TestUpdatePyproject:
    def test_pep621_dependencies(self, parser: PythonParser) -> None:
        content = (
            "[project]\n"
            'name = "demo"\n'
            "dependencies = [\n"
            '    "typer>=0.12.0",\n'
            '    "rich>=13.0.0",  # console\n'
            "]\n"
        )
        new, changed = parser.update_versions(
            Path("pyproject.toml"), content, {"typer": "0.26.0"}
        )
        assert '"typer>=0.26.0"' in new
        assert '"rich>=13.0.0"' in new
        assert "# console" in new
        assert changed == ["typer"]

    def test_optional_dependencies(self, parser: PythonParser) -> None:
        content = (
            "[project]\n"
            'name = "demo"\n'
            "[project.optional-dependencies]\n"
            'dev = ["pytest>=8.0.0"]\n'
        )
        new, changed = parser.update_versions(
            Path("pyproject.toml"), content, {"pytest": "9.0.0"}
        )
        assert '"pytest>=9.0.0"' in new
        assert changed == ["pytest"]

    def test_poetry_keeps_caret(self, parser: PythonParser) -> None:
        content = (
            "[tool.poetry.dependencies]\n"
            'python = "^3.11"\n'
            'requests = "^2.28.0"\n'
        )
        new, changed = parser.update_versions(
            Path("pyproject.toml"), content, {"requests": "2.31.0", "python": "9.9"}
        )
        assert 'requests = "^2.31.0"' in new
        assert 'python = "^3.11"' in new
        assert changed == ["requests"]

    def test_poetry_dict_spec(self, parser: PythonParser) -> None:
        content = (
            "[tool.poetry.dependencies]\n"
            'uvicorn = { version = ">=0.20.0", extras = ["standard"] }\n'
        )
        new, changed = parser.update_versions(
            Path("pyproject.toml"), content, {"uvicorn": "0.30.0"}
        )
        assert '">=0.30.0"' in new
        assert "standard" in new
        assert changed == ["uvicorn"]

    def test_unsupported_file_raises(self, parser: PythonParser) -> None:
        with pytest.raises(NotImplementedError):
            parser.update_versions(Path("Pipfile"), "", {"a": "1.0"})

    def test_supports_update(self, parser: PythonParser) -> None:
        assert parser.supports_update(Path("requirements.txt"))
        assert parser.supports_update(Path("pyproject.toml"))
        assert not parser.supports_update(Path("Pipfile"))
        assert not parser.supports_update(Path("setup.cfg"))
