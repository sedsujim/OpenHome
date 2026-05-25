from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import get_settings
from app.core.container import shutdown_all_containers
from app.core.orchestrator import get_orchestrator
from app.middleware.cors import setup_cors
from app.models.schemas import DnsStatus, HealthResponse, InstanceState, TunnelStatus
from app.services.dns import get_dns_service
from app.services.tunnel import get_tunnel_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_server_dir()
    settings.servers_base_dir.mkdir(parents=True, exist_ok=True)
    logger.info("OpenHome starting (version %s)", settings.app_version)

    orch = await get_orchestrator()
    dns = await get_dns_service()

    if dns.configured:
        await dns.start_auto_update()

    yield

    await shutdown_all_containers()
    await orch.shutdown()
    tunnel = await get_tunnel_service()
    await tunnel.stop()
    await dns.stop_auto_update()
    logger.info("OpenHome shut down")


def create_app() -> FastAPI:
    settings = get_settings()
    static_dir = Path(__file__).resolve().parent / "static"
    index_file = static_dir / "index.html"
    login_file = static_dir / "login.html"
    register_file = static_dir / "register.html"
    servers_file = static_dir / "servers.html"
    pricing_file = static_dir / "pricing.html"
    server_detail_file = static_dir / "server-detail.html"
    auth_confirm_file = static_dir / "auth-confirm.html"
    forgot_password_file = static_dir / "forgot-password.html"
    reset_password_file = static_dir / "reset-password.html"

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    setup_cors(app)
    app.include_router(api_router)

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
    async def health():
        orch = await get_orchestrator()
        tunnel = await get_tunnel_service()
        dns = await get_dns_service()

        return HealthResponse(
            server=InstanceState(**await orch.get_status()),
            tunnel=TunnelStatus(**await tunnel.get_status()),
            dns=DnsStatus(**await dns.get_status()),
            version=get_settings().app_version,
        )

    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    async def home_page():
        return FileResponse(index_file)

    @app.get("/login", include_in_schema=False)
    @app.get("/login.html", include_in_schema=False)
    async def login_page():
        return FileResponse(login_file)

    @app.get("/register", include_in_schema=False)
    @app.get("/register.html", include_in_schema=False)
    async def register_page():
        return FileResponse(register_file)

    @app.get("/servers", include_in_schema=False)
    @app.get("/servers.html", include_in_schema=False)
    async def servers_page():
        return FileResponse(servers_file)

    @app.get("/pricing", include_in_schema=False)
    @app.get("/pricing.html", include_in_schema=False)
    async def pricing_page():
        return FileResponse(pricing_file)

    @app.get("/server", include_in_schema=False)
    @app.get("/server-detail.html", include_in_schema=False)
    async def server_detail_page():
        return FileResponse(server_detail_file)

    @app.get("/auth-confirm", include_in_schema=False)
    @app.get("/auth-confirm.html", include_in_schema=False)
    async def auth_confirm_page():
        return FileResponse(auth_confirm_file)

    @app.get("/forgot-password", include_in_schema=False)
    @app.get("/forgot-password.html", include_in_schema=False)
    async def forgot_password_page():
        return FileResponse(forgot_password_file)

    @app.get("/reset-password", include_in_schema=False)
    @app.get("/reset-password.html", include_in_schema=False)
    async def reset_password_page():
        return FileResponse(reset_password_file)

    app.mount("/css", StaticFiles(directory=str(static_dir / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(static_dir / "js")), name="js")

    return app


app = create_app()
