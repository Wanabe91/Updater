from __future__ import annotations

from pathlib import Path

from app.core.scanner import Scanner


class TestScan:
    def test_finds_requirements(self, make_project) -> None:  # type: ignore[no-untyped-def]
        project = make_project(
            {"requirements.txt": "requests==2.31.0\ndjango>=4.0\n"}
        )
        result = Scanner(project).scan()
        names = [d.name for d in result.dependencies]
        assert "requests" in names
        assert "django" in names
        assert "python" in result.parsers_used

    def test_finds_nested_files(self, make_project) -> None:  # type: ignore[no-untyped-def]
        project = make_project(
            {"requirements.txt": "requests==2.31.0\n", "sub/requirements.txt": "flask\n"}
        )
        result = Scanner(project).scan()
        names = [d.name for d in result.dependencies]
        assert "flask" in names

    def test_finds_pyproject(self, make_project) -> None:  # type: ignore[no-untyped-def]
        project = make_project(
            {"pyproject.toml": '[project]\ndependencies = ["typer>=0.12"]\n'}
        )
        result = Scanner(project).scan()
        names = [d.name for d in result.dependencies]
        assert "typer" in names

    def test_skips_venv(self, make_project) -> None:  # type: ignore[no-untyped-def]
        project = make_project(
            {
                "requirements.txt": "requests==2.31.0\n",
                "venv/requirements.txt": "hidden==1.0.0\n",
            }
        )
        result = Scanner(project).scan()
        names = [d.name for d in result.dependencies]
        assert "hidden" not in names
        assert "requests" in names

    def test_skips_hidden_dirs(self, make_project) -> None:  # type: ignore[no-untyped-def]
        project = make_project(
            {
                "requirements.txt": "requests==2.31.0\n",
                ".hidden/requirements.txt": "secret==1.0.0\n",
            }
        )
        result = Scanner(project).scan()
        names = [d.name for d in result.dependencies]
        assert "secret" not in names

    def test_empty_project(self, tmp_path: Path) -> None:
        result = Scanner(tmp_path).scan()
        assert result.dependencies == []
        assert result.errors == []

    def test_max_depth(self, make_project) -> None:  # type: ignore[no-untyped-def]
        project = make_project(
            {
                "requirements.txt": "top==1.0.0\n",
                "a/b/c/requirements.txt": "deep==1.0.0\n",
            }
        )
        result = Scanner(project, max_depth=2).scan()
        names = [d.name for d in result.dependencies]
        assert "top" in names
        assert "deep" not in names

    def test_dependency_fields(self, make_project) -> None:  # type: ignore[no-untyped-def]
        project = make_project({"requirements.txt": "requests==2.31.0\n"})
        result = Scanner(project).scan()
        dep = result.dependencies[0]
        assert dep.ecosystem == "python"
        assert set(dep.to_dict().keys()) == {
            "name",
            "version",
            "version_specifier",
            "is_dev",
            "source",
            "ecosystem",
        }

    def test_collects_errors(self, make_project) -> None:  # type: ignore[no-untyped-def]
        project = make_project({"requirements.txt": "not valid {{{ toml"})
        result = Scanner(project).scan()
        assert len(result.dependencies) == 1  # the line still parses as a name
