# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **About this file.** This repository is a fork of
> [`lfnovo/open-notebook`](https://github.com/lfnovo/open-notebook). The
> section `[Unreleased]` below describes the **fork's work on top of
> upstream `v1.8.4`**, i.e. everything done since commit `1431a5f`
> (`chore(deps): bump tornado from 6.5.4 to 6.5.5`). The rest of the
> file preserves the full upstream history verbatim so readers can
> trace the lineage end to end.

## [Unreleased] — OpenNotebook-Archival fork

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
- **Security documentation**: `SECURITY.md` (public security policy and
  threat model) and `SECURITY_NOTES.md` (technical rationale for the
  hardening decisions), plus `docs/archival/06-deployment-hardening.md`.
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
  installation survives the transient named-pipe race when Docker Desktop
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

- **Pillow forced to >= 13.0.0** through `[tool.uv] override-dependencies`.
  The locked Pillow 11.3.0 carries 4 critical and 35 high advisories, and
  Dependabot could not upgrade it because moviepy 2.2.1 (pulled in by
  content-core and podcast-creator) declares `pillow<12`. That cap exists
  only for `TextClip`, which neither dependency uses; `AudioFileClip` and
  `concatenate_audioclips` were tested under Pillow 13. Drop the override
  once moviepy releases a version without the cap.
- **Development images published to the fork's own registry.**
  `build-dev.yml` and the `Makefile` still targeted upstream's
  `ghcr.io/lfnovo/open-notebook` and `lfnovo/open_notebook`, so publishing
  failed with `permission_denied`. They now use
  `ghcr.io/vvillapalosucm/opennotebook-archival`, like `build-and-release.yml`.
- **Authentication bypass via poisoned `Host` header** (CVE-2026-48710,
  GHSA-86qp-5c8j-p5mr). `PasswordAuthMiddleware` decided public paths
  with `request.url.path`, which Starlette < 1.0.1 rebuilds from the
  `Host` header: `Host: localhost:5055/docs?` let any request skip the
  password. Exemptions now use the real ASGI path (`scope["path"]`) and
  malformed `Host` headers are rejected with 400. Regression tests in
  `tests/api/test_auth_security.py`.
- **SSRF through redirects and DNS rebinding on source URLs.** The URL
  pre-check only looked at the submitted URL, while content-core follows
  redirects. New `open_notebook/utils/ssrf_guard.py` checks the address
  of every connection content-core opens (first request and each
  redirect hop) and refuses non-public destinations. Scoped to
  content-core, so local model providers are unaffected. Tests in
  `tests/test_ssrf_guard.py`.
- **Source URLs no longer sent to r.jina.ai by default.** The ingestion
  graph hard-coded content-core's `auto` URL engine, which forwards every
  URL to Jina. Default is now `simple` (local download); external engines
  are an explicit opt-in through `OPEN_NOTEBOOK_URL_ENGINE`.
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

- **Upstream Claude workflows** (`.github/workflows/claude.yml`,
  `claude-code-review.yml`). The review workflow ran on
  `pull_request_target`, checked out the external PR's code and exposed
  `CLAUDE_CODE_OAUTH_TOKEN` and `id-token: write` to it. The fork does
  not use them.
- **Tracking of local runtime and backup directories**
  (`deployment/windows/runtime/`, `deployment/windows/backups/`).
  These contain locally-generated credentials and must never reach
  the repository.

### Fork-commit mapping

For traceability, the categories above draw from the following commits
of this fork (oldest first):

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

---

# Upstream history — Open Notebook (`lfnovo/open-notebook`)

The entries below are preserved verbatim from the upstream project's
`CHANGELOG.md`. This fork branches off after `[1.8.4]`; anything done
after that in upstream is not yet integrated here.

## [1.8.4] - 2026-04-09

### Security
- Fix Remote Code Execution (RCE) via Jinja2 Server-Side Template Injection in transformations (CVSS 9.2 Critical)
- Fix arbitrary file write via path traversal in file upload (CVSS 7.0 High)
- Fix arbitrary file read via Local File Inclusion in source creation (CVSS 8.2 High)

### Dependencies
- Bump ai-prompter to >=0.4.0 (uses Jinja2 SandboxedEnvironment to prevent SSTI)

## [1.8.3] - 2026-04-07

### Security
- Fix SurrealDB injection via unsanitized `order_by` query parameter in `GET /api/notebooks` (CVSS 8.7 High)
- Add allowlist validation for sorting parameters in notebooks endpoint
- Replace f-string query interpolation with parameterized `$variable` binding in source chat and migration queries
- Add defensive validation in `get_all()` base method to prevent injection via `order_by` parameter

## [1.8.2] - 2026-04-06

### Added
- DashScope (Qwen) and MiniMax provider support via Esperanto v2.20.0 (#725)
- Source list auto-refresh after adding a new source via URL, file upload, or text (#721)

### Fixed
- Source asset persistence — failed sources now persist their asset (URL/file path), making them identifiable and retryable (#722)
- Source title preservation — user-set custom titles are no longer overwritten after background processing (#722)
- Credential cascade delete — deleting a credential now removes linked models instead of returning a 409 error (#722)
- Podcast directory names — uses UUID for episode directories, fixing filesystem errors with special characters (#666)
- Tiktoken offline handling — API no longer crashes in air-gapped environments (#622)
- SurrealDB healthcheck — removed incompatible healthcheck from Docker Compose (#656)
- Esperanto embedding fixes — base_url/api_key config issues across multiple embedding providers (#664, #665)

### Docs
- Deprecated single-container Docker image in favor of Docker Compose (#723)

### Dependencies
- Bump esperanto to >=2.20.0

## [1.8.1] - 2026-03-10

### Added
- i18n support for Bengali (bn-IN) (#643)
- Podcast language support via podcast-creator 0.12.0 (#645)
- Upgrade default Azure API version for model testing and fetching (#638)

### Fixed
- Tiktoken network errors in offline/air-gapped Docker deployments — pre-downloads encoding at build time (#264, #622)
- SurrealDB getting stuck (#656)

### Dependencies
- Bump esperanto to 2.19.5 (#657)
- Bump langgraph from 1.0.6 to 1.0.10rc1 (#658)
- Bump authlib from 1.6.6 to 1.6.7 (#649)
- Bump lxml-html-clean from 0.4.3 to 0.4.4 (#646)
- Bump rollup from 4.55.1 to 4.59.0 (#635)
- Bump minimatch in frontend (#634)
- Bump tar from 7.5.9 to 7.5.11 (#650, #659)

## [1.7.4] - 2026-02-18

### Fixed
- Embedding large documents (3MB+) fails with 413 Payload Too Large (#594)
- `generate_embeddings()` now batches texts in groups of 50 with per-batch retry, preventing provider payload limits from being exceeded
- 413 errors now classified with user-friendly message in error classifier
- Misleading "Created 0 embedded chunks" log in `process_source_command` — embedding is fire-and-forget, so the count was always 0; now logs "embedding submitted" instead

## [1.7.3] - 2026-02-17

### Added
- Retry button for failed podcast episodes in the UI (#211, #218)
- Error details displayed on failed podcast episodes (#185, #355)
- `POST /podcasts/episodes/{id}/retry` API endpoint for re-submitting failed episodes
- `error_message` field in podcast episode API responses

### Fixed
- Podcast generation failures now correctly marked as "failed" instead of "completed" (#300, #335)
- Disabled automatic retries for podcast generation to prevent duplicate episode records (#302)

### Dependencies
- Bump podcast-creator to >= 0.11.2
- Bump esperanto to >= 2.19.4

## [1.7.2] - 2026-02-16

### Added
- Error classification utility that maps LLM provider errors to user-friendly messages (#506)
- Global exception handlers in FastAPI for all custom exception types with proper HTTP status codes
- `getApiErrorMessage()` frontend helper that falls back to backend messages when no i18n mapping exists

### Fixed
- LLM errors (invalid API key, wrong model, rate limits) now show descriptive messages instead of "An unexpected error occurred" (#590)
- SSE streaming error events in source chat and ask hooks were swallowed by inner JSON parse catch blocks
- Transformation execution errors were caught and re-wrapped as generic 500s instead of using proper status codes
- Fail fast when source content extraction returns empty instead of retrying (#589)
- Chat input and message overflow with long unbroken strings (#588)
- Word-wrap overflow in source cards, note editor, inline edit, note titles, and dialog content (#588)
- Translation proxy shadowing `name` keys (#588)
- OpenAI-compatible provider name handling via Esperanto update (#583)

### Changed
- `ValueError` replaced with `ConfigurationError` in model provisioning for proper error classification
- `ConfigurationError` added to command retry `stop_on` lists to avoid retrying permanent config failures

### Dependencies
- Bump esperanto to 2.19.3 (#583)
- Bump podcast-creator to 0.9.1

## [1.7.1] - 2026-02-14

### Added
- French (fr-FR) language support (#581)
- CI test workflow and improved i18n validation (#580)
- Expose embed `command_id` in note API responses (#545)

### Fixed
- ElevenLabs TTS credential passthrough via Esperanto update (#578)
- Handle empty/whitespace source content without retry loop (#576)
- Increase transformation `max_tokens` and update Esperanto dep (#568)
- Turn the embedding field into optional (#557)

### Docs
- Fix docker container names in local setup guides (#577)

### Dependencies
- Bump langchain-core from 1.2.7 to 1.2.11 (#564)
- Bump cryptography from 46.0.3 to 46.0.5 (#563)

## [1.7.0] - 2026-02-10

### Added
- **Credential-Based Provider Management** (#477)
  - New Settings → API Keys page for managing AI provider credentials via the UI
  - Support for 14 providers: OpenAI, Anthropic, Google, Groq, Mistral, DeepSeek, xAI, OpenRouter, Voyage AI, ElevenLabs, Ollama, Azure OpenAI, OpenAI-Compatible, and Vertex AI
  - Secure storage of API keys in SurrealDB with field-level encryption (Fernet AES-128-CBC + HMAC-SHA256)
  - One-click connection testing, model discovery, and model registration per credential
  - Migration tool to import existing environment variable keys into the credential system
  - Azure OpenAI support with service-specific endpoints (LLM, Embedding, STT, TTS)
  - OpenAI-Compatible support with per-service URL configurations
  - Vertex AI support with project, location, and credentials path
  - Environment variable API keys deprecated in favor of Settings UI

- **Security Enhancements**
  - Docker secrets support via `_FILE` suffix pattern (e.g., `OPEN_NOTEBOOK_PASSWORD_FILE`)
  - Default encryption key derived from "0p3n-N0t3b0ok" for easy setup (change in production!)
  - Default password "open-notebook-change-me" for out-of-box experience (change in production!)
  - URL validation for SSRF protection - blocks private IPs and localhost (except for Ollama which runs locally)
  - Security warnings logged when using default credentials

- HTML clipboard detection for text sources (#426)
  - When pasting content, automatically detects HTML format (e.g., from Word, web pages)
  - Shows info message when HTML is detected, informing user it will be converted to Markdown
  - Preserves formatting that would be lost with plain text paste
  - Bump content-core to 0.11.0 for HTML to Markdown conversion support

- **Improved Getting Started Experience**
  - Simplified docker-compose.yml in repository root (single official file)
  - Added examples/ folder with ready-made configurations:
    - `docker-compose-ollama.yml` - Local AI with Ollama
    - `docker-compose-speaches.yml` - Local TTS/STT with Speaches
    - `docker-compose-full-local.yml` - 100% local setup (Ollama + Speaches)
  - Inline quick start in README (no need to navigate to docs)
  - Cross-references between docker-compose examples and documentation
  - .env.example template with all configuration options

### Fixed
- Azure form race condition: all configuration now saved in single atomic request
- Migration API "error error" display: added proper MigrationResult model with message field
- Connection tester for Ollama providers: improved error handling and URL validation
- SqliteSaver async compatibility issues in chat system (#509, #525, #538)
- Re-embedding failures with empty content (#513, #515)
- Deletion cascade for notes and sources (#77)
- YouTube content availability issues (#494)
- Large document embedding errors (#489)

### Security
- API keys are encrypted at rest using Fernet symmetric encryption
- Keys are never returned to the frontend, only configuration status
- SSRF protection prevents internal network access via URL validation

### Docs
- Complete documentation update for credential-based system across 25 files
- All quick-start, installation, and configuration guides now use Settings UI workflow
- Environment variable API key instructions moved to deprecated/legacy sections
- Fixed broken links in installation docs
- Added comprehensive examples/ folder with documented docker-compose configurations
- Updated local-tts.md and local-stt.md with links to ready-made examples

### Internationalization
- Added Russian (ru-RU) language support (#524)
- Added Italian (it-IT) language support (#508)

## [1.6.2] - 2026-01-24

### Fixed
- Connection error with llama.cpp and OpenAI-compatible providers (#465)
  - Bump Esperanto to 2.17.2 which fixes LangChain connection errors caused by garbage collection

## [1.6.1] - 2026-01-22

### Fixed
- "Failed to send message" error with unhelpful logs when chat model is not configured (#358)
  - Added detailed error logging with model selection context and full traceback
  - Improved error messages to guide users to Settings → Models
  - Added warnings when default models are not configured

### Docs
- Ollama troubleshooting: Added "Model Name Configuration" section emphasizing exact model names from `ollama list`
- Added troubleshooting entry for "Failed to send message" error with step-by-step solutions
- Updated AI Chat Issues documentation with model configuration guidance


## [1.6.0] - 2026-01-21

### Added
- Content-type aware text chunking with automatic HTML, Markdown, and plain text detection (#350, #142)
- Unified embedding generation with mean pooling for large content that exceeds model context limits
- Dedicated embedding commands: `embed_note`, `embed_insight`, `embed_source`
- New utility modules: `chunking.py` and `embedding.py` in `open_notebook/utils/`
- Japanese (ja-JP) language support (#450)

### Changed
- Embedding is now fire-and-forget: domain models submit embedding commands asynchronously after save
- `rebuild_embeddings_command` now delegates to individual embed_* commands instead of inline processing
- Chunk size reduced to 1500 characters for better compatibility with Ollama embedding models
- Bump Esperanto to 2.16 for increased Ollama context window support

### Removed
- Legacy embedding commands: `embed_single_item_command`, `embed_chunk_command`, `vectorize_source_command`
- `needs_embedding()` and `get_embedding_content()` methods from domain models
- `split_text()` function from text_utils (replaced by `chunk_text()` in chunking module)

### Fixed
- Embedding failures when content exceeds model context limits (#350, #142)
- Empty note titles when saving from chat (clean thinking tags from prompt graph output)
- Orphaned embedding/insight records when deleting sources (cascade delete)
- Search results crash with null parent_id (defensive frontend check)
- Database migration 10 cleans up existing orphaned records

## [1.5.2] - 2026-01-15

### Performance
- Improved source listing speed by 20-30x (#436, closes #351)
  - Added database indexes on `source` field for `source_insight` and `source_embedding` tables
  - Use SurrealDB `FETCH` clause for command status instead of N async calls

## [1.5.1] - 2026-01-15

### Fixed
- Podcast dialog infinite loop error caused by excessive translation Proxy accesses in loops
- Podcast dialog UI freezing when typing episode name or additional instructions
- Removed incorrect translation keys for user-defined episode profiles (user content should not be translated)

## [1.5.0] - 2026-01-15

### Added
- Internationalization (i18n) support with Chinese (Simplified and Traditional) translations (#371, closes #344, #349, #360)
- Frontend test infrastructure with Vitest (#371)
- Language toggle component for switching UI language (#371)
- Date localization using date-fns locales (#371)
- Error message translation system (#371)

### Fixed
- Accessibility improvements: added missing `id`, `name`, and `autoComplete` attributes to form inputs (#371)
- Added `DialogDescription` to dialogs for Radix UI accessibility compliance (#371)
- Fixed "Collapsible is changing from uncontrolled to controlled" warning in SettingsForm (#371)
- Fixed lint command for Next.js 16 compatibility (`eslint` instead of `next lint`)

### Changed
- Dockerfile optimizations: better layer caching, `--no-install-recommends` for smaller images (#371)
- Dockerfile.single refactored into 3 separate build stages for better caching (#371)

## [1.4.0] - 2026-01-14

### Added
- CTA button to empty state notebook list for better onboarding (#408)
- Offline deployment support for Docker containers (#414)

### Fixed
- Large file uploads (>10MB) by upgrading to Next.js 16 (#423)
- Orphaned uploaded files when sources are removed (#421)
- Broken documentation links to ai-providers.md (#419)
- ZIP support indication removed from UI (#418)
- Duplicate Claude Code workflow runs on PRs (#417)
- Claude Code review workflow now runs on PRs from forks (#416)

### Changed
- Upgraded Next.js from 15.4.10 to 16.1.1 (#423)
- Upgraded React from 19.1.0 to 19.2.3 (#423)
- Renamed `middleware.ts` to `proxy.ts` for Next.js 16 compatibility (#423)

### Dependencies
- next: 15.4.10 → 16.1.1
- react: 19.1.0 → 19.2.3
- react-dom: 19.1.0 → 19.2.3

## [1.2.4] - 2025-12-14

### Added
- Infinite scroll for notebook sources - no more 50 source limit (#325)
- Markdown table rendering in chat responses, search results, and insights (#325)

### Fixed
- Timeout errors with Ollama and local LLMs - increased to 10 minutes (#325)
- "Unable to Connect to API Server" on Docker startup - frontend now waits for API health check (#325, #315)
- SSL issues with langchain (#274)
- Query key consistency for source mutations to properly refresh infinite scroll (#325)
- Docker compose start-all flow (#323)

### Changed
- Timeout configuration now uses granular httpx.Timeout (short connect, long read) (#325)

### Dependencies
- Updated next.js to 15.4.10
- Updated httpx to >=0.27.0 for SSL fix
