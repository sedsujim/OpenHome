from __future__ import annotations

import asyncio
import json
import logging
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

from app.api.deps import get_container_dep, get_current_user, get_owned_server
from app.config import get_settings
from app.core.container import ContainerInstance, get_container, remove_container_instance
from app.exceptions import DockerError, ServerLimitError, ServerNotRunningError
from app.models.schemas import (
    CommandRequest,
    ProvisionRequest,
    ServerCreateRequest,
    ServerResponse,
    ServerStatusResponse,
    WsMessage,
)
from app.plans import assert_can_create_server, get_plan_limits, normalize_plan_id
from app.services.auth import SupabaseService, get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=list[ServerResponse])
async def list_servers(
    user: dict = Depends(get_current_user),
    auth: SupabaseService = Depends(get_supabase),
):
    if user.get("id") == "anonymous":
        return []
    servers = await auth.get_user_servers(user["id"])
    return [ServerResponse(**s) for s in servers]


@router.post("/", response_model=ServerResponse, status_code=201)
async def create_server(
    body: ServerCreateRequest,
    user: dict = Depends(get_current_user),
    auth: SupabaseService = Depends(get_supabase),
):
    if user.get("id") == "anonymous":
        raise HTTPException(401, "Authentication required")

    profile = await auth.ensure_profile(user["id"])
    plan_id = normalize_plan_id(profile.get("plan"))
    plan = get_plan_limits(plan_id)

    servers = await auth.get_user_servers(user["id"])
    try:
        await assert_can_create_server(user["id"], len(servers), plan_id=plan_id)
    except ServerLimitError as e:
        raise HTTPException(429, str(e))

    payload = {
        "user_id": user["id"],
        "name": body.name,
        "description": body.description,
        "minecraft_version": body.minecraft_version,
        "loader": body.loader,
        "plan": plan["id"],
        "plan_at_creation": plan["id"],
        "status": "created",
        "ram_mb": plan["ram_mb"],
        "max_players": plan["max_players"],
        "storage_limit_gb": plan["storage_gb"],
    }

    try:
        result = await auth.create_server(payload)
    except Exception as e:
        raise HTTPException(500, f"Failed to create server: {e}")
    return ServerResponse(**result)


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(server: dict = Depends(get_owned_server)):
    return ServerResponse(**server)


@router.delete("/{server_id}", status_code=204)
async def delete_server(
    server: dict = Depends(get_owned_server),
    auth: SupabaseService = Depends(get_supabase),
):
    server_id = server["id"]
    settings = get_settings()

    await remove_container_instance(server_id)

    server_path = settings.server_path(server_id)
    if server_path.exists():
        shutil.rmtree(server_path, ignore_errors=True)

    try:
        await auth.delete_server(server_id)
    except Exception as e:
        raise HTTPException(500, f"Failed to delete server: {e}")


@router.post("/{server_id}/provision", response_model=dict)
async def provision_server(
    body: ProvisionRequest = ProvisionRequest(),
    server: dict = Depends(get_owned_server),
    auth: SupabaseService = Depends(get_supabase),
):
    server_id = server["id"]
    settings = get_settings()
    server_path = settings.server_path(server_id)

    await auth.update_server(server_id, {"status": "provisioning"})

    try:
        server_path.mkdir(parents=True, exist_ok=True)

        eula_path = server_path / "eula.txt"
        if not eula_path.exists():
            eula_path.write_text("eula=true\n")

        properties_path = server_path / "server.properties"
        if not properties_path.exists():
            _write_default_properties(properties_path, server)

        plugins_dir = server_path / "plugins"
        plugins_dir.mkdir(exist_ok=True)

        worlds_dir = server_path / "worlds"
        worlds_dir.mkdir(exist_ok=True)

        await auth.update_server(server_id, {
            "status": "stopped",
            "minecraft_version": body.minecraft_version,
            "loader": body.loader,
        })

        return {
            "provisioned": True,
            "server_id": server_id,
            "path": str(server_path),
            "minecraft_version": body.minecraft_version,
            "loader": body.loader,
        }
    except Exception as e:
        await auth.update_server(server_id, {"status": "error"})
        logger.error("Provision failed for %s: %s", server_id, e)
        raise HTTPException(500, f"Provisioning failed: {e}")


@router.post("/{server_id}/start", response_model=ServerStatusResponse)
async def start_server(
    container: ContainerInstance = Depends(get_container_dep),
    server: dict = Depends(get_owned_server),
    auth: SupabaseService = Depends(get_supabase),
):
    server_id = server["id"]
    settings = get_settings()
    server_path = settings.server_path(server_id)

    if not server_path.exists():
        raise HTTPException(400, "Server not provisioned yet")

    try:
        await container.start(
            ram_mb=server.get("ram_mb", 1024),
            server_dir=server_path,
            mc_version=server.get("minecraft_version", "latest"),
            loader=server.get("loader", "paper"),
        )
        await auth.update_server(server_id, {"status": "running"})
        status = await container.get_status()
        return ServerStatusResponse(**status)
    except DockerError as e:
        await auth.update_server(server_id, {"status": "error"})
        raise HTTPException(500, str(e))


@router.post("/{server_id}/stop", response_model=ServerStatusResponse)
async def stop_server(
    container: ContainerInstance = Depends(get_container_dep),
    server: dict = Depends(get_owned_server),
    auth: SupabaseService = Depends(get_supabase),
):
    server_id = server["id"]
    try:
        await container.stop()
        await auth.update_server(server_id, {"status": "stopped"})
        status = await container.get_status()
        return ServerStatusResponse(**status)
    except ServerNotRunningError:
        await auth.update_server(server_id, {"status": "stopped"})
        return ServerStatusResponse(status="stopped")
    except DockerError as e:
        raise HTTPException(500, str(e))


