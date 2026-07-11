from __future__ import annotations

from pathlib import Path

from app.parsers.nodejs import NodeJsParser


def _parse_file(tmp_path: Path, filename: str, content: str):
    file_path = tmp_path / filename
    file_path.write_text(content, encoding="utf-8")
    return NodeJsParser().parse(file_path)


class TestPackageJson:
    def test_dependencies(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "package.json",
            '{"dependencies": {"express": "^4.18.0", "lodash": "~4.17.21"}}',
        )
        assert len(result.dependencies) == 2
        express = next(d for d in result.dependencies if d.name == "express")
        assert express.version == "4.18.0"
        assert express.version_specifier == "^"
        assert express.is_dev is False
        lodash = next(d for d in result.dependencies if d.name == "lodash")
        assert lodash.version_specifier == "~"

    def test_dev_dependencies(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "package.json",
            '{"devDependencies": {"jest": "^29.0.0"}}',
        )
        assert len(result.dependencies) == 1
        assert result.dependencies[0].is_dev is True

    def test_peer_and_optional(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "package.json",
            '{"peerDependencies": {"react": ">=16.0.0"},'
            ' "optionalDependencies": {"fsevents": "^2.3.0"}}',
        )
        assert len(result.dependencies) == 2
        react = next(d for d in result.dependencies if d.name == "react")
        assert react.version_specifier == ">="
        assert react.is_dev is False

    def test_exact_version(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "package.json",
            '{"dependencies": {"lodash": "4.17.21"}}',
        )
        dep = result.dependencies[0]
        assert dep.version == "4.17.21"
        assert dep.version_specifier == ""

    def test_star_version(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "package.json",
            '{"dependencies": {"lodash": "*"}}',
        )
        dep = result.dependencies[0]
        assert dep.version == "*"
        assert dep.version_specifier == ""

    def test_git_url_skipped(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "package.json",
            '{"dependencies": {"my-pkg": "git+https://github.com/user/repo.git"}}',
        )
        assert len(result.dependencies) == 0

    def test_workspace_skipped(self, tmp_path: Path) -> None:
        result = _parse_file(
            tmp_path,
            "package.json",
            '{"dependencies": {"my-pkg": "workspace:*"}}',
        )
        assert len(result.dependencies) == 0


class TestPackageLock:
    def test_v3_packages(self, tmp_path: Path) -> None:
        content = """{
            "lockfileVersion": 3,
            "packages": {
                "": {},
                "node_modules/express": {"version": "4.18.2"},
                "node_modules/lodash": {"version": "4.17.21"}
            }
        }"""
        result = _parse_file(tmp_path, "package-lock.json", content)
        assert len(result.dependencies) == 2
        express = next(d for d in result.dependencies if d.name == "express")
        assert express.version == "4.18.2"
        assert express.version_specifier == "="

    def test_skips_root_package(self, tmp_path: Path) -> None:
        content = '{"lockfileVersion": 3, "packages": {"": {"name": "myapp"}}}'
        result = _parse_file(tmp_path, "package-lock.json", content)
        assert len(result.dependencies) == 0

    def test_v1_fallback(self, tmp_path: Path) -> None:
        content = '{"lockfileVersion": 1, "dependencies": {"express": {"version": "4.18.2"}}}'
        result = _parse_file(tmp_path, "package-lock.json", content)
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "express"

    def test_scoped_package(self, tmp_path: Path) -> None:
        content = """{
            "lockfileVersion": 3,
            "packages": {
                "node_modules/@types/node": {"version": "18.0.0"}
            }
        }"""
        result = _parse_file(tmp_path, "package-lock.json", content)
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "@types/node"


class TestYarnLock:
    def test_basic(self, tmp_path: Path) -> None:
        content = (
            'express@^4.18.0:\n  version "4.18.2"\n'
            '  resolved "https://registry.yarnpkg.com/..."\n\n'
            'lodash@^4.17.21:\n  version "4.17.21"\n'
            '  resolved "https://registry.yarnpkg.com/..."\n'
        )
        result = _parse_file(tmp_path, "yarn.lock", content)
        assert len(result.dependencies) == 2
        express = next(d for d in result.dependencies if d.name == "express")
        assert express.version == "4.18.2"
        assert express.version_specifier == "="

    def test_multiple_specs(self, tmp_path: Path) -> None:
        content = 'lodash@^4.17.21, lodash@^4.17.15:\n  version "4.17.21"\n\n'
        result = _parse_file(tmp_path, "yarn.lock", content)
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "lodash"

    def test_scoped_package(self, tmp_path: Path) -> None:
        content = '@types/node@^18.0.0:\n  version "18.11.9"\n\n'
        result = _parse_file(tmp_path, "yarn.lock", content)
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "@types/node"

    def test_quoted_scoped_key(self, tmp_path: Path) -> None:
        content = (
            '"@babel/core@^7.20.0", "@babel/core@^7.18.0":\n'
            '  version "7.20.12"\n\n'
        )
        result = _parse_file(tmp_path, "yarn.lock", content)
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "@babel/core"
        assert result.dependencies[0].version == "7.20.12"

    def test_npm_protocol_key(self, tmp_path: Path) -> None:
        content = '"lodash@npm:^4.17.21":\n  version "4.17.21"\n\n'
        result = _parse_file(tmp_path, "yarn.lock", content)
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "lodash"


class TestPnpmLock:
    def test_basic(self, tmp_path: Path) -> None:
        content = (
            "packages:\n\n"
            "  /express@4.18.2:\n    resolution: {integrity: ...}\n\n"
            "  /lodash@4.17.21:\n    resolution: {integrity: ...}\n"
        )
        result = _parse_file(tmp_path, "pnpm-lock.yaml", content)
        assert len(result.dependencies) == 2
        express = next(d for d in result.dependencies if d.name == "express")
        assert express.version == "4.18.2"
        assert express.version_specifier == "="

    def test_scoped_package(self, tmp_path: Path) -> None:
        content = "packages:\n\n  /@types/node@18.0.0:\n    resolution: {integrity: ...}\n"
        result = _parse_file(tmp_path, "pnpm-lock.yaml", content)
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "@types/node"

    def test_v9_no_leading_slash(self, tmp_path: Path) -> None:
        content = (
            "packages:\n\n"
            "  express@4.18.2:\n    resolution: {integrity: ...}\n\n"
            "  '@types/node@18.0.0':\n    resolution: {integrity: ...}\n\n"
            "snapshots:\n\n"
            "  ignored@1.0.0:\n    dependencies: {}\n"
        )
        result = _parse_file(tmp_path, "pnpm-lock.yaml", content)
        names = [d.name for d in result.dependencies]
        assert names == ["express", "@types/node"]

    def test_peer_suffix_stripped(self, tmp_path: Path) -> None:
        content = (
            "packages:\n\n"
            "  /vue-router@4.2.0(vue@3.3.0):\n    resolution: {integrity: ...}\n"
        )
        result = _parse_file(tmp_path, "pnpm-lock.yaml", content)
        assert len(result.dependencies) == 1
        assert result.dependencies[0].name == "vue-router"
        assert result.dependencies[0].version == "4.2.0"


class TestCanParse:
    def test_matches_nodejs_files(self) -> None:
        parser = NodeJsParser()
        for name in ("package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
            assert parser.can_parse(Path(name))

    def test_rejects_other_files(self) -> None:
        parser = NodeJsParser()
        assert not parser.can_parse(Path("Cargo.toml"))
        assert not parser.can_parse(Path("requirements.txt"))
