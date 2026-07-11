from __future__ import annotations

from pathlib import Path

from app.parsers.rust import RustParser


def _parse_file(tmp_path: Path, filename: str, content: str):
    file_path = tmp_path / filename
    file_path.write_text(content, encoding="utf-8")
    return RustParser().parse(file_path)


class TestCargoLock:
    def test_multiple_packages(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "Cargo.lock",
            """\
version = 3

[[package]]
name = "serde"
version = "1.0.193"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "abc123"

[[package]]
name = "tokio"
version = "1.35.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "def456"
""",
        )
        assert len(result.dependencies) == 2
        serde = result.dependencies[0]
        assert serde.name == "serde"
        assert serde.version == "1.0.193"
        assert serde.version_specifier == "="
        tokio = result.dependencies[1]
        assert tokio.name == "tokio"
        assert tokio.version == "1.35.1"

    def test_skips_top_level_version(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "Cargo.lock",
            """\
version = 3

[[package]]
name = "rand"
version = "0.8.5"
""",
        )
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "rand"

    def test_minimal_package(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "Cargo.lock",
            """\
[[package]]
name = "libc"
version = "0.2.150"
""",
        )
        assert len(result.dependencies) == 1
        dep = result.dependencies[0]
        assert dep.name == "libc"
        assert dep.version == "0.2.150"
        assert dep.version_specifier == "="

    def test_empty_lock(self, tmp_path: Path) -> None:
        result = _parse_file(tmp_path, "Cargo.lock", "version = 3\n")
        assert len(result.dependencies) == 0

    def test_no_packages_key(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "Cargo.lock",
            'version = 3\n\n[[metadata]]\nkey = "value"\n',
        )
        assert len(result.dependencies) == 0

    def test_package_without_version_skipped(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "Cargo.lock",
            """\
[[package]]
name = "broken"
""",
        )
        assert len(result.dependencies) == 0

    def test_is_dev_always_false(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "Cargo.lock",
            """\
[[package]]
name = "serde"
version = "1.0.0"
""",
        )
        assert result.dependencies[0].is_dev is False

    def test_source_field_set(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "Cargo.lock",
            """\
[[package]]
name = "serde"
version = "1.0.0"
""",
        )
        assert "Cargo.lock" in result.dependencies[0].source


class TestCanParse:
    def test_matches_cargo_lock(self) -> None:
        assert RustParser().can_parse(Path("Cargo.lock"))

    def test_matches_cargo_toml(self) -> None:
        assert RustParser().can_parse(Path("Cargo.toml"))

    def test_rejects_other_files(self) -> None:
        parser = RustParser()
        assert not parser.can_parse(Path("package.json"))
        assert not parser.can_parse(Path("requirements.txt"))
