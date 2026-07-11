from __future__ import annotations

from pathlib import Path

import pytest

from app.parsers.golang import GolangParser
from app.parsers.nodejs import NodeJsParser
from app.parsers.rust import RustParser


class TestPackageJsonUpdate:
    def test_preserves_caret_and_formatting(self) -> None:
        content = (
            '{\n'
            '  "dependencies": {\n'
            '    "express": "^4.18.0",\n'
            '    "lodash": "~4.17.20"\n'
            '  }\n'
            '}\n'
        )
        new, changed = NodeJsParser().update_versions(
            Path("package.json"), content, {"express": "4.19.0"}
        )
        assert '"express": "^4.19.0"' in new
        assert '"lodash": "~4.17.20"' in new
        assert changed == ["express"]

    def test_skips_git_spec(self) -> None:
        content = '{"dependencies": {"mylib": "git+https://x/y.git"}}'
        new, changed = NodeJsParser().update_versions(
            Path("package.json"), content, {"mylib": "2.0.0"}
        )
        assert new == content
        assert changed == []

    def test_unsupported_file(self) -> None:
        with pytest.raises(NotImplementedError):
            NodeJsParser().update_versions(Path("yarn.lock"), "", {"a": "1"})


class TestCargoTomlParseAndUpdate:
    def test_parses_manifest(self, tmp_path: Path) -> None:
        cargo = tmp_path / "Cargo.toml"
        cargo.write_text(
            '[package]\nname = "demo"\n\n'
            "[dependencies]\n"
            'serde = "1.0.100"\n'
            'tokio = { version = "^1.20", features = ["full"] }\n'
            'local = { path = "../local" }\n\n'
            "[dev-dependencies]\n"
            'criterion = "0.5"\n',
            encoding="utf-8",
        )
        result = RustParser().parse(cargo)
        by_name = {d.name: d for d in result.dependencies}
        assert by_name["serde"].version == "1.0.100"
        assert by_name["tokio"].version == "1.20"
        assert by_name["tokio"].version_specifier == "^"
        assert by_name["criterion"].is_dev is True
        assert "local" not in by_name

    def test_update_preserves_format(self) -> None:
        content = (
            "[dependencies]\n"
            'serde = "1.0.100"  # serialization\n'
            'tokio = { version = "^1.20", features = ["full"] }\n'
        )
        new, changed = RustParser().update_versions(
            Path("Cargo.toml"), content, {"serde": "1.0.200", "tokio": "1.35"}
        )
        assert 'serde = "1.0.200"' in new
        assert '"^1.35"' in new
        assert "# serialization" in new
        assert 'features = ["full"]' in new
        assert sorted(changed) == ["serde", "tokio"]

    def test_lock_not_updatable(self) -> None:
        parser = RustParser()
        assert not parser.supports_update(Path("Cargo.lock"))
        with pytest.raises(NotImplementedError):
            parser.update_versions(Path("Cargo.lock"), "", {"a": "1"})


class TestGoModUpdate:
    def test_updates_require_block(self) -> None:
        content = (
            "module example.com/app\n\ngo 1.21\n\n"
            "require (\n"
            "\tgithub.com/gin-gonic/gin v1.9.0\n"
            "\tgithub.com/go-chi/chi v1.5.5 // indirect\n"
            ")\n"
        )
        new, changed = GolangParser().update_versions(
            Path("go.mod"), content, {"github.com/gin-gonic/gin": "v1.9.1"}
        )
        assert "github.com/gin-gonic/gin v1.9.1" in new
        assert "github.com/go-chi/chi v1.5.5 // indirect" in new
        assert changed == ["github.com/gin-gonic/gin"]

    def test_updates_single_line_require(self) -> None:
        content = "module m\n\nrequire github.com/pkg/errors v0.8.0\n"
        new, changed = GolangParser().update_versions(
            Path("go.mod"), content, {"github.com/pkg/errors": "v0.9.1"}
        )
        assert "require github.com/pkg/errors v0.9.1" in new
        assert changed == ["github.com/pkg/errors"]

    def test_replace_block_untouched(self) -> None:
        content = (
            "module m\n\n"
            "replace (\n"
            "\tgithub.com/old/pkg => github.com/new/pkg v2.0.0\n"
            ")\n"
            "require github.com/old/pkg v1.0.0\n"
        )
        new, changed = GolangParser().update_versions(
            Path("go.mod"), content, {"github.com/old/pkg": "v1.5.0"}
        )
        assert "github.com/new/pkg v2.0.0" in new
        assert "require github.com/old/pkg v1.5.0" in new
        assert changed == ["github.com/old/pkg"]

    def test_unsupported_file(self) -> None:
        with pytest.raises(NotImplementedError):
            GolangParser().update_versions(Path("go.sum"), "", {"a": "v1"})
