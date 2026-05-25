from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_orchestrator_dep
from app.exceptions import (
    ServerAlreadyRunningError,
    ServerJarNotFoundError,
    ServerNotRunningError,
)
from app.models.schemas import CommandRequest, InstanceState, StartRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status", response_model=InstanceState)
async def get_status(
    orch=Depends(get_orchestrator_dep),
):
    return await orch.get_status()


@router.post("/start", response_model=InstanceState)
async def start_server(
    body: StartRequest = StartRequest(),
    orch=Depends(get_orchestrator_dep),
):
    try:
        await orch.start(force=body.force)
        return await orch.get_status()
    except ServerAlreadyRunningError as e:
        raise HTTPException(409, str(e)) from e
    except ServerJarNotFoundError as e:
        raise HTTPException(500, str(e)) from e


@router.post("/stop", response_model=InstanceState)
async def stop_server(
    orch=Depends(get_orchestrator_dep),
):
    try:
        await orch.stop()
        return await orch.get_status()
    except ServerNotRunningError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/restart", response_model=InstanceState)
async def restart_server(
    orch=Depends(get_orchestrator_dep),
):
    try:
        await orch.restart()
        return await orch.get_status()
    except ServerJarNotFoundError as e:
        raise HTTPException(500, str(e)) from e


@router.post("/kill", response_model=InstanceState)
async def kill_server(
    orch=Depends(get_orchestrator_dep),
):
    try:
        await orch.force_kill()
        return await orch.get_status()
    except ServerNotRunningError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/console", response_model=dict)
async def console_command(
    body: CommandRequest,
    orch=Depends(get_orchestrator_dep),
):
    try:
        await orch.send_command(body.command)
        return {"sent": True, "command": body.command}
    except ServerNotRunningError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/console", response_model=list[str])
async def get_console_log(
    tail: int = 200,
    orch=Depends(get_orchestrator_dep),
):
    return await orch.get_console(tail=tail)
