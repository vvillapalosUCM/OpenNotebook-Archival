import asyncio
import ipaddress
import os
import socket
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse, Response
from loguru import logger
from surreal_commands import execute_command_sync, submit_command

from api.command_service import CommandService
from api.models import (
    AssetModel,
    CreateSourceInsightRequest,
    InsightCreationResponse,
    SourceCreate,
    SourceInsightResponse,
    SourceListResponse,
    SourceResponse,
    SourceStatusResponse,
    SourceUpdate,
)
from commands.source_commands import SourceProcessingInput
from open_notebook.config import UPLOADS_FOLDER
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import Asset, Notebook, Source
from open_notebook.domain.transformation import Transformation
from open_notebook.exceptions import InvalidInputError

router = APIRouter()

MAX_UPLOAD_BYTES = int(os.environ.get("OPEN_NOTEBOOK_MAX_UPLOAD_BYTES", 50 * 1024 * 1024))
ALLOW_PRIVATE_SOURCE_URLS = os.environ.get(
    "OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS", "false"
).strip().lower() in {"1", "true", "yes", "on"}


def generate_unique_filename(original_filename: str, upload_folder: str) -> str:
    """Generate unique filename like Streamlit app (append counter if file exists)."""
    file_path = Path(upload_folder)
    file_path.mkdir(parents=True, exist_ok=True)

    safe_filename = os.path.basename(original_filename)
    if not safe_filename:
        raise ValueError("Invalid filename")

    stem = Path(safe_filename).stem
    suffix = Path(safe_filename).suffix

    counter = 0
    while True:
        if counter == 0:
            new_filename = safe_filename
        else:
            new_filename = f"{stem} ({counter}){suffix}"

        full_path = file_path / new_filename
        resolved = full_path.resolve()
        if not str(resolved).startswith(str(file_path.resolve()) + os.sep):
            raise ValueError("Invalid filename: path traversal detected")
        if not resolved.exists():
            return str(resolved)
        counter += 1


def _is_private_or_local_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_source_url(url: str) -> None:
    """
    Basic SSRF protection for user-provided link sources.
    By default, private and local network targets are blocked.
    """
    if not url or not url.strip():
        raise ValueError("URL is required")

    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are allowed")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: hostname could not be determined")

    if ALLOW_PRIVATE_SOURCE_URLS:
        return

    localhost_names = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
    if hostname.lower() in localhost_names:
        raise ValueError("Local and loopback source URLs are not allowed")

    try:
        ip = ipaddress.ip_address(hostname)
        if _is_private_or_local_ip(str(ip)):
            raise ValueError("Private or local network source URLs are not allowed")
        return
    except ValueError as exc:
        if "not allowed" in str(exc):
            raise

    try:
        resolved_ips = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in resolved_ips:
            ip_addr = sockaddr[0]
            try:
                if _is_private_or_local_ip(ip_addr):
                    raise ValueError("Private or local network source URLs are not allowed")
            except ValueError as exc:
                if "not allowed" in str(exc):
                    raise
                continue
    except socket.gaierror:
        raise ValueError("Could not resolve source URL hostname")


