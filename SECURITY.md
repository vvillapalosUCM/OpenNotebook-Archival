# Security Policy

## Scope and threat model

**OpenNotebook-Archival** is a hardened fork of
[`lfnovo/open-notebook`](https://github.com/lfnovo/open-notebook)
designed for a **single local user on a single machine**, with local
LLM inference (Ollama) or a local OpenAI-compatible endpoint.

The hardening work — container capability dropping, rate limiting,
SSRF guards, injection validation, etc. — is built around that
assumption. Before filing a security report, please check that your
concern fits inside the threat model below. A finding that only
applies outside this scope is not necessarily a bug; it may simply
be a deployment mode the fork does not try to support.

### What this fork tries to protect against

- **Local malware / other processes on the same machine** reading
  database contents or credentials at rest. The entry-point password
  is never written to disk in the clear after install; the per-install
  encryption key protects credentials stored in SurrealDB.
- **Accidental LAN exposure.** All listening ports
  (`127.0.0.1:5055`, `127.0.0.1:8502`) are bound to loopback. SurrealDB
  publishes **no** ports; it is reachable only through the Docker
  internal network.
- **Host-escape via container vulnerability.** Both services run with
  `no-new-privileges`, `cap_drop: [ALL]`, `pids_limit`, memory and CPU
  limits, and named volumes rather than bind mounts.
- **Brute-force against the entry password.** Constant-time comparison
  (`hmac.compare_digest`), per-IP rate limiting (10 attempts / 5 min,
  10-minute block), artificial delay on failure.
- **Cross-site fingerprinting and scripting.**
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`, restrictive
  `Permissions-Policy`, CORS locked to a configurable origin allowlist
  (default: `http://127.0.0.1:8502`), Swagger / ReDoc disabled
  unless explicitly enabled.
- **Backend version fingerprinting** before authentication. The public
  `/api/config` endpoint only exposes database status; the version
  moved to `/api/config/version`, which requires the entry password.
- **SSRF via misconfigured LLM endpoints.** Hostnames pointing at
  link-local addresses (`169.254.0.0/16`, including
  `::ffff:169.254.169.254`) are rejected. DNS resolution is re-checked
  to catch hostnames that resolve to link-local or private ranges
  unless `OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS=true` is set.
- **SurrealQL injection** through dynamic query building: interpolated
  identifiers and ORDER-BY clauses are validated against allowlists
  before insertion; user data uses parameterised queries.
- **Path traversal** on source-file download: resolved paths outside
  the uploads directory are rejected.
- **Oversized uploads** (default limit 50 MB, configurable).

### What this fork does NOT try to protect against

The following are **out of scope** — reports about them will most
likely be closed as "working as intended for this deployment profile":

- **Multi-user or multi-tenant deployments.** There is one password;
  anyone who knows it has full access. There are no per-user
  permissions, audit logs, or session management beyond the in-memory
  rate limiter.
- **Exposure to the public internet.** If you bind the ports to
  `0.0.0.0` or put this behind a reverse proxy on a public address,
  you are operating outside the supported profile. At minimum you
  will want: TLS termination, a stronger auth story than a single
  bearer password, a persistent rate limiter (current one is
  in-memory and resets on restart), and audit logging.
- **A compromised host.** If malware has local shell access or the
  local user account is compromised, all bets are off: the attacker
  can read the `settings.env` that contains the entry password.
- **Physical access to an unlocked machine.**
- **Upstream dependency CVEs** (FastAPI, Next.js, Ollama, SurrealDB,
  etc.). Dependency updates are tracked separately via Dependabot;
  this policy covers bugs in code added or modified by the fork.
- **Supply-chain attacks against the image registry or base images.**
  Reproducible-build guarantees are not claimed.
- **Timing side-channels beyond password comparison**, cache attacks,
  Spectre-class CPU issues, etc.
- **Denial of service** as long as it only affects the local user who
  is already running the stack. A fork bomb limited by `pids_limit`
  may still make the laptop slow; that is a resource-limit tuning
  question, not a security bug.

### Deployment assumptions you must respect

The security posture above only holds if:

1. You keep the fork on a **single local machine** and do not expose
   its ports to the network.
2. You let the installer generate credentials for you, or you set
   equivalently strong ones. `OPEN_NOTEBOOK_PASSWORD` is the only
   authentication gate.
3. You keep `deployment/windows/runtime/` out of the repo
   (enforced by `.gitignore`), out of cloud backups that you share,
   and out of version control.
4. You do **not** set `OPEN_NOTEBOOK_ALLOW_NO_PASSWORD=true` on a
   machine that is reachable from anywhere except your own user
   account.
5. You only point LLM endpoints (`OLLAMA_API_BASE`,
   `OPENAI_COMPATIBLE_BASE_URL`) at hosts you control.

## Supported versions

The fork is new and does not yet have a first tagged release. Once
`v0.1.0` ships, the support policy will be:

- **Latest minor release**: security fixes, bug fixes, documentation.
- **Earlier releases**: not supported. Upgrading is expected to be
  cheap — the whole stack is reinstalled from a clean image.

This section will be updated when the first release is tagged.

## Reporting a vulnerability

If you believe you have found a security issue inside the scope
described above, please **do not open a public GitHub issue**. Instead:

1. Open a **private security advisory** on GitHub:
   <https://github.com/vvillapalosUCM/OpenNotebook-Archival/security/advisories/new>
   This is the preferred channel — the conversation stays private,
   is tied to the repo, and GitHub will assign a CVE if appropriate.
2. Include: the commit or release you tested against, the steps to
   reproduce, the impact you believe the issue has, and whether you
   have seen it exploited in the wild.
3. Please give the maintainer **at least 30 days** to respond before
   any public disclosure. A first acknowledgement should normally
   arrive within 7 days.

For issues in upstream Open Notebook that also affect this fork,
please file them against
[`lfnovo/open-notebook`](https://github.com/lfnovo/open-notebook/security/advisories)
as well.

## Known limitations we do not consider "vulnerabilities"

- **The entry password travels as `Authorization: Bearer <password>`**
  rather than as an opaque session token. This is intentional within
  the single-user-local threat model. A rotating-token scheme would
  mostly help against XSS that can read `sessionStorage`, and CSP is
  a more effective mitigation for that — tracked as future work.
- **The rate limiter is in-memory.** Restarting the container clears
  its state. This is acceptable locally and deliberately not fixed
  with Redis or a persistent store.
- **The SurrealDB service runs as root inside its container.** It is
  required because the distroless image's default non-root user
  cannot create the RocksDB directory on a fresh named volume. The
  risk is compensated by `cap_drop: [ALL]`, `no-new-privileges`,
  unpublished ports, and the lack of a shell in the distroless image.

## Credits

Thanks in advance to anyone who takes the time to evaluate and
report issues responsibly. If you'd like to be credited in a
resulting advisory or release notes, let us know in your report.
