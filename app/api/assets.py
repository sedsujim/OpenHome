from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.exceptions import IconProcessingError
from app.models.schemas import MotdPayload
from app.services.icon import IconService
from app.services.motd import legacy_to_json, parse_motd_to_json
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/icon", response_class=FileResponse)
async def get_icon():
    settings = get_settings()
    if not settings.server_icon_path.exists():
        raise HTTPException(404, "Server icon not found")
    return FileResponse(settings.server_icon_path, media_type="image/png")


@router.post("/icon", response_model=dict)
async def upload_icon(file: UploadFile = File(...)):
    settings = get_settings()
    svc = IconService()

    try:
        svc.validate_mime(file.content_type or "application/octet-stream")
    except IconProcessingError as e:
        raise HTTPException(400, str(e)) from e

    data = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(413, f"File too large (max {settings.max_upload_size_mb}MB)")

    try:
        path = await svc.process(data)
    except IconProcessingError as e:
        raise HTTPException(422, str(e)) from e

    return {"saved": str(path), "size": "64x64", "format": "PNG"}


@router.post("/motd/preview", response_model=dict)
async def preview_motd(payload: MotdPayload):
    if payload.raw:
        segments = parse_motd_to_json(payload.raw)
        json_str = legacy_to_json(payload.raw)
    elif payload.json_motd:
        from app.services.motd import format_json_motd

        segments = [s.model_dump() for s in payload.json_motd]
        json_str = format_json_motd(segments)
    else:
        raise HTTPException(400, "Provide raw or json_motd")

    return {"segments": segments, "json": json_str}
