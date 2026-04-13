from __future__ import annotations

from ipaddress import ip_address, ip_network
from urllib.parse import urlparse


ALLOWED_PROVIDERS = {"ollama", "openai_compatible"}
PRIVATE_NETWORKS = [
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
]


def is_local_hostname(hostname: str | None) -> bool:
    if not hostname:
        return False
    return hostname in {"localhost", "127.0.0.1", "host.docker.internal"}


def is_private_ip(hostname: str | None) -> bool:
    if not hostname:
        return False
    try:
        ip = ip_address(hostname)
    except ValueError:
        return False
    return any(ip in net for net in PRIVATE_NETWORKS)


def is_local_or_private_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    hostname = parsed.hostname
    return is_local_hostname(hostname) or is_private_ip(hostname)


def assert_local_only_provider(provider: str) -> None:
    normalized = (provider or "").strip().lower()
    if normalized not in ALLOWED_PROVIDERS:
        raise ValueError(
            f"Provider '{provider}' no permitido en este fork. "
            f"Permitidos: {', '.join(sorted(ALLOWED_PROVIDERS))}."
        )


def assert_local_only_url(url: str | None, provider: str) -> None:
    if provider == "ollama" and not url:
        return
    if not is_local_or_private_url(url):
        raise ValueError(
            "La URL configurada no es local ni de red privada controlada. "
            "Este fork solo admite endpoints locales."
        )
