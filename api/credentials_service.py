"""
Credentials Service for the archival fork.

Only local-first providers are allowed:
- Ollama
- OpenAI-compatible local endpoints
"""

import os
from typing import Dict, List
from urllib.parse import urlparse

import httpx
from loguru import logger
from pydantic import SecretStr

from api.models import CredentialResponse
from open_notebook.archival.local_only_policy import (
    ALLOWED_PROVIDERS,
    assert_local_only_provider,
    assert_local_only_url,
    is_local_or_private_url,
)
from open_notebook.domain.credential import Credential
from open_notebook.utils.encryption import get_secret_from_env

PROVIDER_ENV_CONFIG: Dict[str, dict] = {
    "ollama": {"required": ["OLLAMA_API_BASE"]},
    "openai_compatible": {
        "required": ["OPENAI_COMPATIBLE_BASE_URL"],
        "optional": ["OPENAI_COMPATIBLE_API_KEY"],
    },
}

PROVIDER_MODALITIES: Dict[str, List[str]] = {
    "ollama": ["language", "embedding"],
    "openai_compatible": ["language", "embedding"],
}


def validate_url(url: str, provider: str) -> None:
    assert_local_only_provider(provider)
    if not url or not url.strip():
        return

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https are allowed.")
    if not parsed.hostname:
        raise ValueError("Invalid URL: hostname could not be determined.")
    if not is_local_or_private_url(url):
        raise ValueError("This archival fork only allows local or private-network endpoints.")
    assert_local_only_url(url, provider)


def require_encryption_key() -> None:
    if not get_secret_from_env("OPEN_NOTEBOOK_ENCRYPTION_KEY"):
        raise ValueError(
            "Encryption key not configured. Set OPEN_NOTEBOOK_ENCRYPTION_KEY to enable storing API keys."
        )


def credential_to_response(cred: Credential, model_count: int = 0) -> CredentialResponse:
    return CredentialResponse(
        id=cred.id or "",
        name=cred.name,
        provider=cred.provider,
        modalities=cred.modalities,
        base_url=cred.base_url,
        endpoint=cred.endpoint,
        api_version=cred.api_version,
        endpoint_llm=cred.endpoint_llm,
        endpoint_embedding=cred.endpoint_embedding,
        endpoint_stt=cred.endpoint_stt,
        endpoint_tts=cred.endpoint_tts,
        project=cred.project,
        location=cred.location,
        credentials_path=cred.credentials_path,
        has_api_key=cred.api_key is not None,
        created=str(cred.created) if cred.created else "",
        updated=str(cred.updated) if cred.updated else "",
        model_count=model_count,
    )


def check_env_configured(provider: str) -> bool:
    config = PROVIDER_ENV_CONFIG.get(provider)
    if not config:
        return False
    if "required" in config:
        return all(bool(os.environ.get(v, "").strip()) for v in config["required"])
    return False


def get_default_modalities(provider: str) -> List[str]:
    assert_local_only_provider(provider)
    return PROVIDER_MODALITIES.get(provider.lower(), ["language"])


def create_credential_from_env(provider: str) -> Credential:
    assert_local_only_provider(provider)
    modalities = get_default_modalities(provider)
    name = "Default (Migrated from env)"

    if provider == "ollama":
        base_url = os.environ.get("OLLAMA_API_BASE")
        validate_url(base_url, provider)
        return Credential(name=name, provider=provider, modalities=modalities, base_url=base_url)

    if provider == "openai_compatible":
        api_key = os.environ.get("OPENAI_COMPATIBLE_API_KEY")
        base_url = os.environ.get("OPENAI_COMPATIBLE_BASE_URL")
        validate_url(base_url, provider)
        return Credential(
            name=name,
            provider=provider,
            modalities=modalities,
            api_key=SecretStr(api_key) if api_key else None,
            base_url=base_url,
        )

    raise ValueError(f"Unsupported provider in archival fork: {provider}")


