from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from pathlib import Path
from typing import Callable

import docker
from docker.errors import DockerException, NotFound, APIError

from app.config import get_settings
from app.exceptions import DockerError, ServerNotRunningError

logger = logging.getLogger(__name__)

CONTAINER_PREFIX = "openhome-"
DEFAULT_PORT = 25565


class ContainerInstance:
    def __init__(
        self,
        server_id: str,
        on_stdout: Callable[[str], None] | None = None,
        on_exit: Callable[[int], None] | None = None,
    ) -> None:
        self.server_id = server_id
        self.container_name = f"{CONTAINER_PREFIX}{server_id}"
        self._on_stdout = on_stdout
        self._on_exit = on_exit
        self._console_buffer: deque[str] = deque(maxlen=8192)
        self._reader_task: asyncio.Task | None = None
        self._started_at: float | None = None
        self._pid: int | None = None

    @property
    def container_id(self) -> str:
        return self.container_name

    async def start(self, ram_mb: int, server_dir: Path, mc_version: str, loader: str) -> None:
        settings = get_settings()
        client = _get_docker_client()
        try:
            existing = self._find_container(client)
            if existing:
                logger.info("Container %s already exists, starting it", self.container_name)
                existing.start()
                self._started_at = time.time()
                self._reader_task = asyncio.create_task(self._follow_logs())
                return

            env = {
                "EULA": "TRUE",
                "MEMORY": f"{ram_mb}M",
                "TYPE": loader.upper(),
                "VERSION": mc_version,
                "ONLINE_MODE": "FALSE",
                "MAX_PLAYERS": "10",
                "ENABLE_RCON": "FALSE",
                "ENABLE_QUERY": "FALSE",
            }

            volumes = {str(server_dir): {"bind": "/data", "mode": "rw"}}

            logger.info(
                "Creating container %s (ram=%dM, type=%s, version=%s)",
                self.container_name,
                ram_mb,
                loader,
                mc_version,
            )

            container = client.containers.create(
                image=settings.mc_image,
                name=self.container_name,
                environment=env,
                volumes=volumes,
                mem_limit=f"{ram_mb}m",
                nano_cpus=int(1.5 * 1e9),
                network=settings.docker_network,
                detach=True,
                stdin_open=True,
                tty=False,
                ports={f"{DEFAULT_PORT}/tcp": None},
                labels={
                    "openhome": "true",
                    "server_id": self.server_id,
                },
            )
            container.start()
            self._started_at = time.time()
            self._reader_task = asyncio.create_task(self._follow_logs())
            logger.info("Container %s started", self.container_name)
        except DockerException as e:
            raise DockerError(f"Docker error: {e}") from e
        finally:
            client.close()

    async def stop(self, timeout: int = 30) -> bool:
        client = _get_docker_client()
        try:
            container = self._find_container(client)
            if not container:
                raise ServerNotRunningError(f"Container {self.container_name} not found")

            if container.status != "running":
                return True

            logger.info("Stopping container %s", self.container_name)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: container.stop(timeout=timeout))
            
            self._started_at = None
            self._pid = None
            if self._reader_task and not self._reader_task.done():
                self._reader_task.cancel()
            return True
        except NotFound:
            return True
        except DockerException as e:
            raise DockerError(f"Docker error: {e}") from e
        finally:
            client.close()

    async def restart(self, timeout: int = 30) -> None:
        client = _get_docker_client()
        try:
            container = self._find_container(client)
            if not container:
                raise ServerNotRunningError(f"Container {self.container_name} not found")

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: container.restart(timeout=timeout))
            self._started_at = time.time()
        except DockerException as e:
            raise DockerError(f"Docker error: {e}") from e
        finally:
            client.close()

    async def force_kill(self) -> None:
        client = _get_docker_client()
        try:
            container = self._find_container(client)
            if not container:
                raise ServerNotRunningError(f"Container {self.container_name} not found")
            container.kill()
            self._started_at = None
            self._pid = None
        except DockerException as e:
            raise DockerError(f"Docker error: {e}") from e
        finally:
            client.close()

    async def send_command(self, command: str) -> None:
        client = _get_docker_client()
        try:
            container = self._find_container(client)
            if not container or container.status != "running":
                raise ServerNotRunningError(f"Container {self.container_name} not running")

            exec_id = client.api.exec_create(
                container.id,
                cmd=["mc-send-to-console", command],
            )
            client.api.exec_start(exec_id)
        except DockerException as e:
            raise DockerError(f"Docker error: {e}") from e
        finally:
            client.close()

    async def get_status(self) -> dict:
        client = _get_docker_client()
        try:
            container = self._find_container(client)
            if not container:
                return {"status": "stopped", "container_name": self.container_name}

            container.reload()
            status_map = {
                "running": "running",
                "exited": "stopped",
                "paused": "stopped",
                "restarting": "starting",
                "created": "stopped",
            }
            status = status_map.get(container.status, "stopped")

            result = {
                "status": status,
                "container_name": self.container_name,
                "container_id": container.short_id,
                "uptime_seconds": None,
                "memory_mb": None,
                "players": [],
                "version": None,
            }

            if self._started_at and status == "running":
                result["uptime_seconds"] = time.time() - self._started_at

            if status == "running":
                stats = container.stats(stream=False)
                memory_usage = stats.get("memory_stats", {}).get("usage")
                if memory_usage:
                    result["memory_mb"] = memory_usage // (1024 * 1024)

            return result
        except DockerException:
            return {"status": "error", "container_name": self.container_name}
        finally:
            client.close()

    async def get_console(self, tail: int = 200) -> list[str]:
        if not self._console_buffer:
            client = _get_docker_client()
            try:
                container = self._find_container(client)
                if container:
                    logs = container.logs(tail=tail, timestamps=False)
                    decoded = logs.decode("utf-8", errors="replace")
                    lines = [l for l in decoded.split("\n") if l.strip()]
                    for line in lines:
                        self._console_buffer.append(line)
                    return lines[-tail:]
            except DockerException:
                pass
            finally:
                client.close()
        return list(self._console_buffer)[-tail:]

    def is_running(self) -> bool:
        client = _get_docker_client()
        try:
            container = self._find_container(client)
            return container is not None and container.status == "running"
        except DockerException:
            return False
        finally:
            client.close()

    def _find_container(self, client):
        try:
            return client.containers.get(self.container_name)
        except NotFound:
            return None

    async def _follow_logs(self) -> None:
        client = _get_docker_client()
        try:
            container = self._find_container(client)
            if not container:
                return

            for log_line in container.logs(stream=True, follow=True, tail=0):
                decoded = log_line.decode("utf-8", errors="replace").rstrip("\n\r")
                if decoded:
                    self._console_buffer.append(decoded)
                    if self._on_stdout:
                        self._on_stdout(decoded)
        except Exception:
            pass
        finally:
            client.close()
            if self._on_exit:
                self._on_exit(0)

    async def shutdown(self) -> None:
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        await self.stop(timeout=10)
        client = _get_docker_client()
        try:
            container = self._find_container(client)
            if container:
                container.remove(force=True)
        except DockerException:
            pass
        finally:
            client.close()

    async def remove(self) -> None:
        await self.shutdown()

    def prune_containers(self) -> None:
        client = _get_docker_client()
        try:
            containers = client.containers.list(
                all=True,
                filters={"label": "openhome=true"},
            )
            for c in containers:
                c.remove(force=True)
        except DockerException:
            pass
        finally:
            client.close()


_container_instances: dict[str, ContainerInstance] = {}
_containers_lock = asyncio.Lock()


async def get_container(server_id: str) -> ContainerInstance:
    async with _containers_lock:
        if server_id not in _container_instances:
            _container_instances[server_id] = ContainerInstance(server_id)
        return _container_instances[server_id]


async def remove_container_instance(server_id: str) -> None:
    async with _containers_lock:
        inst = _container_instances.pop(server_id, None)
        if inst:
            await inst.shutdown()


async def shutdown_all_containers() -> None:
    async with _containers_lock:
        for inst in _container_instances.values():
            await inst.shutdown()
        _container_instances.clear()


def _get_docker_client():
    return docker.from_env()
