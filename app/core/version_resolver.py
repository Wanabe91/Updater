from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from app.parsers.base import Dependency

logger = logging.getLogger(__name__)


@dataclass
class ResolvedVersion:
    package: str
    current: str
    latest: str
    latest_compatible: str
    is_prerelease: bool = False

    @property
    def is_outdated(self) -> bool:
        if not self.current or not self.latest:
            return False
        try:
            return Version(self.latest) > Version(self.current)
        except InvalidVersion:
            return self.latest != self.current


class RegistryClient(ABC):
    ecosystem: str

    @abstractmethod
    def get_versions(self, package: str) -> list[str]:
        """Return all published versions, or an empty list if not found."""
        raise NotImplementedError


class PyPIClient(RegistryClient):
    ecosystem = "python"

    def __init__(
        self,
        base_url: str = "https://pypi.org/pypi",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout, follow_redirects=True, transport=transport
        )

    def get_versions(self, package: str) -> list[str]:
        response = self._client.get(f"{self._base_url}/{package}/json")
        if response.status_code == 404:
            return []
        response.raise_for_status()
        releases = response.json().get("releases", {})
        return [version for version, files in releases.items() if files]

    def get_metadata(self, package: str) -> dict | None:
        """Return {"version", "requires_dist"} for the latest release."""
        response = self._client.get(f"{self._base_url}/{package}/json")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        info = response.json().get("info", {})
        return {
            "version": info.get("version", ""),
            "requires_dist": info.get("requires_dist") or [],
        }


class NpmClient(RegistryClient):
    ecosystem = "nodejs"

    def __init__(
        self,
        base_url: str = "https://registry.npmjs.org",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
            # Abbreviated metadata is much smaller than the full document.
            headers={"Accept": "application/vnd.npm.install-v1+json"},
        )

    def get_versions(self, package: str) -> list[str]:
        encoded = package.replace("/", "%2F")
        response = self._client.get(f"{self._base_url}/{encoded}")
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return list(response.json().get("versions", {}).keys())


class CratesIoClient(RegistryClient):
    ecosystem = "rust"

    def __init__(
        self,
        base_url: str = "https://crates.io/api/v1/crates",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
            # crates.io requires a User-Agent identifying the client.
            headers={"User-Agent": "updater-cli (dependency checker)"},
        )

    def get_versions(self, package: str) -> list[str]:
        response = self._client.get(f"{self._base_url}/{package}/versions")
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return [
            v["num"]
            for v in response.json().get("versions", [])
            if not v.get("yanked")
        ]


def _escape_go_module(module: str) -> str:
    # The Go module proxy escapes uppercase letters as "!<lowercase>".
    return "".join(f"!{c.lower()}" if c.isupper() else c for c in module)


class GoProxyClient(RegistryClient):
    ecosystem = "golang"

    def __init__(
        self,
        base_url: str = "https://proxy.golang.org",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout, follow_redirects=True, transport=transport
        )

    def get_versions(self, package: str) -> list[str]:
        escaped = _escape_go_module(package)
        response = self._client.get(f"{self._base_url}/{escaped}/@v/list")
        if response.status_code in (404, 410):
            return []
        response.raise_for_status()
        return [line.strip() for line in response.text.splitlines() if line.strip()]


class MavenCentralClient(RegistryClient):
    ecosystem = "java"

    def __init__(
        self,
        base_url: str = "https://search.maven.org/solrsearch/select",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._client = httpx.Client(
            timeout=timeout, follow_redirects=True, transport=transport
        )

    def get_versions(self, package: str) -> list[str]:
        if ":" not in package:
            return []
        group, artifact = package.split(":", 1)
        response = self._client.get(
            self._base_url,
            params={
                "q": f'g:"{group}" AND a:"{artifact}"',
                "core": "gav",
                "rows": "100",
                "wt": "json",
            },
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        docs = response.json().get("response", {}).get("docs", [])
        return [doc["v"] for doc in docs if "v" in doc]


def default_registries() -> dict[str, RegistryClient]:
    return {
        client.ecosystem: client
        for client in (
            PyPIClient(),
            NpmClient(),
            CratesIoClient(),
            GoProxyClient(),
            MavenCentralClient(),
        )
    }


def _caret_upper_bound(version: Version) -> str:
    release = list(version.release) or [0]
    for i, part in enumerate(release):
        if part != 0:
            bumped = release[: i + 1]
            bumped[i] += 1
            bumped += [0] * (len(release) - len(bumped))
            return ".".join(str(p) for p in bumped)
    return ".".join(str(p) for p in release[:-1] + [release[-1] + 1])


def _build_specifier_set(specifier: str, version: str) -> SpecifierSet | None:
    if not specifier or not version or version == "*":
        return None
    try:
        if specifier == "^":
            base = Version(version)
            return SpecifierSet(f">={version},<{_caret_upper_bound(base)}")
        if specifier == "~":
            return SpecifierSet(f"~={version}")
        return SpecifierSet(f"{specifier}{version}")
    except (InvalidSpecifier, InvalidVersion):
        return None


class VersionResolver:
    def __init__(self, registries: dict[str, RegistryClient] | None = None) -> None:
        if registries is None:
            registries = default_registries()
        self._registries = registries
        self._cache: dict[tuple[str, str], list[str]] = {}

    def supports(self, ecosystem: str) -> bool:
        return ecosystem in self._registries

    def _get_versions(self, ecosystem: str, package: str) -> list[str]:
        key = (ecosystem, package)
        if key not in self._cache:
            registry = self._registries[ecosystem]
            try:
                self._cache[key] = registry.get_versions(package)
            except httpx.HTTPError as exc:
                logger.warning("Failed to fetch versions for %s: %s", package, exc)
                self._cache[key] = []
        return self._cache[key]

    def resolve(
        self,
        package: str,
        current_version: str,
        ecosystem: str = "python",
        specifier: str = "",
    ) -> ResolvedVersion | None:
        if not self.supports(ecosystem):
            return None

        raw_versions = self._get_versions(ecosystem, package)
        versions: list[tuple[Version, str]] = []
        for raw in raw_versions:
            try:
                versions.append((Version(raw), raw))
            except InvalidVersion:
                continue
        if not versions:
            return None

        stable = [v for v in versions if not v[0].is_prerelease]
        latest = max(stable, key=lambda v: v[0]) if stable else max(
            versions, key=lambda v: v[0]
        )

        spec_set = _build_specifier_set(specifier, current_version)
        if spec_set is not None:
            candidates = stable if stable else versions
            compatible = [v for v in candidates if v[0] in spec_set]
            latest_compatible = (
                max(compatible, key=lambda v: v[0]) if compatible else latest
            )
        else:
            latest_compatible = latest

        return ResolvedVersion(
            package=package,
            current=current_version,
            latest=latest[1],
            latest_compatible=latest_compatible[1],
            is_prerelease=latest[0].is_prerelease,
        )

    def resolve_batch(self, dependencies: list[Dependency]) -> list[ResolvedVersion]:
        resolved: list[ResolvedVersion] = []
        seen: set[tuple[str, str]] = set()
        for dep in dependencies:
            key = (dep.ecosystem, dep.name)
            if key in seen:
                continue
            seen.add(key)
            result = self.resolve(
                package=dep.name,
                current_version=dep.version,
                ecosystem=dep.ecosystem or "python",
                specifier=dep.version_specifier,
            )
            if result is not None:
                resolved.append(result)
        return resolved
