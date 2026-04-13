"""
Credentials Router for the archival fork.

This fork only permits:
- Ollama
- OpenAI-compatible local endpoints
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import SecretStr

from api.credentials_service import (
    credential_to_response,
    discover_with_config,
    get_env_status as svc_get_env_status,
    get_provider_status,
    migrate_from_env as svc_migrate_from_env,
    migrate_from_provider_config as svc_migrate_from_provider_config,
    register_models,
    require_encryption_key,
    test_credential as svc_test_credential,
    validate_url,
)
from api.models import (
    CreateCredentialRequest,
    CredentialDeleteResponse,
    CredentialResponse,
    DiscoveredModelResponse,
    DiscoverModelsResponse,
    RegisterModelsRequest,
    RegisterModelsResponse,
    UpdateCredentialRequest,
)
from open_notebook.archival.local_only_policy import assert_local_only_provider
from open_notebook.domain.credential import Credential

router = APIRouter(prefix="/credentials", tags=["credentials"])


def _handle_value_error(e: ValueError, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=str(e))


@router.get("/status")
async def get_status():
    try:
        return await get_provider_status()
    except Exception as e:
        logger.error(f"Error fetching status: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch credential status")


@router.get("/env-status")
async def get_env_status():
    try:
        return await svc_get_env_status()
    except Exception as e:
        logger.error(f"Error checking env status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check environment status")


@router.get("", response_model=List[CredentialResponse])
async def list_credentials(provider: Optional[str] = Query(None, description="Filter by provider")):
    try:
        if provider:
            assert_local_only_provider(provider)
            credentials = await Credential.get_by_provider(provider)
        else:
            credentials = await Credential.get_all(order_by="provider, created")
            credentials = [
                cred for cred in credentials if cred.provider.lower() in {"ollama", "openai_compatible"}
            ]

        result = []
        for cred in credentials:
            models = await cred.get_linked_models()
            result.append(credential_to_response(cred, len(models)))
        return result
    except ValueError as e:
        raise _handle_value_error(e)
    except Exception as e:
        logger.error(f"Error listing credentials: {e}")
        raise HTTPException(status_code=500, detail="Failed to list credentials")


@router.get("/by-provider/{provider}", response_model=List[CredentialResponse])
async def list_credentials_by_provider(provider: str):
    try:
        assert_local_only_provider(provider)
        credentials = await Credential.get_by_provider(provider.lower())
        result = []
        for cred in credentials:
            models = await cred.get_linked_models()
            result.append(credential_to_response(cred, len(models)))
        return result
    except ValueError as e:
        raise _handle_value_error(e)
    except Exception as e:
        logger.error(f"Error listing credentials for {provider}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list credentials for provider")


@router.post("", response_model=CredentialResponse, status_code=201)
async def create_credential(request: CreateCredentialRequest):
    try:
        require_encryption_key()
        assert_local_only_provider(request.provider)
    except ValueError as e:
        raise _handle_value_error(e)

    for url_field in [
        request.base_url,
        request.endpoint,
        request.endpoint_llm,
        request.endpoint_embedding,
        request.endpoint_stt,
        request.endpoint_tts,
    ]:
        if url_field:
            try:
                validate_url(url_field, request.provider)
            except ValueError as e:
                raise _handle_value_error(e)

    try:
        cred = Credential(
            name=request.name,
            provider=request.provider.lower(),
            modalities=request.modalities,
            api_key=SecretStr(request.api_key) if request.api_key else None,
            base_url=request.base_url,
            endpoint=request.endpoint,
            api_version=request.api_version,
            endpoint_llm=request.endpoint_llm,
            endpoint_embedding=request.endpoint_embedding,
            endpoint_stt=request.endpoint_stt,
            endpoint_tts=request.endpoint_tts,
            project=request.project,
            location=request.location,
            credentials_path=request.credentials_path,
        )
        await cred.save()
        return credential_to_response(cred, 0)
    except Exception as e:
        logger.error(f"Error creating credential: {e}")
        raise HTTPException(status_code=500, detail="Failed to create credential")


@router.get("/{credential_id}", response_model=CredentialResponse)
async def get_credential(credential_id: str):
    try:
        cred = await Credential.get(credential_id)
        assert_local_only_provider(cred.provider)
        models = await cred.get_linked_models()
        return credential_to_response(cred, len(models))
    except ValueError as e:
        raise _handle_value_error(e)
    except Exception as e:
        logger.error(f"Error fetching credential {credential_id}: {e}")
        raise HTTPException(status_code=404, detail="Credential not found")


@router.put("/{credential_id}", response_model=CredentialResponse)
async def update_credential(credential_id: str, request: UpdateCredentialRequest):
    try:
        require_encryption_key()
        cred = await Credential.get(credential_id)
        assert_local_only_provider(cred.provider)
    except ValueError as e:
        raise _handle_value_error(e)

    for url_field in [
        request.base_url,
        request.endpoint,
        request.endpoint_llm,
        request.endpoint_embedding,
        request.endpoint_stt,
        request.endpoint_tts,
    ]:
        if url_field:
            try:
                validate_url(url_field, cred.provider)
            except ValueError as e:
                raise _handle_value_error(e)

    try:
        if request.name is not None:
            cred.name = request.name
        if request.modalities is not None:
            cred.modalities = request.modalities
        if request.api_key is not None:
            cred.api_key = SecretStr(request.api_key)
        if request.base_url is not None:
            cred.base_url = request.base_url or None
        if request.endpoint is not None:
            cred.endpoint = request.endpoint or None
        if request.api_version is not None:
            cred.api_version = request.api_version or None
        if request.endpoint_llm is not None:
            cred.endpoint_llm = request.endpoint_llm or None
        if request.endpoint_embedding is not None:
            cred.endpoint_embedding = request.endpoint_embedding or None
        if request.endpoint_stt is not None:
            cred.endpoint_stt = request.endpoint_stt or None
        if request.endpoint_tts is not None:
            cred.endpoint_tts = request.endpoint_tts or None
        if request.project is not None:
            cred.project = request.project or None
        if request.location is not None:
            cred.location = request.location or None
        if request.credentials_path is not None:
            cred.credentials_path = request.credentials_path or None

        await cred.save()
        models = await cred.get_linked_models()
        return credential_to_response(cred, len(models))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating credential {credential_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update credential")


@router.delete("/{credential_id}", response_model=CredentialDeleteResponse)
async def delete_credential(
    credential_id: str,
    migrate_to: Optional[str] = Query(None, description="Migrate linked models to this credential ID"),
):
    try:
        cred = await Credential.get(credential_id)
        assert_local_only_provider(cred.provider)
        linked_models = await cred.get_linked_models()
        deleted_models = 0

        if linked_models and migrate_to:
            target_cred = await Credential.get(migrate_to)
            assert_local_only_provider(target_cred.provider)
            for model in linked_models:
                model.credential = target_cred.id
                await model.save()
        elif linked_models:
            for model in linked_models:
                await model.delete()
                deleted_models += 1

        await cred.delete()
        return CredentialDeleteResponse(message="Credential deleted successfully", deleted_models=deleted_models)
    except ValueError as e:
        raise _handle_value_error(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting credential {credential_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete credential")


@router.post("/{credential_id}/test")
async def test_credential(credential_id: str):
    return await svc_test_credential(credential_id)


@router.post("/{credential_id}/discover", response_model=DiscoverModelsResponse)
async def discover_models_for_credential(credential_id: str):
    try:
        cred = await Credential.get(credential_id)
        assert_local_only_provider(cred.provider)
        config = cred.to_esperanto_config()
        provider = cred.provider.lower()
        discovered = await discover_with_config(provider, config)

        return DiscoverModelsResponse(
            credential_id=cred.id or "",
            provider=provider,
            discovered=[
                DiscoveredModelResponse(
                    name=d["name"],
                    provider=d["provider"],
                    description=d.get("description"),
                )
                for d in discovered
            ],
        )
    except ValueError as e:
        raise _handle_value_error(e)
    except Exception as e:
        logger.error(f"Error discovering models for credential {credential_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to discover models")


@router.post("/{credential_id}/register-models", response_model=RegisterModelsResponse)
async def register_models_for_credential(credential_id: str, request: RegisterModelsRequest):
    try:
        result = await register_models(credential_id, request.models)
        return RegisterModelsResponse(**result)
    except ValueError as e:
        raise _handle_value_error(e)
    except Exception as e:
        logger.error(f"Error registering models for credential {credential_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to register models")


@router.post("/migrate-from-provider-config")
async def migrate_from_provider_config():
    try:
        return await svc_migrate_from_provider_config()
    except ValueError as e:
        raise _handle_value_error(e)
    except Exception as e:
        logger.error(f"ProviderConfig migration FAILED: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Migration from provider config failed")


@router.post("/migrate-from-env")
async def migrate_from_env():
    try:
        return await svc_migrate_from_env()
    except ValueError as e:
        raise _handle_value_error(e)
    except Exception as e:
        logger.error(f"Env migration FAILED: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Migration from environment variables failed")
