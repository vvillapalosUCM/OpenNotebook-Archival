"""Exercise Docker's real ignore/COPY semantics without building the application.

Run with Python 3.10+ and a running Linux Docker engine (BuildKit enabled).
Only tracked filenames are read from Git; their contents are replaced by dummy
data. No user settings, services, volumes, base images or package downloads are
needed. FROM scratch probes retain local COPY/WORKDIR instructions from the real
Dockerfiles; dependency installation and copies of compiled artifacts are outside
this test's scope. Temporary contexts/exports are removed on exit.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_MARKER = b"SYNTHETIC-PRIVATE-PACKAGING-CANARY"
PRIVATE_FILES = (
    ".env",
    ".env.local",
    "docker.env",
    "personal-notes.txt",
    ".git/config",
    ".codex/session.json",
    "deployment/windows/runtime/settings.env",
    "deployment/windows/runtime/diagnostico.txt",
    "deployment/windows/backups/settings.env",
    "deployment/windows/backups/export.json",
    "data/upload.txt",
    "notebook_data/document.pdf",
    "surreal_data/database.db",
    "api/.env",
    "api/nested/.env.local",
    "api/debug.log",
    "api/local.sqlite",
    "api/__pycache__/local.pyc",
    "commands/settings.env",
    "open_notebook/nested/runtime/diagnostico.txt",
    "open_notebook/backups/export.json",
    "prompts/.env",
    "frontend/.env.local",
    "frontend/.env.production.local",
    "frontend/public/.env",
    "frontend/private.key",
    "frontend/.npmrc",
    "api/.netrc",
    "api/.aws/credentials",
    "frontend/.next/private.js",
    "frontend/node_modules/local/private.js",
)
SOURCE_TREES = ("api/", "commands/", "open_notebook/", "prompts/", "frontend/")
SOURCE_SUFFIXES = {
    ".py", ".surrealql", ".jinja", ".ts", ".tsx", ".js", ".mjs", ".json",
    ".css", ".svg", ".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2", ".ttf",
}
METADATA = ("pyproject.toml", "uv.lock", ".python-version", "README.md", "LICENSE", "run_api.py")
SEED = "configs/archival/seed_transformations.json"
WAIT_SCRIPT = "scripts/wait-for-api.sh"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def prepare_context(context):
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT
    ).decode("utf-8").split("\0")
    tracked = [name for name in tracked if name]
    for name in tracked:
        path = context / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("public fixture: " + name + "\n", encoding="utf-8")
    for name in PRIVATE_FILES:
        path = context / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PRIVATE_MARKER + b"\n")
    (context / ".dockerignore").write_bytes((ROOT / ".dockerignore").read_bytes())
    return tracked


def make_probe(dockerfile):
    """Reuse local COPY commands verbatim; Docker interprets paths and globs."""
    lines = ["FROM scratch AS context-probe", "COPY . /context/"]
    stages = []
    copied_stages = set()
    stage = None
    source = re.sub(r"\\\r?\n", " ", dockerfile.read_text(encoding="utf-8"))
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        instruction, _, argument = line.partition(" ")
        instruction = instruction.upper()
        if instruction == "FROM":
            match = re.search(r"\sAS\s+(\S+)$", line, flags=re.IGNORECASE)
            require(match is not None, "Probe requires named Dockerfile stages")
            stage = match.group(1)
            stages.append(stage)
            lines.append("FROM scratch AS " + stage)
        elif instruction == "WORKDIR":
            lines.append(line)
        elif instruction == "COPY":
            if "--from=" not in argument:
                lines.append(line)
                copied_stages.add(stage)
        elif instruction in {"ADD", "ONBUILD"}:
            raise AssertionError("Extend packaging coverage before using " + instruction)
    require("runtime" in stages, "Missing runtime stage")
    lines.extend([
        "FROM scratch AS packaging-result",
        "COPY --from=context-probe /context/ /context/",
    ])
    # Export stages with local copies so Docker also checks builder COPY sources.
    # No RUN or
    # cross-stage compiled artifacts are executed/copied by this lightweight probe.
    lines.extend(
        "COPY --from=" + stage + " / /stages/" + stage + "/"
        for stage in stages if stage in copied_stages
    )
    return "\n".join(lines) + "\n"


def check_export(export, tracked, dockerfile_name):
    leaked = [
        path.relative_to(export).as_posix()
        for path in export.rglob("*")
        if path.is_file() and PRIVATE_MARKER in path.read_bytes()
    ]
    require(not leaked, "Private fixtures included: " + ", ".join(leaked))
    source_files = {
        name for name in tracked
        if name.startswith(SOURCE_TREES) and Path(name).suffix in SOURCE_SUFFIXES
    }
    required_context = source_files | set(METADATA) | {
        SEED, WAIT_SCRIPT, "supervisord.conf", "supervisord.single.conf",
    }
    missing_context = sorted(
        name for name in required_context if not (export / "context" / name).is_file()
    )
    require(not missing_context, "Missing build inputs: " + ", ".join(missing_context))
    required_runtime = {
        name for name in source_files if not name.startswith("frontend/")
    } | set(METADATA) | {SEED, WAIT_SCRIPT}
    missing_runtime = sorted(
        name for name in required_runtime
        if not (export / "stages/runtime/app" / name).is_file()
    )
    require(not missing_runtime, "Missing runtime inputs: " + ", ".join(missing_runtime))
    supervisor = "supervisord.single.conf" if dockerfile_name.endswith(".single") else "supervisord.conf"
    config = export / "stages/runtime/etc/supervisor/conf.d/supervisord.conf"
    require(config.is_file(), "Missing supervisor configuration")
    require(supervisor in config.read_text(encoding="utf-8"), "Wrong supervisor configuration")
    # Frontend should enter the final image only via the compiled standalone
    # output, never by accidentally restoring a broad COPY of the source tree.
    require(
        not (export / "stages/runtime/app/frontend/src").exists(),
        "Uncompiled frontend source copied into runtime",
    )


def main():
    subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL)
    env = dict(os.environ, DOCKER_BUILDKIT="1")
    with tempfile.TemporaryDirectory(prefix="on-packaging-") as directory:
        scratch = Path(directory)
        context = scratch / "context"
        context.mkdir()
        tracked = prepare_context(context)
        for name in ("Dockerfile", "Dockerfile.single"):
            require(
                not (ROOT / (name + ".dockerignore")).exists(),
                "Extend test coverage for Dockerfile-specific ignore rules",
            )
            (context / name).write_text(make_probe(ROOT / name), encoding="utf-8")
            export = scratch / (name + "-export")
            subprocess.run([
                "docker", "build", "--network=none", "--progress=plain",
                "--file", str(context / name),
                "--output", "type=local,dest=" + str(export), str(context),
            ], check=True, env=env)
            check_export(export, tracked, name)
            print("PASS: " + name + " context, private fixtures and runtime resources", flush=True)


if __name__ == "__main__":
    main()