async def get_provider_status() -> dict:
    encryption_configured = bool(get_secret_from_env("OPEN_NOTEBOOK_ENCRYPTION_KEY"))
    configured: Dict[str, bool] = {}
    source: Dict[str, str] = {}

    for provider in ALLOWED_PROVIDERS:
        env_configured = check_env_configured(provider)
        try:
            db_credentials = await Credential.get_by_provider(provider)
            db_configured = len(db_credentials) > 0
        except Exception:
            db_configured = False

        configured[provider] = db_configured or env_configured
        source[provider] = "database" if db_configured else "environment" if env_configured else "none"

    return {
        "configured": configured,
        "source": source,
        "encryption_configured": encryption_configured,
    }


async def get_env_status() -> Dict[str, bool]:
    return {provider: check_env_configured(provider) for provider in ALLOWED_PROVIDERS}


async def test_credential(credential_id: str) -> dict:
    provider = "unknown"
    try:
        cred = await Credential.get(credential_id)
        provider = cred.provider.lower()
        assert_local_only_provider(provider)
        config = cred.to_esperanto_config()

        from open_notebook.ai.connection_tester import (
            _test_ollama_connection,
            _test_openai_compatible_connection,
        )

        if provider == "ollama":
            base_url = config.get("base_url", "http://localhost:11434")
            validate_url(base_url, provider)
            success, message = await _test_ollama_connection(base_url)
            return {"provider": provider, "success": success, "message": message}

        if provider == "openai_compatible":
            base_url = config.get("base_url")
            api_key = config.get("api_key")
            if not base_url:
                return {"provider": provider, "success": False, "message": "No base URL configured"}
            validate_url(base_url, provider)
            success, message = await _test_openai_compatible_connection(base_url, api_key)
            return {"provider": provider, "success": success, "message": message}

        return {"provider": provider, "success": False, "message": f"Provider not allowed: {provider}"}
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "unauthorized" in error_msg.lower():
            return {"provider": provider, "success": False, "message": "Invalid API key"}
        if "403" in error_msg or "forbidden" in error_msg.lower():
            return {"provider": provider, "success": False, "message": "API key lacks required permissions"}
        logger.debug(f"Test connection error for credential {credential_id}: {e}")
        truncated = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        return {"provider": provider, "success": False, "message": f"Error: {truncated}"}


async def discover_with_config(provider: str, config: dict) -> List[dict]:
    provider = provider.lower()
    assert_local_only_provider(provider)
    api_key = config.get("api_key")
    base_url = config.get("base_url")

    if provider == "ollama":
        ollama_url = base_url or "http://localhost:11434"
        validate_url(ollama_url, provider)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=10.0)
                response.raise_for_status()
                data = response.json()
                return [
                    {"name": m.get("name", ""), "provider": "ollama"}
                    for m in data.get("models", [])
                    if m.get("name")
                ]
        except Exception as e:
            logger.warning(f"Failed to discover Ollama models: {e}")
            return []

    if provider == "openai_compatible":
        if not base_url:
            return []
        validate_url(base_url, provider)
        try:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base_url.rstrip('/')}/models", headers=headers, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                return [
                    {"name": m.get("id", ""), "provider": "openai_compatible"}
                    for m in data.get("data", [])
                    if m.get("id")
                ]
        except Exception as e:
            logger.warning(f"Failed to discover openai_compatible models: {e}")
            return []

    raise ValueError(f"Provider not allowed for discovery: {provider}")


async def register_models(credential_id: str, models_data: list) -> dict:
    cred = await Credential.get(credential_id)
    assert_local_only_provider(cred.provider)

    from open_notebook.ai.models import Model
    from open_notebook.database.repository import repo_query

    existing_models = await repo_query(
        "SELECT string::lowercase(name) as name, string::lowercase(type) as type FROM model WHERE string::lowercase(provider) = $provider",
        {"provider": cred.provider.lower()},
    )
    existing_keys = {(m["name"], m["type"]) for m in existing_models}
    created = 0
    existing = 0

    for model_data in models_data:
        model_provider = (model_data.provider or cred.provider).lower()
        assert_local_only_provider(model_provider)
        key = (model_data.name.lower(), model_data.model_type.lower())
        if key in existing_keys:
            existing += 1
            continue

        new_model = Model(
            name=model_data.name,
            provider=model_provider,
            type=model_data.model_type,
            credential=cred.id,
        )
        await new_model.save()
        created += 1

    return {"created": created, "existing": existing}


