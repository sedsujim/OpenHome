from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.core.container import ContainerInstance, get_container
from app.core.orchestrator import ServerOrchestrator, get_orchestrator
from app.exceptions import AuthError
from app.services.auth import SupabaseService, get_supabase
from app.services.dns import DnsService, get_dns_service
from app.services.tunnel import TunnelService, get_tunnel_service

security = HTTPBearer(auto_error=False)


async def get_orchestrator_dep() -> ServerOrchestrator:
    return await get_orchestrator()


async def get_tunnel_dep() -> TunnelService:
    return await get_tunnel_service()


async def get_dns_dep() -> DnsService:
    return await get_dns_service()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    auth: SupabaseService = Depends(get_supabase),
):
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        return {"id": "anonymous", "email": "", "role": "anonymous"}
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        user = await auth.validate_token(credentials.credentials)
        return user
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


async def get_owned_server(
    server_id: str,
    user: dict = Depends(get_current_user),
    auth: SupabaseService = Depends(get_supabase),
):
    if user.get("id") == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    server = await auth.get_server(server_id, user["id"])
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )
    return server


async def get_container_dep(
    server_id: str,
    server: dict = Depends(get_owned_server),
) -> ContainerInstance:
    return await get_container(server_id)
