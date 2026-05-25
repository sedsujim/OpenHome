from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "OpenHome"
    app_version: str = "0.1.0"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    cors_origins: list[str] = ["*"]

    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""

    docker_network: str = "openhome-net"
    servers_base_dir: Path = Path(os.getenv("SERVERS_BASE_DIR", "/opt/openhome/servers"))
    mc_image: str = "itzg/minecraft-server:latest"

    server_dir: Path = Path(os.getenv("SERVER_DIR", "/opt/openhome/server"))
    server_jar: str = os.getenv("SERVER_JAR", "server.jar")
    java_path: str = os.getenv("JAVA_PATH", "java")
    java_xms: str = os.getenv("JAVA_XMS", "512M")
    java_xmx: str = os.getenv("JAVA_XMX", "2G")
    java_flags: str = os.getenv("JAVA_FLAGS", "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200")

    max_console_buffer: int = 8192
    ws_heartbeat_interval: int = 30

    playit_api_key: str | None = os.getenv("PLAYIT_API_KEY")
    playit_agent_path: str = os.getenv("PLAYIT_AGENT_PATH", "playit")
    playit_tunnel_port: int = int(os.getenv("PLAYIT_TUNNEL_PORT", "25565"))

    duckdns_token: str | None = os.getenv("DUCKDNS_TOKEN")
    duckdns_domain: str | None = os.getenv("DUCKDNS_DOMAIN")

    max_upload_size_mb: int = 50

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def server_jar_path(self) -> Path:
        return self.server_dir / self.server_jar

    @property
    def server_properties_path(self) -> Path:
        return self.server_dir / "server.properties"

    @property
    def server_icon_path(self) -> Path:
        return self.server_dir / "server-icon.png"

    @property
    def eula_path(self) -> Path:
        return self.server_dir / "eula.txt"

    def ensure_server_dir(self) -> None:
        self.server_dir.mkdir(parents=True, exist_ok=True)
        self.servers_base_dir.mkdir(parents=True, exist_ok=True)
        if not self.eula_path.exists():
            self.eula_path.write_text("eula=true\n")

    def server_path(self, server_id: str) -> Path:
        return self.servers_base_dir / server_id

    def accepted_memory_mb(self) -> int:
        return self._parse_memory(self.java_xmx)

    @staticmethod
    def _parse_memory(val: str) -> int:
        val = val.strip().upper()
        if val.endswith("G"):
            return int(float(val[:-1]) * 1024)
        if val.endswith("M"):
            return int(val[:-1])
        return int(val)


@lru_cache
def get_settings() -> Settings:
    return Settings()
