import asyncio
from starlette.requests import Request
from fastapi.security import HTTPAuthorizationCredentials


def _build_request(headers=None, client_host="10.0.0.5"):
    headers = headers or {}
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/private",
        "headers": raw_headers,
        "client": (client_host, 12345),
        "scheme": "http",
        "server": ("testserver", 80),
        "query_string": b"",
    }
    return Request(scope)


def test_proxy_headers_not_trusted_by_default(monkeypatch):
    monkeypatch.delenv("OPEN_NOTEBOOK_TRUST_PROXY_HEADERS", raising=False)
    from api.auth import PasswordAuthMiddleware

    middleware = PasswordAuthMiddleware(app=lambda scope, receive, send: None)
    request = _build_request({"x-forwarded-for": "203.0.113.55"}, client_host="10.1.1.7")
    assert middleware._client_ip(request) == "10.1.1.7"


def test_proxy_headers_trusted_when_enabled(monkeypatch):
    monkeypatch.setenv("OPEN_NOTEBOOK_TRUST_PROXY_HEADERS", "true")
    from api.auth import PasswordAuthMiddleware

    middleware = PasswordAuthMiddleware(app=lambda scope, receive, send: None)
    request = _build_request({"x-forwarded-for": "203.0.113.55, 10.1.1.7"}, client_host="10.1.1.7")
    assert middleware._client_ip(request) == "203.0.113.55"


def test_check_api_password_accepts_valid_secret(monkeypatch):
    monkeypatch.setenv("OPEN_NOTEBOOK_PASSWORD", "secret-token")
    from api.auth import check_api_password

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="secret-token")
    assert check_api_password(creds) is True


# ---------------------------------------------------------------------------
# Host header poisoning (CVE-2026-48710 / GHSA-86qp-5c8j-p5mr)
# ---------------------------------------------------------------------------

def _protected_app(monkeypatch):
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    monkeypatch.setenv("OPEN_NOTEBOOK_PASSWORD", "secret-token")
    monkeypatch.setenv("OPEN_NOTEBOOK_AUTH_FAILURE_DELAY_MS", "1")
    from api.auth import PasswordAuthMiddleware

    async def private(request):
        return JSONResponse({"ok": True})

    async def health(request):
        return JSONResponse({"status": "healthy"})

    app = Starlette(routes=[Route("/api/notebooks", private), Route("/health", health)])
    app.add_middleware(PasswordAuthMiddleware)
    return app


def _call(app, path, host, auth=None):
    headers = [(b"host", host.encode())]
    if auth:
        headers.append((b"authorization", auth.encode()))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "root_path": "", "headers": headers,
        "client": ("127.0.0.1", 40000), "server": ("127.0.0.1", 5055),
    }
    result = {}
    messages = [{"type": "http.request", "body": b"", "more_body": False}]

    async def receive():
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            result["status"] = message["status"]

    asyncio.run(app(scope, receive, send))
    return result["status"]


def test_poisoned_host_cannot_reach_protected_path(monkeypatch):
    app = _protected_app(monkeypatch)
    for host in ("localhost:5055/docs?", "localhost:5055/health#", "x/health?a="):
        assert _call(app, "/api/notebooks", host) in (400, 401), host


def test_malformed_host_rejected(monkeypatch):
    app = _protected_app(monkeypatch)
    assert _call(app, "/api/notebooks", "localhost:5055/docs?", auth="Bearer secret-token") == 400


def test_valid_hosts_still_work(monkeypatch):
    app = _protected_app(monkeypatch)
    for host in ("localhost:5055", "127.0.0.1:5055", "open_notebook:5055", "[::1]:5055", "api.example.org"):
        assert _call(app, "/health", host) == 200, host
        assert _call(app, "/api/notebooks", host) == 401, host
        assert _call(app, "/api/notebooks", host, auth="Bearer secret-token") == 200, host


def test_host_header_validator():
    from api.auth import host_header_is_valid

    assert host_header_is_valid(None)
    assert host_header_is_valid("localhost:5055")
    assert not host_header_is_valid("localhost:5055/docs?")
    assert not host_header_is_valid("user@localhost")
    assert not host_header_is_valid("localhost 5055")