@router.post("/{server_id}/restart", response_model=ServerStatusResponse)
async def restart_server(
    container: ContainerInstance = Depends(get_container_dep),
    server: dict = Depends(get_owned_server),
    auth: SupabaseService = Depends(get_supabase),
):
    server_id = server["id"]
    try:
        await container.restart()
        await auth.update_server(server_id, {"status": "running"})
        status = await container.get_status()
        return ServerStatusResponse(**status)
    except DockerError as e:
        raise HTTPException(500, str(e))


@router.get("/{server_id}/status", response_model=ServerStatusResponse)
async def get_server_status(
    container: ContainerInstance = Depends(get_container_dep),
):
    status = await container.get_status()
    return ServerStatusResponse(**status)


@router.get("/{server_id}/logs", response_model=list[str])
async def get_server_logs(
    tail: int = 200,
    container: ContainerInstance = Depends(get_container_dep),
):
    return await container.get_console(tail=tail)


@router.post("/{server_id}/command", response_model=dict)
async def send_command(
    body: CommandRequest,
    container: ContainerInstance = Depends(get_container_dep),
):
    try:
        await container.send_command(body.command)
        return {"sent": True, "command": body.command}
    except ServerNotRunningError as e:
        raise HTTPException(409, str(e))
    except DockerError as e:
        raise HTTPException(500, str(e))


@router.websocket("/{server_id}/console")
async def console_ws(websocket: WebSocket, server_id: str):
    token = websocket.query_params.get("access_token", "")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    auth = get_supabase()
    try:
        user = await auth.validate_token(token)
        server = await auth.get_server(server_id, user["id"])
        if not server:
            await websocket.close(code=4004, reason="Server not found")
            return
    except Exception:
        await websocket.close(code=4001, reason="Auth failed")
        return

    await websocket.accept()
    container = await get_container(server_id)
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=2048)

    def _on_console(line: str):
        try:
            queue.put_nowait(line)
        except asyncio.QueueFull:
            pass

    container._on_stdout = _on_console

    async def _sender():
        try:
            while True:
                line = await queue.get()
                try:
                    msg = WsMessage(type="console", data=line)
                    await websocket.send_text(msg.model_dump_json())
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def _receiver():
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    parsed = json.loads(raw)
                    msg = WsMessage(**parsed)
                except (json.JSONDecodeError, ValueError):
                    await websocket.send_text(
                        WsMessage(type="error", data="invalid message").model_dump_json()
                    )
                    continue

                if msg.type == "command":
                    try:
                        await container.send_command(msg.data)
                        ack = WsMessage(type="ack", data=msg.data)
                        await websocket.send_text(ack.model_dump_json())
                    except Exception as e:
                        err = WsMessage(type="error", data=str(e))
                        await websocket.send_text(err.model_dump_json())
                else:
                    await websocket.send_text(
                        WsMessage(type="error", data=f"unknown type: {msg.type}").model_dump_json()
                    )
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    sender = asyncio.create_task(_sender())
    receiver = asyncio.create_task(_receiver())

    try:
        await asyncio.gather(sender, receiver)
    finally:
        sender.cancel()
        receiver.cancel()


@router.post("/{server_id}/plugins", response_model=dict)
async def upload_plugin(
    file: UploadFile = File(...),
    server: dict = Depends(get_owned_server),
):
    server_id = server["id"]
    settings = get_settings()
    plugins_dir = settings.server_path(server_id) / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    if not file.filename or not file.filename.endswith(".jar"):
        raise HTTPException(400, "Only .jar plugin files are accepted")

    data = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(413, f"File too large (max {settings.max_upload_size_mb}MB)")

    dest = plugins_dir / file.filename
    with open(dest, "wb") as f:
        f.write(data)

    logger.info("Plugin uploaded: %s -> %s", file.filename, dest)
    return {"uploaded": file.filename, "size": len(data), "path": str(dest)}


@router.post("/{server_id}/world", response_model=dict)
async def upload_world(
    file: UploadFile = File(...),
    server: dict = Depends(get_owned_server),
):
    server_id = server["id"]
    settings = get_settings()
    server_path = settings.server_path(server_id)

    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, "Only .zip world files are accepted")

    data = await file.read()
    max_bytes = 200 * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(413, "World file too large (max 200MB)")

    temp_zip = server_path / "_upload_world.zip"
    with open(temp_zip, "wb") as f:
        f.write(data)

    world_name = file.filename.replace(".zip", "")
    world_dir = server_path / world_name

    try:
        with zipfile.ZipFile(temp_zip, "r") as zf:
            zf.extractall(server_path)

        if not world_dir.exists():
            extracted = [p for p in server_path.iterdir() if p.is_dir() and p.name != "plugins"]
            if extracted:
                world_dir = extracted[0]
                world_name = world_dir.name

        logger.info("World uploaded: %s -> %s", file.filename, world_dir)
        return {"uploaded": world_name, "size": len(data), "path": str(world_dir)}
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid zip file")
    finally:
        if temp_zip.exists():
            temp_zip.unlink()


def _write_default_properties(path: Path, server: dict) -> None:
    props = {
        "motd": f"{server.get('name', 'OpenHome Server')}",
        "server-port": "25565",
        "difficulty": "easy",
        "gamemode": "survival",
        "max-players": str(server.get("max_players", 10)),
        "online-mode": "false",
        "pvp": "true",
        "allow-flight": "false",
        "enable-command-block": "true",
        "spawn-protection": "0",
        "view-distance": "10",
        "simulation-distance": "8",
        "level-seed": "",
        "white-list": "false",
        "hardcore": "false",
    }
    lines = [f"{k}={v}" for k, v in props.items()]
    path.write_text("\n".join(lines) + "\n")
