from __future__ import annotations

from fastapi import APIRouter

from app.api.instance import router as instance_router
from app.api.profile import router as profile_router
from app.api.properties import router as properties_router
from app.api.assets import router as assets_router
from app.api.tunnel import router as tunnel_router
from app.api.ws import router as ws_router
from app.api.servers import router as servers_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(instance_router, prefix="/instance", tags=["Instance (legacy)"])
api_router.include_router(profile_router, prefix="/profile", tags=["Profile"])
api_router.include_router(properties_router, prefix="/properties", tags=["Properties (legacy)"])
api_router.include_router(assets_router, prefix="/assets", tags=["Assets"])
api_router.include_router(tunnel_router, prefix="/tunnel", tags=["Tunnel"])
api_router.include_router(ws_router, prefix="/ws", tags=["WebSocket (legacy)"])
api_router.include_router(servers_router, prefix="/servers", tags=["Servers"])
