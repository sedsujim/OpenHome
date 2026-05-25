from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_dns_dep, get_tunnel_dep
from app.models.schemas import DnsStatus, TunnelStatus

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status", response_model=TunnelStatus)
async def tunnel_status(
    tunnel=Depends(get_tunnel_dep),
):
    return await tunnel.get_status()


@router.post("/start", response_model=TunnelStatus)
async def tunnel_start(
    tunnel=Depends(get_tunnel_dep),
):
    try:
        await tunnel.start()
    except FileNotFoundError as e:
        raise HTTPException(500, f"Tunnel agent not found: {e}") from e
    return await tunnel.get_status()


@router.post("/stop", response_model=TunnelStatus)
async def tunnel_stop(
    tunnel=Depends(get_tunnel_dep),
):
    await tunnel.stop()
    return await tunnel.get_status()


@router.get("/dns", response_model=DnsStatus)
async def dns_status(
    dns=Depends(get_dns_dep),
):
    return await dns.get_status()


@router.post("/dns/update", response_model=DnsStatus)
async def dns_update(
    ip: str | None = None,
    dns=Depends(get_dns_dep),
):
    from app.exceptions import DnsUpdateError

    try:
        await dns.update(ip=ip)
    except DnsUpdateError as e:
        raise HTTPException(500, str(e)) from e
    return await dns.get_status()
