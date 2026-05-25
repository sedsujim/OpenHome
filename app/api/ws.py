from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import get_orchestrator_dep
from app.models.schemas import WsMessage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/console")
async def console_ws(websocket: WebSocket):
    await websocket.accept()
    orch = await get_orchestrator_dep()
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=2048)

    def _on_console(line: str) -> None:
        try:
            queue.put_nowait(line)
        except asyncio.QueueFull:
            pass

    orch.register_broadcast(_on_console)

    async def _sender() -> None:
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

    async def _receiver() -> None:
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
                        await orch.send_command(msg.data)
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
        orch.unregister_broadcast(_on_console)
