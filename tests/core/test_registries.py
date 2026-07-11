from __future__ import annotations

import httpx
import pytest

from app.core.version_resolver import (
    CratesIoClient,
    GoProxyClient,
    MavenCentralClient,
    NpmClient,
    _escape_go_module,
    default_registries,
)


def _transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


class TestNpmClient:
    def test_parses_versions(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/express"
            return httpx.Response(
                200, json={"versions": {"4.18.0": {}, "4.18.2": {}}}
            )

        client = NpmClient(transport=_transport(handler))
        assert client.get_versions("express") == ["4.18.0", "4.18.2"]

    def test_scoped_package_encoded(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert "%2F" in request.url.raw_path.decode()
            return httpx.Response(200, json={"versions": {"18.0.0": {}}})

        client = NpmClient(transport=_transport(handler))
        assert client.get_versions("@types/node") == ["18.0.0"]

    def test_not_found(self) -> None:
        client = NpmClient(
            transport=_transport(lambda r: httpx.Response(404))
        )
        assert client.get_versions("nope") == []


class TestCratesIoClient:
    def test_skips_yanked(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers.get("user-agent", "").startswith("updater-cli")
            return httpx.Response(
                200,
                json={
                    "versions": [
                        {"num": "1.0.200", "yanked": False},
                        {"num": "1.0.199", "yanked": True},
                    ]
                },
            )

        client = CratesIoClient(transport=_transport(handler))
        assert client.get_versions("serde") == ["1.0.200"]


class TestGoProxyClient:
    def test_parses_version_list(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/github.com/gin-gonic/gin/@v/list"
            return httpx.Response(200, text="v1.9.0\nv1.9.1\n\n")

        client = GoProxyClient(transport=_transport(handler))
        assert client.get_versions("github.com/gin-gonic/gin") == [
            "v1.9.0",
            "v1.9.1",
        ]

    def test_escapes_uppercase(self) -> None:
        assert (
            _escape_go_module("github.com/Azure/azure-sdk")
            == "github.com/!azure/azure-sdk"
        )

    def test_gone_module(self) -> None:
        client = GoProxyClient(
            transport=_transport(lambda r: httpx.Response(410))
        )
        assert client.get_versions("example.com/gone") == []


class TestMavenCentralClient:
    def test_parses_gav_docs(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            query = dict(request.url.params)
            assert 'g:"org.springframework"' in query["q"]
            return httpx.Response(
                200,
                json={
                    "response": {
                        "docs": [{"v": "5.3.20"}, {"v": "5.3.21"}]
                    }
                },
            )

        client = MavenCentralClient(transport=_transport(handler))
        assert client.get_versions("org.springframework:spring-core") == [
            "5.3.20",
            "5.3.21",
        ]

    def test_rejects_name_without_group(self) -> None:
        client = MavenCentralClient(
            transport=_transport(lambda r: pytest.fail("should not be called"))
        )
        assert client.get_versions("spring-core") == []


class TestDefaultRegistries:
    def test_covers_all_ecosystems(self) -> None:
        registries = default_registries()
        assert set(registries) == {"python", "nodejs", "rust", "golang", "java"}
        for ecosystem, client in registries.items():
            assert client.ecosystem == ecosystem


class TestRawVersionPreserved:
    def test_go_versions_keep_v_prefix(self) -> None:
        from app.core.version_resolver import VersionResolver

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="v1.9.0\nv1.9.1\n")

        resolver = VersionResolver(
            registries={"golang": GoProxyClient(transport=_transport(handler))}
        )
        res = resolver.resolve(
            "github.com/gin-gonic/gin", "v1.9.0", ecosystem="golang"
        )
        assert res is not None
        assert res.latest == "v1.9.1"
