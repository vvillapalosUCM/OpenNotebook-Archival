"""
Connection-level SSRF guard for user-supplied source URLs.

``api.routers.sources.validate_source_url`` checks the URL a user submits, but
content-core then downloads it with aiohttp, which follows HTTP redirects and
resolves DNS again. A public URL that answers ``302 Location: http://surrealdb:8000``
(or a hostname that re-resolves to 127.0.0.1 between check and use) used to
reach internal services.

This module closes that gap where it can no longer be bypassed: at connect time.
Every aiohttp session that content-core opens gets a connector that inspects
the IP address it is about to connect to, for the first request and for every
redirect hop, and refuses anything that is not a public address.

The guard is scoped to content-core modules only, so model providers that
legitimately live on the local network (Ollama, LM Studio...) are unaffected.
Set OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS=true to disable it, exactly as for
the URL pre-check.

When an HTTP(S) proxy is configured through the environment, aiohttp connects
to the proxy and the proxy resolves the target. In that case the connection to
the proxy host is allowed, literal internal IPs and localhost names are still
refused at request time, and final egress filtering is the proxy's job.
"""

from __future__ import annotations

import importlib
import ipaddress
import os
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from loguru import logger

ALLOW_PRIVATE_ENV = "OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS"

# content-core modules that open aiohttp sessions on user-controlled URLs.
CONTENT_CORE_FETCH_MODULES = (
    "content_core.processors.url",
    "content_core.processors.youtube",
    "content_core.content.extraction.graph",
)

_LOCAL_HOSTNAMES = {"localhost", "localhost.localdomain", "host.docker.internal"}
_PROXY_ENV_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")

_installed = False


class BlockedDestinationError(ValueError):
    """Raised when a source fetch would connect to a non-public address.

    Deliberately not an OSError/aiohttp.ClientError: content-core retries those,
    and a blocked destination must fail at once.
    """


def private_destinations_allowed() -> bool:
    return os.environ.get(ALLOW_PRIVATE_ENV, "false").strip().lower() in {"1", "true", "yes", "on"}


def is_blocked_ip(value: str) -> bool:
    """True for any address that is not globally routable (or is unparseable).

    Covers loopback, RFC 1918, link-local / cloud metadata (169.254.0.0/16),
    CGNAT (100.64.0.0/10), unspecified, reserved, documentation and multicast
    ranges, plus IPv4-mapped IPv6 forms of all of them.
    """
    try:
        ip = ipaddress.ip_address(str(value).split("%", 1)[0])
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (not ip.is_global) or ip.is_multicast


def is_blocked_hostname(host: Optional[str]) -> bool:
    """True for localhost-style names and literal non-public IPs."""
    if not host:
        return True
    name = host.strip("[]").rstrip(".").lower()
    if name in _LOCAL_HOSTNAMES or name.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(name.split("%", 1)[0])
    except ValueError:
        return False  # a DNS name: checked against its resolved IPs at connect time
    return is_blocked_ip(name)


def _proxy_hostnames() -> set[str]:
    hosts = set()
    for var in _PROXY_ENV_VARS:
        raw = os.environ.get(var, "").strip()
        if raw:
            parsed = urlparse(raw if "://" in raw else f"http://{raw}")
            if parsed.hostname:
                hosts.add(parsed.hostname.lower())
    return hosts


def _build_guarded_client_session(aiohttp: Any) -> Callable[..., Any]:
    class GuardedTCPConnector(aiohttp.TCPConnector):
        async def _resolve_host(self, host, port, traces=None):  # type: ignore[override]
            results = await super()._resolve_host(host, port, traces=traces)
            if private_destinations_allowed() or host.lower() in _proxy_hostnames():
                return results
            for result in results:
                if is_blocked_ip(result["host"]):
                    logger.warning(
                        "Blocked source fetch to non-public address {} (host {!r})",
                        result["host"],
                        host,
                    )
                    raise BlockedDestinationError(
                        "Source URL points to a private or local network address"
                    )
            return results

    async def _check_request_url(session, ctx, params) -> None:
        # Runs for the first request and for every redirect hop.
        if private_destinations_allowed():
            return
        url = params.url
        if url.scheme not in ("http", "https"):
            raise BlockedDestinationError("Only http and https source URLs are allowed")
        if is_blocked_hostname(url.host):
            logger.warning("Blocked source fetch to local URL host {!r}", url.host)
            raise BlockedDestinationError(
                "Source URL points to a private or local network address"
            )

    trace_config = aiohttp.TraceConfig()
    trace_config.on_request_start.append(_check_request_url)
    trace_config.freeze()

    def guarded_client_session(*args: Any, **kwargs: Any):
        if kwargs.get("connector") is None:
            kwargs["connector"] = GuardedTCPConnector()
        kwargs["trace_configs"] = list(kwargs.get("trace_configs") or []) + [trace_config]
        return aiohttp.ClientSession(*args, **kwargs)

    guarded_client_session.__name__ = "ClientSession"
    return guarded_client_session


class _GuardedAiohttpNamespace:
    """Stands in for the ``aiohttp`` module inside content-core modules only."""

    def __init__(self, real_module: Any) -> None:
        self._real = real_module
        self.ClientSession = _build_guarded_client_session(real_module)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


def install_source_fetch_guard() -> None:
    """Patch content-core's aiohttp usage. Idempotent; safe to call at import."""
    global _installed
    if _installed:
        return

    import aiohttp

    namespace = _GuardedAiohttpNamespace(aiohttp)
    patched = []
    for module_name in CONTENT_CORE_FETCH_MODULES:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            logger.debug("content-core module {} not available; skipping", module_name)
            continue
        if getattr(module, "aiohttp", None) is aiohttp:
            module.aiohttp = namespace
            patched.append(module_name)
        elif not isinstance(getattr(module, "aiohttp", None), _GuardedAiohttpNamespace):
            # content-core changed how it imports aiohttp: fail loudly instead
            # of silently running without protection.
            raise RuntimeError(
                f"SSRF guard could not patch {module_name}; review open_notebook/utils/ssrf_guard.py"
            )

    _installed = True
    logger.info("Source fetch SSRF guard installed on: {}", ", ".join(patched) or "none")
