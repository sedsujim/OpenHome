from __future__ import annotations

import asyncio
import logging
from typing import Callable

from app.config import get_settings
from app.core.java_process import JavaProcess
from app.exceptions import (
    ServerAlreadyRunningError,
    ServerJarNotFoundError,
    ServerNotRunningError,
)
from app.models.schemas import ServerStatus
from app.models.state import get_server_state

logger = logging.getLogger(__name__)


class ServerOrchestrator:
    def __init__(self) -> None:
        self._process: JavaProcess | None = None
        self._state = get_server_state()
        self._broadcast_callbacks: list[Callable[[str], None]] = []
        self._lock = asyncio.Lock()

    def register_broadcast(self, cb: Callable[[str], None]) -> None:
        self._broadcast_callbacks.append(cb)

    def unregister_broadcast(self, cb: Callable[[str], None]) -> None:
        self._broadcast_callbacks.remove(cb)

    def _broadcast(self, line: str) -> None:
        for cb in self._broadcast_callbacks:
            try:
                cb(line)
            except Exception:
                pass

    def _on_stdout(self, line: str) -> None:
        logger.debug("[stdout] %s", line)
        self._broadcast(line)
        self._parse_player_list(line)

    def _on_stderr(self, line: str) -> None:
        logger.warning("[stderr] %s", line)
        self._broadcast(line)

    def _on_exit(self, rc: int) -> None:
        logger.info("Server process exited with code %d", rc)
        if rc != 0:
            self._state.mark_crashed()
        else:
            self._state.mark_stopped()
        self._broadcast(f"[OpenHome] Server stopped (exit code {rc})")
        self._process = None

    def _parse_player_list(self, line: str) -> None:
        prefix = "There are "
        if prefix in line and "players online:" in line:
            try:
                parts = line.split(":")[-1].strip()
                self._state.players = [p.strip() for p in parts.split(",") if p.strip()]
            except Exception:
                pass

    async def start(self, force: bool = False) -> int:
        async with self._lock:
            if self._state.status in (ServerStatus.running, ServerStatus.starting):
                if not force:
                    raise ServerAlreadyRunningError("Server is already running")
                await self.stop()

            settings = get_settings()
            if not settings.server_jar_path.exists():
                raise ServerJarNotFoundError(
                    f"server.jar not found at {settings.server_jar_path}"
                )

            self._state.status = ServerStatus.starting
            self._process = JavaProcess(
                on_stdout=self._on_stdout,
                on_stderr=self._on_stderr,
                on_exit=self._on_exit,
            )
            pid = await self._process.start()
            self._state.mark_started(pid)
            self._broadcast(f"[OpenHome] Server started (PID {pid})")
            return pid

    async def stop(self, timeout: int = 30) -> bool:
        async with self._lock:
            if self._process is None or not self._process.is_running:
                raise ServerNotRunningError("Server is not running")
            self._state.status = ServerStatus.stopping
            ok = await self._process.stop(timeout=timeout)
            await asyncio.sleep(0.5)
            if ok:
                self._state.mark_stopped()
            return ok

    async def restart(self) -> int:
        await self.stop()
        await asyncio.sleep(2)
        return await self.start()

    async def force_kill(self) -> bool:
        async with self._lock:
            if self._process is None:
                raise ServerNotRunningError("Server is not running")
            ok = await self._process.kill()
            self._state.mark_stopped()
            return ok

    async def send_command(self, command: str) -> None:
        if self._process is None or not self._process.is_running:
            raise ServerNotRunningError("Server is not running")
        await self._process.write_stdin(command)
        self._broadcast(f"[OpenHome] /{command}")

    async def get_console(self, tail: int = 200) -> list[str]:
        if self._process is None:
            return []
        return await self._process.get_console_buffer(tail=tail)

    async def get_status(self) -> dict:
        state = self._state
        return {
            "status": state.status,
            "pid": state.pid,
            "uptime_seconds": state.uptime_seconds,
            "memory_mb": state.memory_mb,
            "players": state.players,
            "version": state.version,
        }

    async def shutdown(self) -> None:
        if self._process:
            await self._process.shutdown()
            self._state.reset()


_orchestrator: ServerOrchestrator | None = None
_orch_lock = asyncio.Lock()


async def get_orchestrator() -> ServerOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        async with _orch_lock:
            if _orchestrator is None:
                _orchestrator = ServerOrchestrator()
    return _orchestrator
