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


# ---------------------------------------------------------------------------
# Non-ASCII passwords, template placeholders and lockout accounting
# ---------------------------------------------------------------------------

def _app_with_password(monkeypatch, password, max_attempts="3"):
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    monkeypatch.setenv("OPEN_NOTEBOOK_PASSWORD", password)
    monkeypatch.setenv("OPEN_NOTEBOOK_AUTH_FAILURE_DELAY_MS", "1")
    monkeypatch.setenv("OPEN_NOTEBOOK_AUTH_MAX_ATTEMPTS", max_attempts)
    from api.auth import PasswordAuthMiddleware

    async def private(request):
        return JSONResponse({"ok": True})

    async def health(request):
        return JSONResponse({"status": "healthy"})

    app = Starlette(routes=[Route("/api/notebooks", private), Route("/health", health)])
    app.add_middleware(PasswordAuthMiddleware)
    return app


def _call_raw(app, path, auth_bytes=None):
    """Like _call, but takes the Authorization header as raw bytes."""
    headers = [(b"host", b"localhost:5055")]
    if auth_bytes is not None:
        headers.append((b"authorization", auth_bytes))
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


def test_secrets_match_handles_non_ascii():
    from api.auth import secrets_match

    assert secrets_match("secret-token", "secret-token")
    assert secrets_match("contraseña", "contraseña")
    # UTF-8 bytes on the wire, decoded as latin-1 by the server.
    assert secrets_match("contraseña".encode("utf-8").decode("latin-1"), "contraseña")
    assert not secrets_match("contrasena", "contraseña")
    assert not secrets_match("", "contraseña")
    assert not secrets_match(None, "contraseña")
    assert not secrets_match("contraseña", None)


def test_non_ascii_password_authenticates(monkeypatch):
    password = "Contraseña-Árbol-2026"
    app = _app_with_password(monkeypatch, password)
    # Browser: one latin-1 byte per character.
    assert _call_raw(app, "/api/notebooks", b"Bearer " + password.encode("latin-1")) == 200
    # curl / API clients: UTF-8 bytes.
    assert _call_raw(app, "/api/notebooks", b"Bearer " + password.encode("utf-8")) == 200
    assert _call_raw(app, "/api/notebooks", b"Bearer Contrasena-Arbol-2026") == 401


def test_check_api_password_accepts_non_ascii(monkeypatch):
    monkeypatch.setenv("OPEN_NOTEBOOK_PASSWORD", "contraseña")
    from api.auth import check_api_password

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="contraseña")
    assert check_api_password(creds) is True


def test_placeholder_password_is_refused(monkeypatch):
    for placeholder in (
        "CHANGE_ME_TO_A_STRONG_PASSWORD",
        "⚠️_CAMBIAR_ESTO_contraseña_de_acceso",
    ):
        app = _app_with_password(monkeypatch, placeholder)
        assert _call_raw(app, "/health") == 200
        assert _call_raw(app, "/api/notebooks") == 503
        assert _call_raw(app, "/api/notebooks", b"Bearer " + placeholder.encode("utf-8")) == 503


def test_missing_header_does_not_trigger_lockout(monkeypatch):
    app = _app_with_password(monkeypatch, "secret-token", max_attempts="3")
    for _ in range(10):
        assert _call_raw(app, "/api/notebooks") == 401
    assert _call_raw(app, "/api/notebooks", b"Bearer secret-token") == 200


def test_wrong_password_still_triggers_lockout(monkeypatch):
    app = _app_with_password(monkeypatch, "secret-token", max_attempts="3")
    for _ in range(3):
        assert _call_raw(app, "/api/notebooks", b"Bearer wrong") == 401
    assert _call_raw(app, "/api/notebooks", b"Bearer secret-token") == 429