async def migrate_from_provider_config() -> dict:
    logger.info("=== Starting ProviderConfig migration for archival fork ===")
    require_encryption_key()

    from open_notebook.domain.provider_config import ProviderConfig
    from open_notebook.ai.models import Model
    from open_notebook.database.repository import repo_query

    config = await ProviderConfig.get_instance()
    migrated = []
    skipped = []
    errors = []

    for provider, credentials_list in config.credentials.items():
        provider = provider.lower()
        if provider not in ALLOWED_PROVIDERS:
            skipped.append(f"{provider} (not allowed in archival fork)")
            continue

        for old_cred in credentials_list:
            try:
                existing = await Credential.get_by_provider(provider)
                names = [c.name for c in existing]
                if old_cred.name in names:
                    skipped.append(f"{provider}/{old_cred.name}")
                    continue

                if old_cred.base_url:
                    validate_url(old_cred.base_url, provider)

                new_cred = Credential(
                    name=old_cred.name,
                    provider=provider,
                    modalities=get_default_modalities(provider),
                    api_key=old_cred.api_key,
                    base_url=old_cred.base_url,
                    endpoint=old_cred.endpoint,
                    api_version=old_cred.api_version,
                    endpoint_llm=old_cred.endpoint_llm,
                    endpoint_embedding=old_cred.endpoint_embedding,
                    endpoint_stt=old_cred.endpoint_stt,
                    endpoint_tts=old_cred.endpoint_tts,
                    project=old_cred.project,
                    location=old_cred.location,
                    credentials_path=old_cred.credentials_path,
                )
                await new_cred.save()

                provider_models = await repo_query(
                    "SELECT * FROM model WHERE string::lowercase(provider) = $provider AND credential IS NONE",
                    {"provider": provider},
                )
                for model_data in provider_models:
                    model = Model(**model_data)
                    model.credential = new_cred.id
                    await model.save()

                migrated.append(f"{provider}/{old_cred.name}")
            except Exception as e:
                logger.error(f"[{provider}/{old_cred.name}] Migration FAILED: {type(e).__name__}: {e}", exc_info=True)
                errors.append(f"{provider}/{old_cred.name}: {e}")

    return {
        "message": f"Migration complete. Migrated {len(migrated)} credentials.",
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
    }


async def migrate_from_env() -> dict:
    logger.info("=== Starting environment variable migration for archival fork ===")
    require_encryption_key()

    from open_notebook.ai.models import Model
    from open_notebook.database.repository import repo_query

    migrated = []
    skipped = []
    not_configured = []
    errors = []

    for provider in sorted(ALLOWED_PROVIDERS):
        try:
            if not check_env_configured(provider):
                not_configured.append(provider)
                continue
            existing = await Credential.get_by_provider(provider)
            if existing:
                skipped.append(provider)
                continue

            cred = create_credential_from_env(provider)
            await cred.save()

            provider_models = await repo_query(
                "SELECT * FROM model WHERE string::lowercase(provider) = $provider AND credential IS NONE",
                {"provider": provider.lower()},
            )
            for model_data in provider_models:
                model = Model(**model_data)
                model.credential = cred.id
                await model.save()

            migrated.append(provider)
        except Exception as e:
            logger.error(f"[{provider}] Migration FAILED: {type(e).__name__}: {e}", exc_info=True)
            errors.append(f"{provider}: {e}")

    return {
        "message": f"Migration complete. Migrated {len(migrated)} providers.",
        "migrated": migrated,
        "skipped": skipped,
        "not_configured": not_configured,
        "errors": errors,
    }
