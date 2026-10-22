"""
Tests for the connection-level SSRF guard used by source URL ingestion.

They run real aiohttp servers on loopback addresses. 127.0.0.2 plays the role
of a "public" site (the guard is told to treat it as public); 127.0.0.1 plays
an internal service such as SurrealDB or Ollama.
"""

import asyncio
import sys
import types

import pytest

aiohttp = pytest.importorskip("aiohttp")
from aiohttp import web  # noqa: E402

from open_notebook.utils import ssrf_guard  # noqa: E402

REAL_IS_BLOCKED_IP = ssrf_guard.is_blocked_ip

PUBLIC_IP = "127.0.0.2"
INTERNAL_IP = "127.0.0.1"


@pytest.fixture(autouse=True)
def _guard_on(monkeypatch):
    monkeypatch.delenv(ssrf_guard.ALLOW_PRIVATE_ENV, raising=False)
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    real = REAL_IS_BLOCKED_IP
    # Treat 127.0.0.2 as a public address so redirects can be exercised locally.
    monkeypatch.setattr(
        ssrf_guard, "is_blocked_ip", lambda ip: False if ip == PUBLIC_IP else real(ip)
    )


async def _start(ip, routes):
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, ip, 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, port


async def _scenario(target_builder, allow=False):
    """Start an internal server and a 'public' redirector, then fetch."""

    async def secret(request):
        return web.Response(text="internal-secret")

    internal, internal_port = await _start(INTERNAL_IP, [web.get("/secret", secret)])
    internal_url = f"http://{INTERNAL_IP}:{internal_port}/secret"

    async def redirect(request):
        raise web.HTTPFound(internal_url)

    async def public_page(request):
        return web.Response(text="public-page")

    public, public_port = await _start(
        PUBLIC_IP, [web.get("/redirect", redirect), web.get("/page", public_page)]
    )
    session_factory = ssrf_guard._build_guarded_client_session(aiohttp)
    try:
        url = target_builder(public_port, internal_port)
        async with session_factory(trust_env=True) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return await resp.text()
    finally:
        await public.cleanup()
        await internal.cleanup()


def test_public_page_is_fetched():
    text = asyncio.run(_scenario(lambda p, i: f"http://{PUBLIC_IP}:{p}/page"))
    assert text == "public-page"


def test_direct_internal_ip_is_blocked():
    with pytest.raises(ssrf_guard.BlockedDestinationError):
        asyncio.run(_scenario(lambda p, i: f"http://{INTERNAL_IP}:{i}/secret"))


def test_redirect_to_internal_service_is_blocked():
    with pytest.raises(ssrf_guard.BlockedDestinationError):
        asyncio.run(_scenario(lambda p, i: f"http://{PUBLIC_IP}:{p}/redirect"))


def test_hostname_resolving_to_loopback_is_blocked_at_connect_time():
    async def run():
        session_factory = ssrf_guard._build_guarded_client_session(aiohttp)
        async with session_factory() as session:
            guarded = session.connector
            with pytest.raises(ssrf_guard.BlockedDestinationError):
                # Bypasses the request-level name check on purpose: this is the
                # DNS / rebinding path, where only the resolved IP is known.
                await guarded._resolve_host("localhost", 80)

    asyncio.run(run())


def test_opt_out_allows_private_destinations(monkeypatch):
    monkeypatch.setenv(ssrf_guard.ALLOW_PRIVATE_ENV, "true")
    text = asyncio.run(_scenario(lambda p, i: f"http://{PUBLIC_IP}:{p}/redirect"))
    assert text == "internal-secret"


@pytest.mark.parametrize(
    "ip,blocked",
    [
        ("127.0.0.1", True),
        ("10.1.2.3", True),
        ("172.20.0.5", True),
        ("192.168.1.10", True),
        ("169.254.169.254", True),
        ("100.64.0.1", True),
        ("0.0.0.0", True),
        ("::1", True),
        ("::ffff:127.0.0.1", True),
        ("fe80::1%eth0", True),
        ("not-an-ip", True),
        ("93.184.215.14", False),
        ("2606:4700:4700::1111", False),
    ],
)
def test_ip_classification(ip, blocked):
    assert REAL_IS_BLOCKED_IP(ip) is blocked


def test_install_patches_content_core_modules(monkeypatch):
    names = ssrf_guard.CONTENT_CORE_FETCH_MODULES
    for name in names:
        module = types.ModuleType(name)
        module.aiohttp = aiohttp
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(ssrf_guard, "_installed", False)

    ssrf_guard.install_source_fetch_guard()
    ssrf_guard.install_source_fetch_guard()  # idempotent

    for name in names:
        patched = sys.modules[name].aiohttp
        assert isinstance(patched, ssrf_guard._GuardedAiohttpNamespace)
        # Everything except ClientSession is the real module.
        assert patched.ClientError is aiohttp.ClientError
        assert patched.ClientSession is not aiohttp.ClientSession
    # The real module is never touched, so model providers keep working.
    assert aiohttp.ClientSession.__module__.startswith("aiohttp")


def test_install_fails_loudly_if_content_core_changes(monkeypatch):
    name = ssrf_guard.CONTENT_CORE_FETCH_MODULES[0]
    module = types.ModuleType(name)
    module.aiohttp = object()  # imported some other way
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(ssrf_guard, "_installed", False)
    with pytest.raises(RuntimeError):
        ssrf_guard.install_source_fetch_guard()
