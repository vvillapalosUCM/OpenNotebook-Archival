import asyncio
import hmac
import os
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


class PasswordAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check password authentication for all API requests.

    Hardening added in the archival fork:
    - constant-time password comparison;
    - simple in-memory rate limiting per client IP;
    - optional temporary blocking after repeated failures;
    - optional trust of proxy headers only when explicitly enabled.
    """

    def __init__(self, app, excluded_paths: Optional[list] = None):
        super().__init__(app)
        self.password = get_secret_from_env("OPEN_NOTEBOOK_PASSWORD")
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
        if not self.password:
            return await call_next(request)

        if request.url.path in self.excluded_paths:
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

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
            self._record_failure(client_ip, now)
            await asyncio.sleep(self.failure_delay_ms / 1000)
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

        if not hmac.compare_digest(credentials, self.password):
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

    if not hmac.compare_digest(credentials.credentials, password):
        raise HTTPException(
            status_code=401,
            detail="Invalid password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True
