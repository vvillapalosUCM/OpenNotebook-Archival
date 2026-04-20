# Changelog

All notable changes to **OpenNotebook-Archival** (this fork) are documented in
this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/).

The sections below describe the work done since the fork point — the last
commit merged from upstream [`lfnovo/open-notebook`](https://github.com/lfnovo/open-notebook)
is `1431a5f` (`chore(deps): bump tornado from 6.5.4 to 6.5.5 (#668)`).
Everything after that is specific to this fork.

## [Unreleased]

### Added

- **Windows first-class installer**. New `deployment/windows/` directory with
  self-contained installation and daily-use scripts. Includes:
  - `00-PRIMERA-INSTALACION.bat`, `01-ENCENDER.bat`, `02-APAGAR.bat`,
    `03-ACTUALIZAR.bat`, `06-DIAGNOSTICO.bat` and `MENU.bat` as the
    user-facing entry points.
  - Supporting PowerShell scripts under `deployment/windows/scripts/`
    (`Install.ps1`, `Start.ps1`, `Stop.ps1`, `Update.ps1`, `Diagnose.ps1`,
    `Common.ps1`).
  - `README-INSTALACION.md` and `README-USO-DIARIO.md` walking through
    first-time install and day-to-day usage.
  - `env.template` generating a local `runtime/settings.env` file with
    randomly-generated, non-trivial credentials.
- **Hardened Docker Compose profile for Windows** at
  `deployment/windows/docker-compose.windows.local.yml`. Scoped for a
  single-user local install (see SECURITY.md).
- **Spanish localisation (es-ES)** across the frontend, including login,
  errors, API-key configuration, connection-error overlay and setup banner.
- **Archival-oriented seed transformations** (`configs/archival/seed_transformations.json`
  + `open_notebook/seed_transformations.py`) loaded on first boot.
- **Provider allowlist** (`frontend/src/lib/archival/providerPolicy.ts`) that
  restricts the credential-configuration UI to Ollama and
  OpenAI-compatible local endpoints, reflecting the fork's archival-local
  focus.
- **Security documentation**: `SECURITY_NOTES.md` (technical rationale for
  the hardening decisions) and `docs/archival/06-deployment-hardening.md`.
- **Security test suite** under `tests/api/` (`test_auth_security.py`,
  `test_config_security.py`, `test_sources_security.py`).
- **`.env.hardened`** reference template with conservative defaults for
  authentication, rate limiting, CORS and upload limits.

### Changed

- **API-keys settings page rewritten** (`frontend/src/app/(dashboard)/settings/api-keys/page.tsx`).
  The original upstream page was ~1259 lines; the fork first strips it down
  and then rebuilds a UI aligned with the archival single-user scope.
- **Build pipeline restructured**. The Dockerfile now has three stages —
  `frontend-builder` (node:20-bookworm-slim), `builder` (Python 3.12 + uv)
  and `runtime` (Python 3.12 + Node 20 binary copied in). This unblocks
  Next.js 16 which requires Node ≥ 20; Debian Bookworm ships Node 18.
- **README** rewritten for the fork's audience and scope.
- **Configuration endpoint split** (`api/routers/config.py`, `api/main.py`).
  `GET /api/config` is now public and returns only `dbStatus` +
  `updateCheckEnabled`; backend version, update checks and related details
  moved to `GET /api/config/version`, which stays behind the auth middleware.
  This prevents unauthenticated version fingerprinting without breaking
  the pre-login UI shell.
- **Docker Compose base file** (`docker-compose.yml`) rewritten around
  the hardened profile (cap_drop, pids limit, tmpfs, named volumes,
  restrictive CORS defaults, no public docs by default).

### Fixed

- **Windows installer** — `$Args` parameter name in `Common.ps1` was
  shadowing the PowerShell automatic variable `$Args`, causing the
  splatting in `Invoke-Compose` to expand to an empty list and run
  `docker compose` with no sub-command. Renamed to `$ComposeArgs`.
- **Windows installer** — added a retry loop in `Assert-Docker` so the
  instalación survives the transient named-pipe race when Docker Desktop
  has just started.
- **Windows `.bat` encoding** — every entry-point batch file now forces
  `chcp 65001` and UTF-8 handling so the generated `settings.env`
  keeps valid accented characters and SurrealDB credentials.
- **Dockerfile `FROM` lines with inline comments** — Docker's parser
  was rejecting `FROM image:tag AS builder  # pinned` because the `#`
  counted as an extra argument. Comments moved to their own line.
- **SurrealDB healthcheck** — the previous `CMD-SHELL "exit 0"` could
  never run against the distroless `surrealdb/surrealdb:v2.1.4` image
  (no `/bin/sh`), leaving the container perpetually `unhealthy` and
  blocking dependent services. Replaced by the official
  `["CMD", "/surreal", "isready", "--endpoint", "http://localhost:8000"]`
  exec form.
- **SurrealDB `Permission denied` on first boot** — the distroless image
  runs as a non-root user by default, but Docker named volumes are
  created owned by root, so RocksDB could not create its directory.
  Added `user: root` (compensated by `cap_drop: [ALL]` and
  `no-new-privileges`).
- **`uv` cache permission error in `on-app`** — `uv run` tried to write
  to `$HOME/.cache/uv` (i.e. `/app/.cache/uv`) but `/app` is owned by
  root and the app runs as the non-root `notebook` user. Fixed with
  `ENV UV_CACHE_DIR=/tmp/uv-cache` and by adding `/app/.cache` to the
  `mkdir/chown notebook` layer.
- **Missing `curl` in runtime image** — `scripts/wait-for-api.sh` uses
  `curl -s -f` and silenced errors with `2>&1`, so a missing binary
  caused 60 silent retries and a 5-minute frontend startup delay.
  `curl` is now installed in the runtime stage.
- **Docker Compose `pids_limit` vs `deploy.resources.limits.pids`** —
  modern Compose rejects setting both independently. Moved the limit
  into `deploy.resources.limits.pids` alongside `memory` and `cpus`.
- **Frontend auth token storage mismatch**. `auth-store.ts` persists
  the token in `sessionStorage` (intentional: token is dropped when
  the browser tab closes), but five consumers were still reading
  `localStorage`:
  - `frontend/src/lib/api/client.ts` (axios request interceptor).
  - `frontend/src/lib/api/client.ts` (401 response interceptor cleanup).
  - `frontend/src/lib/api/search.ts`.
  - `frontend/src/lib/api/source-chat.ts`.
  - `frontend/src/components/podcasts/EpisodeCard.tsx`.
  The net effect was that every login appeared to succeed and then
  immediately bounced the user back to `/login` because no `Authorization`
  header was being sent on subsequent requests. All five sites now
  read from `sessionStorage`.
- **Infinite render loop in the model-discovery modal**
  (`frontend/src/app/(dashboard)/settings/api-keys/page.tsx`). The
  `useEffect` that invokes the discover mutation listed `discoverModels`
  (a React Query mutation object that is re-created on every render) and
  `credential.modalities` (array prop with unstable identity) in its
  dependency array, which together with `mutate()`-triggered state
  updates produced React error #185 ("Maximum update depth exceeded")
  and a storm of `POST /api/credentials/{id}/discover` requests. The
  two unstable values are now captured via `useRef`.
- **Source chat could only see document metadata**
  (`open_notebook/graphs/source_chat.py`,
  `open_notebook/utils/context_builder.py`). The source-chat graph was
  building a context with the default `inclusion_level="insights"`,
  producing ~36 tokens (title + insights only) regardless of document
  length — which explained the symptom "the model says the document
  only contains the title 'Memoria sedic 2025'". `ContextBuilder` now
  accepts a `source_inclusion_level` kwarg and the source-chat graph
  requests `"full content insights"`; `max_tokens=50000` still bounds
  the prompt for very long documents.
- **Frontend build** — `Dockerfile` / `supervisord.conf` adjustments so
  the Next.js 16 standalone bundle starts reliably on Windows Docker.
- **CRLF handling** — `.gitattributes` pins `*.sh` to LF so bash scripts
  baked into the image don't inherit Windows CRLF from a Windows
  checkout.

### Security

- **Container hardening** applied to both `surrealdb` and `open_notebook`
  services in both Compose files:
  - `security_opt: no-new-privileges:true`.
  - `cap_drop: [ALL]` on both services (defence-in-depth on `on-app`,
    which runs as the non-root `notebook` user anyway; neutralises
    kernel capabilities on `on-surrealdb`, which must run as root so
    RocksDB can write to its named volume).
  - `pids: 256` (SurrealDB) and `pids: 512` (open_notebook) inside
    `deploy.resources.limits` to prevent local fork-bomb amplification.
  - Memory and CPU limits.
  - SurrealDB runs in an isolated Docker network (`on_internal`) with
    **no ports published to the host**; only `open_notebook` can reach
    it via the Docker-internal DNS name `surrealdb:8000`.
  - `tmpfs: /tmp` on SurrealDB bounded to 64 MB.
- **Ports bound to `127.0.0.1`** only (frontend and API). Services are
  not accessible from the LAN.
- **Password-authentication middleware** (`api/auth.py`) extended with:
  - Constant-time password comparison (`hmac.compare_digest`).
  - In-memory per-IP rate limiting (10 attempts per 5 min, 10-minute
    block on exhaustion) with configurable thresholds via
    `OPEN_NOTEBOOK_AUTH_MAX_ATTEMPTS`, `_WINDOW_SECONDS`,
    `_BLOCK_SECONDS`, `_FAILURE_DELAY_MS`.
  - Artificial delay on failure (`_FAILURE_DELAY_MS`, default 400 ms)
    to slow down brute force.
  - Proxy-header IP trust opt-in only (`OPEN_NOTEBOOK_TRUST_PROXY_HEADERS`).
- **Security response headers** (`SecurityHeadersMiddleware`):
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`,
  `Permissions-Policy: camera=(), microphone=(), geolocation=()`.
- **API docs disabled by default**. `/docs`, `/openapi.json`, `/redoc`
  return 404 unless `OPEN_NOTEBOOK_PUBLIC_DOCS=true`.
- **CORS restricted to an explicit origin allowlist** configured via
  `OPEN_NOTEBOOK_ALLOWED_ORIGINS`; default: `http://127.0.0.1:8502`.
- **Unauthenticated version fingerprinting removed**. `/api/config`
  no longer reveals the backend version to unauthenticated callers;
  the detail moved to `/api/config/version`, which requires auth.
- **SSRF guard on outbound LLM endpoints**
  (`api/credentials_service.py`): blocks link-local (`169.254.0.0/16`)
  hostnames, resolves DNS and re-validates the target is not private
  unless `OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS=true`. Protects
  against attackers steering a misconfigured LLM-endpoint URL at cloud
  metadata services.
- **Upload size limit** configurable via
  `OPEN_NOTEBOOK_MAX_UPLOAD_BYTES` (default 50 MB), enforced in
  `api/routers/sources.py`.
- **Path-traversal protection** on source-file download: rejects paths
  that, once resolved, fall outside the uploads directory.
- **SurrealQL injection guards**: dynamic query building now routes
  interpolated identifiers and ORDER-BY clauses through
  `_validate_record_ref` / `_validate_identifier` / regex allowlists
  before interpolation; all user data uses parameterised queries
  (`$data`) (`open_notebook/database/repository.py`,
  `open_notebook/domain/base.py`).
- **Single-user-local mode enforced in the login UI** — the login form
  displays a banner warning that the install is intended for a single
  local user and must not be exposed as a network service.

### Removed

- **Tracking of local runtime and backup directories**
  (`deployment/windows/runtime/`, `deployment/windows/backups/`).
  These contain locally-generated credentials and must never reach
  the repository.

---

## Mapping to commits

For traceability, the categories above draw from the following commits
(oldest first):

| Commit  | Summary |
| ------- | --- |
| `62aa447` | `s1` — strip down `api-keys/page.tsx` (-1190 lines). |
| `e5dc820` | `s2` — archival fork seed: `configs/archival/`, `docs/archival/`, tests. |
| `2792fbe` | `s3` — rebuild `api-keys/page.tsx` (+1088 lines). |
| `c1403f0` | `s4` — `providerPolicy.ts` (allowlist of archival-friendly providers). |
| `eec6bba` | `feat: merge backend security hardening from archival-bootstrap` — auth / config / sources. |
| `f178b8b` | `s7` — Windows installer scaffold + es-ES locale. |
| `150ecc5`, `5f3269f` | `chore: stop tracking local runtime and backup data`. |
| `3e7f88d` | `fix: make frontend startup robust in Windows Docker builds` — `.gitattributes`, Dockerfile, supervisord. |
| `3ecc797` | `feat: improve Windows deployment startup checks and diagnostics`. |
| `405b076` | `s10` — cross-cutting refactor: Dockerfile, README, `api/main`, `api/routers/podcasts`, compose, `next.config`, `auth-store`, `.bat`. |
| `17063d4` | `S15` — `.env.hardened`, `SECURITY_NOTES.md`, hardened base compose. |
| `3cc2ca6` | `s16` — `.gitignore` tweaks. |
| `c29bb91` | `fix: parche de seguridad` — new Windows compose, Dockerfile hardening, expanded security notes. |
| `9e548df` | `S21` — `api/auth.py`, `api/main.py` validation; compose + frontend adjustments. |
| `3d3b148` | `S22` — README rewrite, `LoginForm`, `config/route.ts`, `.env.example`, layout. |
| `15cfd3c` | `S26` — seed transformations, es-ES translations, `system.jinja`, `repository.py` validation, `ConnectionErrorOverlay`, CI workflows. |
| `bd4931b` | `S28` — `.bat` UTF-8 handling, compose, `Common.ps1` credential handling. |
| `e97bcaa` | `s31` — compose + `Common.ps1` + `Install.ps1` tweaks. |
| `dbd4ead` | `s35` — Dockerfile refactor (Node 20 stage, curl, UV_CACHE_DIR), `Common.ps1` `$ComposeArgs` + Docker retry. |
| `8f11eb2` | `S40` — compose hardening (cap_drop, pids, healthcheck), split `/api/config`, `sessionStorage` alignment. |
| `0cb071d` | `s42` — fix infinite render loop in model-discovery modal; fix source-chat context builder. |
