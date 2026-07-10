from __future__ import annotations

from pathlib import Path

from app.parsers.golang import GolangParser


def _parse_file(tmp_path: Path, filename: str, content: str):
    file_path = tmp_path / filename
    file_path.write_text(content, encoding="utf-8")
    return GolangParser().parse(file_path)


class TestGoMod:
    def test_single_line_require(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "go.mod",
            "module example.com/myapp\n\ngo 1.21\n\n"
            "require github.com/gin-gonic/gin v1.9.1\n",
        )
        assert len(result.dependencies) == 1
        dep = result.dependencies[0]
        assert dep.name == "github.com/gin-gonic/gin"
        assert dep.version == "v1.9.1"
        assert dep.is_dev is False

    def test_require_block(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "go.mod",
            "module example.com/myapp\n\ngo 1.21\n\nrequire (\n"
            "\tgithub.com/gin-gonic/gin v1.9.1\n"
            "\tgithub.com/go-chi/chi v1.5.5\n"
            ")\n",
        )
        assert len(result.dependencies) == 2
        names = [d.name for d in result.dependencies]
        assert "github.com/gin-gonic/gin" in names
        assert "github.com/go-chi/chi" in names

    def test_indirect_deps(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "go.mod",
            "module example.com/myapp\n\ngo 1.21\n\n"
            "require (\n"
            "\tgithub.com/gin-gonic/gin v1.9.1\n"
            "\tgithub.com/json-iterator/go v1.1.12 // indirect\n"
            ")\n",
        )
        assert len(result.dependencies) == 2
        direct = next(d for d in result.dependencies if "gin" in d.name)
        indirect = next(d for d in result.dependencies if "json-iterator" in d.name)
        assert direct.is_dev is False
        assert indirect.is_dev is True

    def test_skips_module_and_go(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "go.mod",
            "module example.com/myapp\n\ngo 1.21\n",
        )
        assert len(result.dependencies) == 0

    def test_skips_exclude_block(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "go.mod",
            "module example.com/myapp\n\ngo 1.21\n\n"
            "exclude (\n"
            "\tgithub.com/old/pkg v1.0.0\n"
            ")\n"
            "require github.com/gin-gonic/gin v1.9.1\n",
        )
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "github.com/gin-gonic/gin"

    def test_skips_replace_block(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "go.mod",
            "module example.com/myapp\n\ngo 1.21\n\n"
            "replace (\n"
            "\tgithub.com/old/pkg => github.com/new/pkg v2.0.0\n"
            ")\n"
            "require github.com/gin-gonic/gin v1.9.1\n",
        )
        assert len(result.dependencies) == 1

    def test_skips_retract_block(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "go.mod",
            "module example.com/myapp\n\ngo 1.21\n\n"
            "retract (\n"
            "\tv1.0.0\n"
            ")\n"
            "require github.com/gin-gonic/gin v1.9.1\n",
        )
        assert len(result.dependencies) == 1

    def test_comments_skipped(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "go.mod",
            "module example.com/myapp\n\n// this is a comment\n"
            "require github.com/gin-gonic/gin v1.9.1\n",
        )
        assert len(result.dependencies) == 1

    def test_empty_file(self, tmp_path: Path) -> None:
        result = _parse_file(tmp_path, "go.mod", "")
        assert len(result.dependencies) == 0


class TestGoSum:
    def test_basic(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "go.sum",
            "github.com/gin-gonic/gin v1.9.1 h1:abc123\n"
            "github.com/gin-gonic/gin v1.9.1/go.mod h1:def456\n"
            "github.com/go-chi/chi v1.5.5 h1:xyz789\n",
        )
        assert len(result.dependencies) == 2
        gin = next(d for d in result.dependencies if "gin" in d.name)
        assert gin.version == "v1.9.1"
        assert gin.version_specifier == "="

    def test_skips_go_mod_entries(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "go.sum",
            "github.com/gin-gonic/gin v1.9.1 h1:abc123\n"
            "github.com/gin-gonic/gin v1.9.1/go.mod h1:def456\n",
        )
        assert len(result.dependencies) == 1

    def test_deduplicates(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "go.sum",
            "github.com/gin-gonic/gin v1.9.1 h1:abc123\n"
            "github.com/gin-gonic/gin v1.9.1 h1:xyz789\n",
        )
        assert len(result.dependencies) == 1


class TestCanParse:
    def test_matches_golang_files(self) -> None:
        parser = GolangParser()
        assert parser.can_parse(Path("go.mod"))
        assert parser.can_parse(Path("go.sum"))

    def test_rejects_other_files(self) -> None:
        parser = GolangParser()
        assert not parser.can_parse(Path("Cargo.toml"))
        assert not parser.can_parse(Path("package.json"))
