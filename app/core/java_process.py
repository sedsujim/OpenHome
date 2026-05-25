from __future__ import annotations

import asyncio
import logging
import os
import signal
from asyncio.subprocess import Process
from collections import deque
from typing import Callable

from app.config import get_settings

logger = logging.getLogger(__name__)


class JavaProcess:
    def __init__(
        self,
        on_stdout: Callable[[str], None] | None = None,
        on_stderr: Callable[[str], None] | None = None,
        on_exit: Callable[[int], None] | None = None,
    ) -> None:
        self._proc: Process | None = None
        self._on_stdout = on_stdout
        self._on_stderr = on_stderr
        self._on_exit = on_exit
        self._console_buffer: deque[str] = deque(maxlen=8192)
        self._reader_task: asyncio.Task[None] | None = None

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc and self._proc.returncode is None else None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    @property
    def return_code(self) -> int | None:
        return self._proc.returncode if self._proc else None

    def _build_command(self) -> list[str]:
        settings = get_settings()
        cmd = [
            settings.java_path,
            f"-Xms{settings.java_xms}",
            f"-Xmx{settings.java_xmx}",
            *settings.java_flags.split(),
            "-jar",
            str(settings.server_jar_path),
            "nogui",
        ]
        return cmd

    async def start(self) -> int:
        if self.is_running:
            raise RuntimeError("Process already running")

        settings = get_settings()
        settings.ensure_server_dir()

        cmd = self._build_command()
        logger.info("Starting Java process: %s", " ".join(cmd))

        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(settings.server_dir),
            preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        )

        self._reader_task = asyncio.create_task(self._pipe_reader())
        return self._proc.pid

    async def _pipe_reader(self) -> None:
        if self._proc is None:
            return

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._read_stream(self._proc.stdout, self._on_stdout))
                tg.create_task(self._read_stream(self._proc.stderr, self._on_stderr))
        except Exception:
            pass
        finally:
            rc = self._proc.returncode if self._proc else -1
            if self._on_exit:
                self._on_exit(rc)

    async def _read_stream(
        self,
        stream: asyncio.StreamReader | None,
        callback: Callable[[str], None] | None,
    ) -> None:
        if stream is None:
            return
        while not stream.at_eof():
            try:
                line = await asyncio.wait_for(stream.readline(), timeout=60.0)
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip("\n\r")
                self._console_buffer.append(decoded)
                if callback:
                    callback(decoded)
            except asyncio.TimeoutError:
                continue
            except (asyncio.CancelledError, BrokenPipeError):
                break

    async def write_stdin(self, command: str) -> None:
        if not self.is_running or self._proc is None or self._proc.stdin is None:
            raise RuntimeError("Process not running")
        data = f"{command}\n".encode("utf-8")
        self._proc.stdin.write(data)
        await self._proc.stdin.drain()

    async def stop(self, timeout: int = 30) -> bool:
        if not self.is_running:
            return True
        logger.info("Stopping Minecraft server (graceful)")
        try:
            await self.write_stdin("stop")
        except RuntimeError:
            pass
        try:
            await asyncio.wait_for(self._proc.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning("Graceful stop timed out, forcing kill")
            return await self.kill()

    async def kill(self) -> bool:
        if not self.is_running or self._proc is None:
            return True
        logger.warning("Force-killing Minecraft server PID=%s", self.pid)
        try:
            if hasattr(os, "killpg") and self._proc.pid:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
            else:
                self._proc.kill()
            await asyncio.wait_for(self._proc.wait(), timeout=10)
        except (ProcessLookupError, asyncio.TimeoutError):
            pass
        return True

    async def get_console_buffer(self, tail: int = 200) -> list[str]:
        return list(self._console_buffer)[-tail:]

    async def shutdown(self) -> None:
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        await self.kill()
