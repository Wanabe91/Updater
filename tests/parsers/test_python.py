from __future__ import annotations

from pathlib import Path

from app.parsers.python import PythonParser


def _parse_file(tmp_path: Path, filename: str, content: str):
    file_path = tmp_path / filename
    file_path.write_text(content, encoding="utf-8")
    return PythonParser().parse(file_path)


class TestRequirementsTxt:
    def test_simple_pinned(self, tmp_path: Path) -> None:
        result = _parse_file(tmp_path, "requirements.txt", "requests==2.31.0\n")
        assert len(result.dependencies) == 1
        dep = result.dependencies[0]
        assert dep.name == "requests"
        assert dep.version == "2.31.0"
        assert dep.version_specifier == "=="

    def test_multiple(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "requirements.txt",
            "requests==2.31.0\ndjango>=4.0\nflask\n",
        )
        assert len(result.dependencies) == 3
        assert result.dependencies[2].version == ""

    def test_skip_comments(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "requirements.txt",
            "# comment\nrequests==2.31.0\n## another\n",
        )
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "requests"

    def test_skip_options(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "requirements.txt",
            "-r other.txt\n--index-url https://pypi.org/simple\n"
            "-e ./local-pkg\nrequests==2.31.0\n",
        )
        assert len(result.dependencies) == 1

    def test_strip_markers(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "requirements.txt",
            'requests==2.31.0; python_version >= "3.11"\n',
        )
        assert len(result.dependencies) == 1
        assert result.dependencies[0].version == "2.31.0"

    def test_strip_inline_comment(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "requirements.txt",
            "requests==2.31.0  # HTTP library\n",
        )
        assert len(result.dependencies) == 1
        assert result.dependencies[0].version == "2.31.0"

    def test_extras_stripped(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "requirements.txt",
            "httpx[http2]>=0.27.0\n",
        )
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "httpx"

    def test_empty_file(self, tmp_path: Path) -> None:
        result = _parse_file(tmp_path, "requirements.txt", "")
        assert len(result.dependencies) == 0

    def test_compound_specifier(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "requirements.txt",
            "django>=4.0,<5.0\n",
        )
        dep = result.dependencies[0]
        assert dep.version_specifier == ">="
        assert dep.version == "4.0"


class TestPyprojectToml:
    def test_pep621_dependencies(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "pyproject.toml",
            '[project]\ndependencies = [\n  "requests>=2.31.0",\n'
            '  "django>=4.0",\n]\n',
        )
        assert len(result.dependencies) == 2
        names = [d.name for d in result.dependencies]
        assert "requests" in names
        assert "django" in names

    def test_pep621_optional_dev(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "pyproject.toml",
            '[project]\ndependencies = ["requests>=2.31.0"]\n\n'
            "[project.optional-dependencies]\ndev = [\"pytest>=8.0.0\"]\n",
        )
        assert len(result.dependencies) == 2
        dev = [d for d in result.dependencies if d.is_dev]
        assert len(dev) == 1
        assert dev[0].name == "pytest"

    def test_poetry_dependencies(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "pyproject.toml",
            "[tool.poetry.dependencies]\npython = \"^3.11\"\n"
            'requests = "^2.31.0"\npytest = {version = "^8.0.0"}\n',
        )
        names = [d.name for d in result.dependencies]
        assert "python" not in names
        assert "requests" in names
        assert "pytest" in names

    def test_poetry_caret_version(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "pyproject.toml",
            '[tool.poetry.dependencies]\nrequests = "^2.31.0"\n',
        )
        dep = result.dependencies[0]
        assert dep.version_specifier == "^"
        assert dep.version == "2.31.0"

    def test_poetry_dev_group(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "pyproject.toml",
            "[tool.poetry.group.dev.dependencies]\npytest = \"^8.0.0\"\n",
        )
        assert len(result.dependencies) == 1
        assert result.dependencies[0].is_dev is True

    def test_poetry_legacy_dev(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "pyproject.toml",
            '[tool.poetry.dev-dependencies]\nruff = "^0.4.0"\n',
        )
        assert len(result.dependencies) == 1
        assert result.dependencies[0].is_dev is True

    def test_no_dependencies_section(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "pyproject.toml",
            '[build-system]\nrequires = ["setuptools"]\n',
        )
        assert len(result.dependencies) == 0


class TestPipfile:
    def test_packages(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "Pipfile",
            '[packages]\nrequests = "==2.31.0"\nflask = "*"\n\n'
            "[dev-packages]\npytest = \"*\"\n",
        )
        assert len(result.dependencies) == 3
        dev = [d for d in result.dependencies if d.is_dev]
        assert len(dev) == 1
        assert dev[0].name == "pytest"

    def test_star_version(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "Pipfile",
            '[packages]\nflask = "*"\n',
        )
        dep = result.dependencies[0]
        assert dep.version == "*"
        assert dep.version_specifier == ""

    def test_dict_spec(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "Pipfile",
            '[packages]\nhttpx = {version = ">=0.27", extras = ["http2"]}\n',
        )
        dep = result.dependencies[0]
        assert dep.name == "httpx"
        assert dep.version == "0.27"
        assert dep.version_specifier == ">="


class TestSetupCfg:
    def test_install_requires(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "setup.cfg",
            "[options]\ninstall_requires =\n    requests>=2.31.0\n    django>=4.0\n",
        )
        assert len(result.dependencies) == 2

    def test_extras_require(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "setup.cfg",
            "[options]\ninstall_requires =\n    requests>=2.31.0\n\n"
            "[options.extras_require]\ndev =\n    pytest>=8.0.0\n",
        )
        assert len(result.dependencies) == 2
        dev = [d for d in result.dependencies if d.is_dev]
        assert len(dev) == 1
        assert dev[0].name == "pytest"


class TestCanParse:
    def test_matches_python_files(self) -> None:
        parser = PythonParser()
        for name in ("requirements.txt", "pyproject.toml", "Pipfile", "setup.cfg"):
            assert parser.can_parse(Path(name))

    def test_rejects_other_files(self) -> None:
        parser = PythonParser()
        assert not parser.can_parse(Path("Cargo.toml"))
        assert not parser.can_parse(Path("package.json"))
