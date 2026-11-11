import asyncio
import hmac
import os
import re
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from open_notebook.utils.encryption import get_secret_from_env


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


# A Host header is "hostname[:port]" or "[ipv6][:port]". Anything else ("/",
# "?", "#", "@", spaces...) is malformed. Older Starlette versions rebuild
# request.url from Host, so a value like "localhost:5055/docs?" poisoned
# request.url.path (CVE-2026-48710 / GHSA-86qp-5c8j-p5mr) and let any request
# match a public path. Such headers are rejected outright.
def secrets_match(candidate: Optional[str], expected: Optional[str]) -> bool:
    """Constant-time comparison that also works for non-ASCII secrets.

    ``hmac.compare_digest`` raises ``TypeError`` when given ``str`` values
    containing non-ASCII characters, so a password such as ``contraseña`` or
    ``Árbol-2026`` turned every authenticated request into a 500. Both sides
    are compared as bytes instead.

    HTTP header values reach us decoded as latin-1. A browser sends ``ñ`` as
    the single byte 0xF1, while curl and most API clients send its UTF-8
    bytes; both spellings of the same password are accepted.
    """
    if not candidate or not expected:
        return False
    expected_bytes = expected.encode("utf-8")
    matched = hmac.compare_digest(candidate.encode("utf-8"), expected_bytes)
    try:
        wire_bytes = candidate.encode("latin-1")
    except UnicodeEncodeError:
        wire_bytes = b""
    # Evaluated unconditionally so both paths cost the same.
    matched_wire = hmac.compare_digest(wire_bytes, expected_bytes)
    return matched or matched_wire


# Values shipped in .env.example / .env.hardened. Anyone can read them in the
# public repository, so a deployment still using one has no real password.
_PLACEHOLDER_MARKERS = ("CHANGE_ME", "CAMBIAR_ESTO")


def is_placeholder_secret(value: Optional[str]) -> bool:
    """True when ``value`` is one of the example secrets from the templates."""
    if not value:
        return False
    upper = value.upper()
    return any(marker in upper for marker in _PLACEHOLDER_MARKERS)


_HOST_HEADER_RE = re.compile(
    r"^(?:[A-Za-z0-9_](?:[A-Za-z0-9_.\-]*[A-Za-z0-9_])?|\[[0-9A-Fa-f:.]+\])(?::[0-9]{1,5})?$"
)


def host_header_is_valid(host: Optional[str]) -> bool:
    """True when the Host header is absent or a well-formed host[:port]."""
    if host is None:
        return True
    return bool(_HOST_HEADER_RE.fullmatch(host.strip()))


def request_path(request: Request) -> str:
    """Real ASGI path of the request.

    Never use request.url.path for security decisions: it is rebuilt from the
    client-controlled Host header. scope["path"] is what the router dispatches on.
    """
    return request.scope.get("path", "")


class PasswordAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check password authentication for all API requests.

    Hardening added in the archival fork:
    - constant-time password comparison;
    - simple in-memory rate limiting per client IP;
    - optional temporary blocking after repeated failures;
    - optional trust of proxy headers only when explicitly enabled;
    - passwords with non-ASCII characters are compared as bytes;
    - the example passwords from the .env templates are refused;
    - requests without credentials are answered 401 but do not count towards
      the lockout (only wrong credentials do).
    """

    def __init__(self, app, excluded_paths: Optional[list] = None):
        super().__init__(app)
        self.password = get_secret_from_env("OPEN_NOTEBOOK_PASSWORD")
        self.password_is_placeholder = is_placeholder_secret(self.password)
        self.excluded_paths = excluded_paths or [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]
        self.max_attempts = _env_int("OPEN_NOTEBOOK_AUTH_MAX_ATTEMPTS", 10)
        self.window_seconds = _env_int("OPEN_NOTEBOOK_AUTH_WINDOW_SECONDS", 300)
        self.block_seconds = _env_int("OPEN_NOTEBOOK_AUTH_BLOCK_SECONDS", 600)
        self.failure_delay_ms = _env_int("OPEN_NOTEBOOK_AUTH_FAILURE_DELAY_MS", 400)
        self.trust_proxy_headers = _env_bool("OPEN_NOTEBOOK_TRUST_PROXY_HEADERS", False)
        self.failed_attempts: dict[str, list[float]] = {}
        self.blocked_until: dict[str, float] = {}

    def _client_ip(self, request: Request) -> str:
        if self.trust_proxy_headers:
            forwarded_for = request.headers.get("x-forwarded-for", "").strip()
            if forwarded_for:
                return forwarded_for.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def _prune_old_attempts(self, client_ip: str, now: float) -> None:
        attempts = self.failed_attempts.get(client_ip, [])
        fresh_attempts = [ts for ts in attempts if now - ts <= self.window_seconds]
        if fresh_attempts:
            self.failed_attempts[client_ip] = fresh_attempts
        elif client_ip in self.failed_attempts:
            del self.failed_attempts[client_ip]

        blocked_until = self.blocked_until.get(client_ip)
        if blocked_until and blocked_until <= now:
            del self.blocked_until[client_ip]

    def _record_failure(self, client_ip: str, now: float) -> None:
        attempts = self.failed_attempts.get(client_ip, [])
        attempts.append(now)
        self.failed_attempts[client_ip] = attempts
        self._prune_old_attempts(client_ip, now)
        if len(self.failed_attempts.get(client_ip, [])) >= self.max_attempts:
            self.blocked_until[client_ip] = now + self.block_seconds

    async def dispatch(self, request: Request, call_next):
        if not host_header_is_valid(request.headers.get("host")):
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Host header"},
            )

        if not self.password:
            # This path is only reachable if OPEN_NOTEBOOK_ALLOW_NO_PASSWORD=true
            # was set explicitly. The lifespan check in main.py blocks startup
            # without a password by default.
            return await call_next(request)

        if request_path(request) in self.excluded_paths:
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        if self.password_is_placeholder:
            # The configured password is the public example value from the
            # .env templates: refuse to serve protected data until it is changed.
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "OPEN_NOTEBOOK_PASSWORD still holds the example value from "
                        "the .env template. Set a real password and restart."
                    )
                },
            )

        client_ip = self._client_ip(request)
        now = time.time()
        self._prune_old_attempts(client_ip, now)

        blocked_until = self.blocked_until.get(client_ip)
        if blocked_until and blocked_until > now:
            retry_after = max(1, int(blocked_until - now))
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many failed authentication attempts"},
                headers={"Retry-After": str(retry_after)},
            )

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            # Not a password guess: do not count it towards the lockout.
            # Behind Docker every client shares one source IP, so counting
            # these let any web page lock the legitimate user out simply by
            # firing unauthenticated requests at the API.
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            scheme, credentials = auth_header.split(" ", 1)
            if scheme.lower() != "bearer":
                raise ValueError("Invalid authentication scheme")
        except ValueError:
            self._record_failure(client_ip, now)
            await asyncio.sleep(self.failure_delay_ms / 1000)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authorization header format"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not secrets_match(credentials, self.password):
            self._record_failure(client_ip, now)
            await asyncio.sleep(self.failure_delay_ms / 1000)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid password"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        self.failed_attempts.pop(client_ip, None)
        self.blocked_until.pop(client_ip, None)
        return await call_next(request)


security = HTTPBearer(auto_error=False)


def check_api_password(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> bool:
    """
    Utility function to check API password.
    Returns True without checking credentials if OPEN_NOTEBOOK_PASSWORD is not configured.
    Raises 401 if credentials are missing or don't match the configured password.
    """
    password = get_secret_from_env("OPEN_NOTEBOOK_PASSWORD")

    if not password:
        return True

    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if is_placeholder_secret(password) or not secrets_match(credentials.credentials, password):
        raise HTTPException(
            status_code=401,
            detail="Invalid password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True
