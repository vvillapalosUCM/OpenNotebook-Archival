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