async def save_uploaded_file(upload_file: UploadFile) -> str:
    """Save uploaded file to uploads folder and return file path."""
    if not upload_file.filename:
        raise ValueError("No filename provided")

    file_path = generate_unique_filename(upload_file.filename, UPLOADS_FOLDER)
    total_bytes = 0
    chunk_size = 1024 * 1024

    try:
        with open(file_path, "wb") as f:
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise ValueError(
                        f"File too large. Maximum allowed size is {MAX_UPLOAD_BYTES} bytes"
                    )
                f.write(chunk)

        try:
            os.chmod(file_path, 0o600)
        except Exception:
            pass

        logger.info(f"Saved uploaded file to: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        if os.path.exists(file_path):
            os.unlink(file_path)
        raise


def parse_source_form_data(
    type: str = Form(...),
    notebook_id: Optional[str] = Form(None),
    notebooks: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    transformations: Optional[str] = Form(None),
    embed: str = Form("false"),
    delete_source: str = Form("false"),
    async_processing: str = Form("false"),
    file: Optional[UploadFile] = File(None),
) -> tuple[SourceCreate, Optional[UploadFile]]:
    import json

    def str_to_bool(value: str) -> bool:
        return value.lower() in ("true", "1", "yes", "on")

    embed_bool = str_to_bool(embed)
    delete_source_bool = str_to_bool(delete_source)
    async_processing_bool = str_to_bool(async_processing)

    notebooks_list = None
    if notebooks:
        try:
            notebooks_list = json.loads(notebooks)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in notebooks field: {notebooks}")
            raise ValueError("Invalid JSON in notebooks field")

    transformations_list = []
    if transformations:
        try:
            transformations_list = json.loads(transformations)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in transformations field: {transformations}")
            raise ValueError("Invalid JSON in transformations field")

    try:
        source_data = SourceCreate(
            type=type,
            notebook_id=notebook_id,
            notebooks=notebooks_list,
            url=url,
            content=content,
            title=title,
            file_path=None,
            transformations=transformations_list,
            embed=embed_bool,
            delete_source=delete_source_bool,
            async_processing=async_processing_bool,
        )
    except Exception as e:
        logger.error(f"Failed to create SourceCreate instance: {e}")
        raise

    return source_data, file


@router.get("/sources", response_model=List[SourceListResponse])
async def get_sources(
    notebook_id: Optional[str] = Query(None, description="Filter by notebook ID"),
    limit: int = Query(50, ge=1, le=100, description="Number of sources to return (1-100)"),
    offset: int = Query(0, ge=0, description="Number of sources to skip"),
    sort_by: str = Query("updated", description="Field to sort by (created or updated)"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
):
    try:
        if sort_by not in ["created", "updated"]:
            raise HTTPException(status_code=400, detail="sort_by must be 'created' or 'updated'")
        if sort_order.lower() not in ["asc", "desc"]:
            raise HTTPException(status_code=400, detail="sort_order must be 'asc' or 'desc'")

        order_clause = f"ORDER BY {sort_by} {sort_order.upper()}"

        if notebook_id:
            notebook = await Notebook.get(notebook_id)
            if not notebook:
                raise HTTPException(status_code=404, detail="Notebook not found")

            query = f"""
                SELECT id, asset, created, title, updated, topics, command,
                (SELECT VALUE count() FROM source_insight WHERE source = $parent.id GROUP ALL)[0].count OR 0 AS insights_count,
                (SELECT VALUE id FROM source_embedding WHERE source = $parent.id LIMIT 1) != [] AS embedded
                FROM (select value in from reference where out=$notebook_id)
                {order_clause}
                LIMIT $limit START $offset
                FETCH command
            """
            result = await repo_query(
                query,
                {"notebook_id": ensure_record_id(notebook_id), "limit": limit, "offset": offset},
            )
        else:
            query = f"""
                SELECT id, asset, created, title, updated, topics, command,
                (SELECT VALUE count() FROM source_insight WHERE source = $parent.id GROUP ALL)[0].count OR 0 AS insights_count,
                (SELECT VALUE id FROM source_embedding WHERE source = $parent.id LIMIT 1) != [] AS embedded
                FROM source
                {order_clause}
                LIMIT $limit START $offset
                FETCH command
            """
            result = await repo_query(query, {"limit": limit, "offset": offset})

        response_list = []
        for row in result:
            command = row.get("command")
            command_id = None
            status = None
            processing_info = None

            if command and isinstance(command, dict):
                command_id = str(command.get("id")) if command.get("id") else None
                status = command.get("status")
                result_data = command.get("result")
                execution_metadata = result_data.get("execution_metadata", {}) if isinstance(result_data, dict) else {}
                processing_info = {
                    "started_at": execution_metadata.get("started_at"),
                    "completed_at": execution_metadata.get("completed_at"),
                    "error": command.get("error_message"),
                }
            elif command:
                command_id = str(command)
                status = "unknown"

            response_list.append(
                SourceListResponse(
                    id=row["id"],
                    title=row.get("title"),
                    topics=row.get("topics") or [],
                    asset=AssetModel(
                        file_path=row["asset"].get("file_path") if row.get("asset") else None,
                        url=row["asset"].get("url") if row.get("asset") else None,
                    ) if row.get("asset") else None,
                    embedded=row.get("embedded", False),
                    embedded_chunks=0,
                    insights_count=row.get("insights_count", 0),
                    created=str(row["created"]),
                    updated=str(row["updated"]),
                    command_id=command_id,
                    status=status,
                    processing_info=processing_info,
                )
            )

        return response_list
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching sources: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching sources: {str(e)}")


@router.post("/sources", response_model=SourceResponse)
async def create_source(
    form_data: tuple[SourceCreate, Optional[UploadFile]] = Depends(parse_source_form_data),
):
    source_data, upload_file = form_data
    file_path = None

    try:
        for notebook_id in source_data.notebooks or []:
            notebook = await Notebook.get(notebook_id)
            if not notebook:
                raise HTTPException(status_code=404, detail=f"Notebook {notebook_id} not found")

        if upload_file and source_data.type == "upload":
            try:
                file_path = await save_uploaded_file(upload_file)
            except Exception as e:
                logger.error(f"File upload failed: {e}")
                raise HTTPException(status_code=400, detail=f"File upload failed: {str(e)}")

        content_state: dict[str, Any] = {}

        if source_data.type == "link":
            if not source_data.url:
                raise HTTPException(status_code=400, detail="URL is required for link type")
            try:
                validate_source_url(source_data.url)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            content_state["url"] = source_data.url
        elif source_data.type == "upload":
            final_file_path = file_path or source_data.file_path
            if not final_file_path:
                raise HTTPException(status_code=400, detail="File upload or file_path is required for upload type")
            uploads_resolved = Path(UPLOADS_FOLDER).resolve()
            file_resolved = Path(final_file_path).resolve()
            if not str(file_resolved).startswith(str(uploads_resolved) + os.sep):
                raise HTTPException(status_code=400, detail="Invalid file path: must be within the uploads directory")
            content_state["file_path"] = final_file_path
            content_state["delete_source"] = source_data.delete_source
        elif source_data.type == "text":
            if not source_data.content:
                raise HTTPException(status_code=400, detail="Content is required for text type")
            content_state["content"] = source_data.content
        else:
            raise HTTPException(status_code=400, detail="Invalid source type. Must be link, upload, or text")

        transformation_ids = source_data.transformations or []
        for trans_id in transformation_ids:
            transformation = await Transformation.get(trans_id)
            if not transformation:
                raise HTTPException(status_code=404, detail=f"Transformation {trans_id} not found")

        if source_data.async_processing:
            logger.info("Using async processing path")

            if source_data.type == "link":
                source_asset = Asset(url=source_data.url)
            elif source_data.type == "upload":
                source_asset = Asset(file_path=file_path or source_data.file_path)
            else:
                source_asset = None

            source = Source(title=source_data.title or "Processing...", topics=[], asset=source_asset)
            await source.save()

            for notebook_id in source_data.notebooks or []:
                await source.add_to_notebook(notebook_id)

            try:
                import commands.source_commands  # noqa: F401

                command_input = SourceProcessingInput(
                    source_id=str(source.id),
                    content_state=content_state,
                    notebook_ids=source_data.notebooks,
                    transformations=transformation_ids,
                    embed=source_data.embed,
                )

                command_id = await CommandService.submit_command_job(
                    "open_notebook",
                    "process_source",
                    command_input.model_dump(),
                )

                logger.info(f"Submitted async processing command: {command_id}")
                source.command = ensure_record_id(command_id)
                await source.save()

                return SourceResponse(
                    id=source.id or "",
                    title=source.title,
                    topics=source.topics or [],
                    asset=None,
                    full_text=None,
                    embedded=False,
                    embedded_chunks=0,
                    created=str(source.created),
                    updated=str(source.updated),
                    command_id=command_id,
                    status="new",
                    processing_info={"async": True, "queued": True},
                )
            except Exception as e:
                logger.error(f"Failed to submit async processing command: {e}")
                try:
                    await source.delete()
                except Exception:
                    pass
                if file_path and upload_file:
                    try:
                        os.unlink(file_path)
                    except Exception:
                        pass
                raise HTTPException(status_code=500, detail=f"Failed to queue processing: {str(e)}")
        else:
            logger.info("Using sync processing path")

            try:
                import commands.source_commands  # noqa: F401

                source = Source(title=source_data.title or "Processing...", topics=[])
                await source.save()

                for notebook_id in source_data.notebooks or []:
                    await source.add_to_notebook(notebook_id)

                command_input = SourceProcessingInput(
                    source_id=str(source.id),
                    content_state=content_state,
                    notebook_ids=source_data.notebooks,
                    transformations=transformation_ids,
                    embed=source_data.embed,
                )

                result = await asyncio.to_thread(
                    execute_command_sync,
                    "open_notebook",
                    "process_source",
                    command_input.model_dump(),
                    timeout=300,
                )

                if not result.is_success():
                    logger.error(f"Sync processing failed: {result.error_message}")
                    try:
                        await source.delete()
                    except Exception:
                        pass
                    if file_path and upload_file:
                        try:
                            os.unlink(file_path)
                        except Exception:
                            pass
                    raise HTTPException(status_code=500, detail=f"Processing failed: {result.error_message}")

                if not source.id:
                    raise HTTPException(status_code=500, detail="Source ID is missing")
                processed_source = await Source.get(source.id)
                if not processed_source:
                    raise HTTPException(status_code=500, detail="Processed source not found")

                embedded_chunks = await processed_source.get_embedded_chunks()
                return SourceResponse(
                    id=processed_source.id or "",
                    title=processed_source.title,
                    topics=processed_source.topics or [],
                    asset=AssetModel(
                        file_path=processed_source.asset.file_path if processed_source.asset else None,
                        url=processed_source.asset.url if processed_source.asset else None,
                    ) if processed_source.asset else None,
                    full_text=processed_source.full_text,
                    embedded=embedded_chunks > 0,
                    embedded_chunks=embedded_chunks,
                    created=str(processed_source.created),
                    updated=str(processed_source.updated),
                )
            except Exception as e:
                logger.error(f"Sync processing failed: {e}")
                if file_path and upload_file:
                    try:
                        os.unlink(file_path)
                    except Exception:
                        pass
                raise
    except HTTPException:
        if file_path and upload_file:
            try:
                os.unlink(file_path)
            except Exception:
                pass
        raise
    except InvalidInputError as e:
        if file_path and upload_file:
            try:
                os.unlink(file_path)
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating source: {str(e)}")
        if file_path and upload_file:
            try:
                os.unlink(file_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Error creating source: {str(e)}")


@router.post("/sources/json", response_model=SourceResponse)
async def create_source_json(source_data: SourceCreate):
    form_data = (source_data, None)
    return await create_source(form_data)


async def _resolve_source_file(source_id: str) -> tuple[str, str]:
    source = await Source.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    file_path = source.asset.file_path if source.asset else None
    if not file_path:
        raise HTTPException(status_code=404, detail="Source has no file to download")

    safe_root = os.path.realpath(UPLOADS_FOLDER)
    resolved_path = os.path.realpath(file_path)

    if not resolved_path.startswith(safe_root + os.sep):
        logger.warning(f"Blocked download outside uploads directory for source {source_id}: {resolved_path}")
        raise HTTPException(status_code=403, detail="Access to file denied")

    if not os.path.exists(resolved_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    filename = os.path.basename(resolved_path)
    return resolved_path, filename


def _is_source_file_available(source: Source) -> Optional[bool]:
    if not source or not source.asset or not source.asset.file_path:
        return None

    file_path = source.asset.file_path
    safe_root = os.path.realpath(UPLOADS_FOLDER)
    resolved_path = os.path.realpath(file_path)

    if not resolved_path.startswith(safe_root + os.sep):
        return False

    return os.path.exists(resolved_path)


@router.get("/sources/{source_id}", response_model=SourceResponse)
async def get_source(source_id: str):
    try:
        source = await Source.get(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        status = None
        processing_info = None
        if source.command:
            try:
                status = await source.get_status()
                processing_info = await source.get_processing_progress()
            except Exception as e:
                logger.warning(f"Failed to get status for source {source_id}: {e}")
                status = "unknown"

        embedded_chunks = await source.get_embedded_chunks()
        notebooks_query = await repo_query(
            "SELECT VALUE out FROM reference WHERE in = $source_id",
            {"source_id": ensure_record_id(source.id or source_id)},
        )
        notebook_ids = [str(nb_id) for nb_id in notebooks_query] if notebooks_query else []

        return SourceResponse(
            id=source.id or "",
            title=source.title,
            topics=source.topics or [],
            asset=AssetModel(
                file_path=source.asset.file_path if source.asset else None,
                url=source.asset.url if source.asset else None,
            ) if source.asset else None,
            full_text=source.full_text,
            embedded=embedded_chunks > 0,
            embedded_chunks=embedded_chunks,
            file_available=_is_source_file_available(source),
            created=str(source.created),
            updated=str(source.updated),
            command_id=str(source.command) if source.command else None,
            status=status,
            processing_info=processing_info,
            notebooks=notebook_ids,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching source {source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching source: {str(e)}")


@router.head("/sources/{source_id}/download")
async def check_source_file(source_id: str):
    try:
        await _resolve_source_file(source_id)
        return Response(status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking file for source {source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to verify file")


@router.get("/sources/{source_id}/download")
async def download_source_file(source_id: str):
    try:
        resolved_path, filename = await _resolve_source_file(source_id)
        return FileResponse(path=resolved_path, filename=filename, media_type="application/octet-stream")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file for source {source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download source file")


@router.get("/sources/{source_id}/status", response_model=SourceStatusResponse)
async def get_source_status(source_id: str):
    try:
        source = await Source.get(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        if not source.command:
            return SourceStatusResponse(
                status=None,
                message="Legacy source (completed before async processing)",
                processing_info=None,
                command_id=None,
            )

        try:
            status = await source.get_status()
            processing_info = await source.get_processing_progress()

            if status == "completed":
                message = "Source processing completed successfully"
            elif status == "failed":
                message = "Source processing failed"
            elif status == "running":
                message = "Source processing in progress"
            elif status == "queued":
                message = "Source processing queued"
            elif status == "unknown":
                message = "Source processing status unknown"
            else:
                message = f"Source processing status: {status}"

            return SourceStatusResponse(
                status=status,
                message=message,
                processing_info=processing_info,
                command_id=str(source.command) if source.command else None,
            )
        except Exception as e:
            logger.warning(f"Failed to get status for source {source_id}: {e}")
            return SourceStatusResponse(
                status="unknown",
                message="Failed to retrieve processing status",
                processing_info=None,
                command_id=str(source.command) if source.command else None,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching status for source {source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching source status: {str(e)}")


@router.put("/sources/{source_id}", response_model=SourceResponse)
async def update_source(source_id: str, source_update: SourceUpdate):
    try:
        source = await Source.get(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        if source_update.title is not None:
            source.title = source_update.title
        if source_update.topics is not None:
            source.topics = source_update.topics

        await source.save()

        embedded_chunks = await source.get_embedded_chunks()
        return SourceResponse(
            id=source.id or "",
            title=source.title,
            topics=source.topics or [],
            asset=AssetModel(
                file_path=source.asset.file_path if source.asset else None,
                url=source.asset.url if source.asset else None,
            ) if source.asset else None,
            full_text=source.full_text,
            embedded=embedded_chunks > 0,
            embedded_chunks=embedded_chunks,
            created=str(source.created),
            updated=str(source.updated),
        )
    except HTTPException:
        raise
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating source {source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating source: {str(e)}")


@router.post("/sources/{source_id}/retry", response_model=SourceResponse)
async def retry_source_processing(source_id: str):
    try:
        source = await Source.get(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        if source.command:
            try:
                status = await source.get_status()
                if status in ["running", "queued"]:
                    raise HTTPException(status_code=400, detail="Source is already processing. Cannot retry while processing is active.")
            except Exception as e:
                logger.warning(f"Failed to check current status for source {source_id}: {e}")

        query = "SELECT notebook FROM reference WHERE source = $source_id"
        references = await repo_query(query, {"source_id": source_id})
        notebook_ids = [str(ref["notebook"]) for ref in references]

        if not notebook_ids:
            raise HTTPException(status_code=400, detail="Source is not associated with any notebooks")

        content_state = {}
        if source.asset:
            if source.asset.file_path:
                content_state = {"file_path": source.asset.file_path, "delete_source": False}
            elif source.asset.url:
                validate_source_url(source.asset.url)
                content_state = {"url": source.asset.url}
            else:
                raise HTTPException(status_code=400, detail="Source asset has no file_path or url")
        else:
            if source.full_text:
                content_state = {"content": source.full_text}
            else:
                raise HTTPException(status_code=400, detail="Cannot determine source content for retry")

        try:
            import commands.source_commands  # noqa: F401

            command_input = SourceProcessingInput(
                source_id=str(source.id),
                content_state=content_state,
                notebook_ids=notebook_ids,
                transformations=[],
                embed=True,
            )

            command_id = await CommandService.submit_command_job(
                "open_notebook",
                "process_source",
                command_input.model_dump(),
            )

            logger.info(f"Submitted retry processing command: {command_id} for source {source_id}")
            source.command = ensure_record_id(command_id)
            await source.save()

            embedded_chunks = await source.get_embedded_chunks()
            return SourceResponse(
                id=source.id or "",
                title=source.title,
                topics=source.topics or [],
                asset=AssetModel(
                    file_path=source.asset.file_path if source.asset else None,
                    url=source.asset.url if source.asset else None,
                ) if source.asset else None,
                full_text=source.full_text,
                embedded=embedded_chunks > 0,
                embedded_chunks=embedded_chunks,
                created=str(source.created),
                updated=str(source.updated),
                command_id=command_id,
                status="queued",
                processing_info={"retry": True, "queued": True},
            )
        except Exception as e:
            logger.error(f"Failed to submit retry processing command for source {source_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to queue retry processing: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying source processing for {source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrying source processing: {str(e)}")


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    try:
        source = await Source.get(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        await source.delete()
        return {"message": "Source deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting source {source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting source: {str(e)}")


@router.get("/sources/{source_id}/insights", response_model=List[SourceInsightResponse])
async def get_source_insights(source_id: str):
    try:
        source = await Source.get(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        insights = await source.get_insights()
        return [
            SourceInsightResponse(
                id=insight.id or "",
                source_id=source_id,
                insight_type=insight.insight_type,
                content=insight.content,
                created=str(insight.created),
                updated=str(insight.updated),
            )
            for insight in insights
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching insights for source {source_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching insights: {str(e)}")


@router.post("/sources/{source_id}/insights", response_model=InsightCreationResponse, status_code=202)
async def create_source_insight(source_id: str, request: CreateSourceInsightRequest):
    try:
        source = await Source.get(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        transformation = await Transformation.get(request.transformation_id)
        if not transformation:
            raise HTTPException(status_code=404, detail="Transformation not found")

        command_id = submit_command(
            "open_notebook",
            "run_transformation",
            {"source_id": source_id, "transformation_id": request.transformation_id},
        )
        logger.info(f"Submitted run_transformation command {command_id} for source {source_id}")

        return InsightCreationResponse(
            status="pending",
            message="Insight generation started",
            source_id=source_id,
            transformation_id=request.transformation_id,
            command_id=str(command_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting insight generation for source {source_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting insight generation: {str(e)}")
