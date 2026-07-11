from __future__ import annotations

from app.core.version_resolver import (
    RegistryClient,
    ResolvedVersion,
    VersionResolver,
)
from app.parsers.base import Dependency


class StubRegistry(RegistryClient):
    ecosystem = "python"

    def __init__(self, versions: dict[str, list[str]]) -> None:
        self._versions = versions
        self.calls: list[str] = []

    def get_versions(self, package: str) -> list[str]:
        self.calls.append(package)
        return self._versions.get(package, [])


def _resolver(versions: dict[str, list[str]]) -> VersionResolver:
    return VersionResolver(registries={"python": StubRegistry(versions)})


class TestResolve:
    def test_latest_and_compatible(self) -> None:
        resolver = _resolver({"requests": ["1.0.0", "1.5.0", "2.0.0"]})
        res = resolver.resolve("requests", "1.0.0", specifier=">=")
        assert res is not None
        assert res.latest == "2.0.0"
        assert res.latest_compatible == "2.0.0"
        assert res.is_outdated is True

    def test_pinned_stays_compatible(self) -> None:
        resolver = _resolver({"requests": ["1.0.0", "2.0.0"]})
        res = resolver.resolve("requests", "1.0.0", specifier="==")
        assert res is not None
        assert res.latest == "2.0.0"
        assert res.latest_compatible == "1.0.0"

    def test_caret_specifier(self) -> None:
        resolver = _resolver({"pkg": ["1.2.0", "1.9.0", "2.0.0"]})
        res = resolver.resolve("pkg", "1.2.0", specifier="^")
        assert res is not None
        assert res.latest_compatible == "1.9.0"
        assert res.latest == "2.0.0"

    def test_caret_zero_major(self) -> None:
        resolver = _resolver({"pkg": ["0.2.0", "0.2.9", "0.3.0"]})
        res = resolver.resolve("pkg", "0.2.0", specifier="^")
        assert res is not None
        assert res.latest_compatible == "0.2.9"

    def test_tilde_specifier(self) -> None:
        resolver = _resolver({"pkg": ["1.2.0", "1.2.9", "1.3.0"]})
        res = resolver.resolve("pkg", "1.2.0", specifier="~")
        assert res is not None
        assert res.latest_compatible == "1.2.9"

    def test_prereleases_excluded_from_latest(self) -> None:
        resolver = _resolver({"pkg": ["1.0.0", "2.0.0rc1"]})
        res = resolver.resolve("pkg", "1.0.0")
        assert res is not None
        assert res.latest == "1.0.0"
        assert res.is_prerelease is False

    def test_only_prereleases(self) -> None:
        resolver = _resolver({"pkg": ["2.0.0rc1"]})
        res = resolver.resolve("pkg", "")
        assert res is not None
        assert res.latest == "2.0.0rc1"
        assert res.is_prerelease is True

    def test_unknown_package(self) -> None:
        resolver = _resolver({})
        assert resolver.resolve("nope", "1.0.0") is None

    def test_invalid_versions_skipped(self) -> None:
        resolver = _resolver({"pkg": ["not-a-version", "1.0.0"]})
        res = resolver.resolve("pkg", "0.9.0")
        assert res is not None
        assert res.latest == "1.0.0"

    def test_unpinned_not_outdated(self) -> None:
        resolver = _resolver({"pkg": ["1.0.0"]})
        res = resolver.resolve("pkg", "")
        assert res is not None
        assert res.is_outdated is False
        assert res.latest_compatible == "1.0.0"

    def test_unsupported_ecosystem(self) -> None:
        resolver = _resolver({"pkg": ["1.0.0"]})
        assert resolver.resolve("pkg", "1.0.0", ecosystem="rust") is None


class TestResolveBatch:
    def test_resolves_and_caches(self) -> None:
        registry = StubRegistry({"a": ["1.0.0", "2.0.0"], "b": ["3.0.0"]})
        resolver = VersionResolver(registries={"python": registry})
        deps = [
            Dependency(name="a", version="1.0.0", version_specifier=">=", ecosystem="python"),
            Dependency(name="b", version="3.0.0", version_specifier="==", ecosystem="python"),
            Dependency(name="a", version="1.0.0", version_specifier=">=", ecosystem="python"),
        ]
        resolved = resolver.resolve_batch(deps)
        assert len(resolved) == 2
        assert registry.calls == ["a", "b"]

    def test_skips_unknown(self) -> None:
        resolver = _resolver({"a": ["1.0.0"]})
        deps = [
            Dependency(name="a", version="1.0.0", ecosystem="python"),
            Dependency(name="missing", version="1.0.0", ecosystem="python"),
        ]
        resolved = resolver.resolve_batch(deps)
        assert [r.package for r in resolved] == ["a"]


class TestIsOutdated:
    def test_newer_available(self) -> None:
        res = ResolvedVersion("p", current="1.0.0", latest="2.0.0", latest_compatible="2.0.0")
        assert res.is_outdated is True

    def test_up_to_date(self) -> None:
        res = ResolvedVersion("p", current="2.0.0", latest="2.0.0", latest_compatible="2.0.0")
        assert res.is_outdated is False

    def test_invalid_current_falls_back_to_string_compare(self) -> None:
        res = ResolvedVersion("p", current="abc", latest="2.0.0", latest_compatible="2.0.0")
        assert res.is_outdated is True
