"""
Model discovery for the archival fork.

This fork only discovers models from:
- Ollama
- OpenAI-compatible local or private-network endpoints
"""

import asyncio
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import httpx
from loguru import logger

from open_notebook.ai.models import Model
from open_notebook.archival.local_only_policy import (
    ALLOWED_PROVIDERS,
    assert_local_only_provider,
    assert_local_only_url,
)
from open_notebook.database.repository import repo_query
from open_notebook.domain.credential import Credential


@dataclass
class DiscoveredModel:
    name: str
    provider: str
    model_type: str
    description: Optional[str] = None


OLLAMA_MODEL_TYPES = {
    "language": [
        "llama", "mistral", "mixtral", "codellama", "phi", "gemma", "qwen",
        "deepseek", "vicuna", "falcon", "orca", "neural", "dolphin",
        "openchat", "starling", "solar", "yi", "nous", "wizard", "zephyr", "tinyllama",
    ],
    "embedding": ["nomic-embed", "mxbai-embed", "all-minilm", "bge-", "e5-"],
}

OPENAI_COMPATIBLE_MODEL_TYPES = {
    "embedding": ["embedding", "embed", "bge-", "e5-", "nomic-embed", "mxbai-embed"],
    "language": [],
}


def classify_model_type(model_name: str, provider: str) -> str:
    name_lower = model_name.lower()
    type_mappings = {
        "ollama": OLLAMA_MODEL_TYPES,
        "openai_compatible": OPENAI_COMPATIBLE_MODEL_TYPES,
        "openai": OPENAI_COMPATIBLE_MODEL_TYPES,
    }
    mapping = type_mappings.get(provider, {})
    for model_type in ["embedding", "language"]:
        for pattern in mapping.get(model_type, []):
            if pattern in name_lower:
                return model_type
    return "language"


async def discover_ollama_models() -> List[DiscoveredModel]:
    base_url = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
    assert_local_only_url(base_url, "ollama")
    models: List[DiscoveredModel] = []

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url.rstrip('/')}/api/tags", timeout=10.0)
            response.raise_for_status()
            data = response.json()
            for model in data.get("models", []):
                model_name = model.get("name", "")
                if model_name:
                    models.append(
                        DiscoveredModel(
                            name=model_name,
                            provider="ollama",
                            model_type=classify_model_type(model_name, "ollama"),
                        )
                    )
    except Exception as e:
        logger.warning(f"Failed to discover Ollama models: {e}")

    return models


async def discover_openai_compatible_models() -> List[DiscoveredModel]:
    api_key = None
    base_url = None

    try:
        credentials = await Credential.get_by_provider("openai_compatible")
        if credentials:
            cred = credentials[0]
            config = cred.to_esperanto_config()
            api_key = config.get("api_key")
            base_url = config.get("base_url", "").rstrip("/")
    except Exception as e:
        logger.warning(f"Failed to read openai_compatible config from Credential: {e}")

    if not api_key:
        api_key = os.environ.get("OPENAI_COMPATIBLE_API_KEY")
    if not base_url:
        base_url = os.environ.get("OPENAI_COMPATIBLE_BASE_URL", "").rstrip("/")

    if not base_url:
        logger.warning("No base_url configured for openai_compatible provider")
        return []

    assert_local_only_url(base_url, "openai_compatible")
    models: List[DiscoveredModel] = []

    try:
        async with httpx.AsyncClient() as client:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            response = await client.get(f"{base_url}/models", headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            for model in data.get("data", []):
                model_id = model.get("id", "")
                if model_id:
                    models.append(
                        DiscoveredModel(
                            name=model_id,
                            provider="openai_compatible",
                            model_type=classify_model_type(model_id, "openai_compatible"),
                        )
                    )
    except httpx.HTTPStatusError as e:
        logger.warning(f"Failed to discover openai_compatible models: HTTP {e.response.status_code}")
    except Exception as e:
        logger.warning(f"Failed to discover openai_compatible models: {e}")

    return models


PROVIDER_DISCOVERY_FUNCTIONS = {
    "ollama": discover_ollama_models,
    "openai_compatible": discover_openai_compatible_models,
}


async def discover_provider_models(provider: str) -> List[DiscoveredModel]:
    provider = provider.lower()
    assert_local_only_provider(provider)
    discover_func = PROVIDER_DISCOVERY_FUNCTIONS.get(provider)
    if discover_func is None:
        logger.warning(f"No discovery function for provider: {provider}")
        return []
    return await discover_func()


async def sync_provider_models(provider: str, auto_register: bool = True) -> Tuple[int, int, int]:
    provider = provider.lower()
    assert_local_only_provider(provider)
    discovered = await discover_provider_models(provider)
    discovered_count = len(discovered)
    new_count = 0
    existing_count = 0

    if not auto_register or not discovered:
        return discovered_count, 0, 0

    try:
        existing_models = await repo_query(
            "SELECT string::lowercase(name) as name, string::lowercase(type) as type FROM model WHERE string::lowercase(provider) = $provider",
            {"provider": provider},
        )
        existing_keys = {(m.get("name", ""), m.get("type", "")) for m in existing_models}
    except Exception as e:
        logger.warning(f"Failed to fetch existing models for {provider}: {e}")
        existing_keys = set()

    for model in discovered:
        model_key = (model.name.lower(), model.model_type.lower())
        if model_key in existing_keys:
            existing_count += 1
            continue
        try:
            new_model = Model(name=model.name, provider=model.provider, type=model.model_type)
            await new_model.save()
            new_count += 1
            logger.info(f"Registered new model: {model.provider}/{model.name} ({model.model_type})")
        except Exception as e:
            logger.warning(f"Failed to register model {model.name}: {e}")

    logger.info(f"Synced {provider}: {discovered_count} discovered, {new_count} new, {existing_count} existing")
    return discovered_count, new_count, existing_count


async def sync_all_providers() -> Dict[str, Tuple[int, int, int]]:
    results: Dict[str, Tuple[int, int, int]] = {}
    providers = sorted(ALLOWED_PROVIDERS)
    task_results = await asyncio.gather(
        *[sync_provider_models(provider, auto_register=True) for provider in providers],
        return_exceptions=True,
    )

    for provider, result in zip(providers, task_results):
        if isinstance(result, Exception):
            logger.error(f"Error syncing {provider}: {result}")
            results[provider] = (0, 0, 0)
        else:
            results[provider] = result

    return results


async def get_provider_model_count(provider: str) -> Dict[str, int]:
    provider = provider.lower()
    assert_local_only_provider(provider)

    result = await repo_query(
        "SELECT type, count() as count FROM model WHERE string::lowercase(provider) = string::lowercase($provider) GROUP BY type",
        {"provider": provider},
    )

    counts = {"language": 0, "embedding": 0, "speech_to_text": 0, "text_to_speech": 0}
    for row in result:
        model_type = row.get("type")
        count = row.get("count", 0)
        if model_type in counts:
            counts[model_type] = count
    return counts
