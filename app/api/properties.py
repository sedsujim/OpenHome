from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.exceptions import PropertiesParseError
from app.models.schemas import PropertiesPayload
from app.services.editor import PropertiesEditor

router = APIRouter()


@router.get("/", response_model=dict[str, str])
async def get_properties():
    editor = PropertiesEditor()
    try:
        return editor.read()
    except PropertiesParseError as e:
        raise HTTPException(500, str(e)) from e


@router.put("/", response_model=dict[str, str])
async def update_properties(payload: PropertiesPayload):
    editor = PropertiesEditor()
    try:
        return editor.apply(payload.properties)
    except PropertiesParseError as e:
        raise HTTPException(500, str(e)) from e
