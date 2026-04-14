import asyncio
import os
import time
import tomllib
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from loguru import logger

from open_notebook.database.repository import repo_query
from open_notebook.utils.version_utils import (
    compare_versions,
    get_version_from_github_async,
)

router = APIRouter()

_version_cache: dict = {
    "latest_version": None,
    "has_update": False,
    "timestamp": 0,
    "check_failed": False,
}

VERSION_CACHE_TTL = 24 * 60 * 60
ENABLE_UPDATE_CHECK = os.environ.get("OPEN_NOTEBOOK_ENABLE_UPDATE_CHECK", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
VERSION_REPOSITORY_URL = os.environ.get(
    "OPEN_NOTEBOOK_VERSION_REPOSITORY_URL",
    "https://github.com/vvillapalosUCM/OpenNotebook-Archival",
).strip()
VERSION_REPOSITORY_BRANCH = os.environ.get(
    "OPEN_NOTEBOOK_VERSION_REPOSITORY_BRANCH",
    "main",
).strip() or "main"


def get_version() -> str:
    try:
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
            return pyproject.get("project", {}).get("version", "unknown")
    except Exception as e:
        logger.warning(f"Could not read version from pyproject.toml: {e}")
        return "unknown"


async def get_latest_version_cached(current_version: str) -> tuple[Optional[str], bool]:
    global _version_cache

    if not ENABLE_UPDATE_CHECK:
        return None, False

    cache_age = time.time() - _version_cache["timestamp"]
    if _version_cache["timestamp"] > 0 and cache_age < VERSION_CACHE_TTL:
        logger.debug(f"Using cached version check result (age: {cache_age:.0f}s)")
        return _version_cache["latest_version"], _version_cache["has_update"]

    if _version_cache["timestamp"] > 0:
        logger.info(f"Version cache expired (age: {cache_age:.0f}s), refreshing...")

    try:
        logger.info("Checking for latest version from GitHub...")
        latest_version = await get_version_from_github_async(
            VERSION_REPOSITORY_URL,
            VERSION_REPOSITORY_BRANCH,
        )
        logger.info(
            f"Latest version from GitHub: {latest_version}, Current version: {current_version}"
        )
        has_update = compare_versions(current_version, latest_version) < 0

        _version_cache["latest_version"] = latest_version
        _version_cache["has_update"] = has_update
        _version_cache["timestamp"] = time.time()
        _version_cache["check_failed"] = False

        logger.info(f"Version check complete. Update available: {has_update}")
        return latest_version, has_update

    except Exception as e:
        logger.warning(f"Version check failed: {e}")
        _version_cache["latest_version"] = None
        _version_cache["has_update"] = False
        _version_cache["timestamp"] = time.time()
        _version_cache["check_failed"] = True
        return None, False


async def check_database_health() -> dict:
    try:
        result = await asyncio.wait_for(repo_query("RETURN 1"), timeout=2.0)
        if result:
            return {"status": "online"}
        return {"status": "offline", "error": "Empty result"}
    except asyncio.TimeoutError:
        logger.warning("Database health check timed out after 2 seconds")
        return {"status": "offline", "error": "Health check timeout"}
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return {"status": "offline", "error": str(e)}


@router.get("/config")
async def get_config(request: Request):
    current_version = get_version()

    latest_version = None
    has_update = False

    if ENABLE_UPDATE_CHECK:
        try:
            latest_version, has_update = await get_latest_version_cached(current_version)
        except Exception as e:
            logger.error(f"Unexpected error during version check: {e}")

    db_health = await check_database_health()
    db_status = db_health["status"]

    if db_status == "offline":
        logger.warning(f"Database offline: {db_health.get('error', 'Unknown error')}")

    return {
        "version": current_version,
        "latestVersion": latest_version,
        "hasUpdate": has_update,
        "dbStatus": db_status,
        "updateCheckEnabled": ENABLE_UPDATE_CHECK,
    }
