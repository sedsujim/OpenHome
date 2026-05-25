from __future__ import annotations

import jwt
import logging
from datetime import datetime

from httpx import AsyncClient, HTTPError

from app.config import get_settings

logger = logging.getLogger(__name__)


class AuthError(Exception):
    pass


class SupabaseService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._http = AsyncClient(base_url=self._settings.supabase_url, timeout=10)
        self._initialized = bool(
            self._settings.supabase_url
            and self._settings.supabase_service_key
            and self._settings.supabase_jwt_secret
        )

    @property
    def configured(self) -> bool:
        return self._initialized

    async def validate_token(self, token: str) -> dict:
        if not self._initialized:
            raise AuthError("Supabase not configured")
        try:
            payload = jwt.decode(
                token,
                self._settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except jwt.ExpiredSignatureError:
            raise AuthError("Token expired")
        except jwt.InvalidAudienceError:
            raise AuthError("Invalid token audience")
        except jwt.InvalidTokenError as e:
            raise AuthError(f"Invalid token: {e}")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthError("Token missing subject")
        return {
            "id": user_id,
            "email": payload.get("email", ""),
            "role": payload.get("role", ""),
        }

    async def get_server(self, server_id: str, user_id: str) -> dict | None:
        if not self._initialized:
            raise AuthError("Supabase not configured")
        headers = {
            "apikey": self._settings.supabase_service_key,
            "Authorization": f"Bearer {self._settings.supabase_service_key}",
        }
        params = {
            "id": f"eq.{server_id}",
            "select": "id,name,user_id,status,ram_mb,minecraft_version,loader,plan,max_players,created_at",
        }
        try:
            resp = await self._http.get(
                "/rest/v1/servers",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            rows = resp.json()
            if not rows:
                return None
            server = rows[0]
            if server.get("user_id") != user_id:
                return None
            return server
        except HTTPError as e:
            logger.error("Supabase get_server error: %s", e)
            raise AuthError(f"Failed to fetch server: {e}")

    async def get_user_servers(self, user_id: str) -> list[dict]:
        if not self._initialized:
            raise AuthError("Supabase not configured")
        headers = {
            "apikey": self._settings.supabase_service_key,
            "Authorization": f"Bearer {self._settings.supabase_service_key}",
        }
        params = {
            "user_id": f"eq.{user_id}",
            "order": "created_at.desc",
            "select": "id,name,user_id,status,ram_mb,minecraft_version,loader,plan,max_players,created_at",
        }
        try:
            resp = await self._http.get(
                "/rest/v1/servers",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
        except HTTPError as e:
            logger.error("Supabase get_user_servers error: %s", e)
            raise AuthError(f"Failed to fetch servers: {e}")

    async def get_profile(self, user_id: str) -> dict | None:
        if not self._initialized:
            raise AuthError("Supabase not configured")
        headers = {
            "apikey": self._settings.supabase_service_key,
            "Authorization": f"Bearer {self._settings.supabase_service_key}",
        }
        params = {
            "id": f"eq.{user_id}",
            "select": "id,username,plan,created_at,updated_at",
        }
        try:
            resp = await self._http.get(
                "/rest/v1/profiles",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            rows = resp.json()
            return rows[0] if rows else None
        except HTTPError as e:
            logger.error("Supabase get_profile error: %s", e)
            raise AuthError(f"Failed to fetch profile: {e}")

    async def ensure_profile(self, user_id: str, username: str | None = None) -> dict:
        profile = await self.get_profile(user_id)
        if profile is not None:
            return profile

        payload = {
            "id": user_id,
            "plan": "free",
        }
        if username is not None:
            payload["username"] = username

        headers = {
            "Content-Type": "application/json",
            "Prefer": "return=representation,resolution=merge-duplicates",
        }
        resp = await self._request("POST", "/rest/v1/profiles", json=payload, headers=headers)
        if resp.status_code >= 400:
            raise AuthError(f"Failed to create profile: {resp.text}")
        result = resp.json()
        return result[0] if isinstance(result, list) else result

    async def update_server(self, server_id: str, data: dict) -> None:
        if not self._initialized:
            raise AuthError("Supabase not configured")
        headers = {
            "apikey": self._settings.supabase_service_key,
            "Authorization": f"Bearer {self._settings.supabase_service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        params = {"id": f"eq.{server_id}"}
        try:
            resp = await self._http.patch(
                "/rest/v1/servers",
                headers=headers,
                params=params,
                json=data,
            )
            resp.raise_for_status()
        except HTTPError as e:
            logger.error("Supabase update_server error: %s", e)
            raise AuthError(f"Failed to update server: {e}")

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        headers.setdefault("apikey", self._settings.supabase_service_key)
        headers.setdefault("Authorization", f"Bearer {self._settings.supabase_service_key}")
        req = self._http.build_request(method, path, headers=headers, **kwargs)
        resp = await self._http.send(req)
        return resp

    async def create_server(self, data: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        resp = await self._request("POST", "/rest/v1/servers", json=data, headers=headers)
        if resp.status_code >= 400:
            raise AuthError(f"Failed to create server: {resp.text}")
        result = resp.json()
        return result[0] if isinstance(result, list) else result

    async def delete_server(self, server_id: str) -> None:
        resp = await self._request("DELETE", f"/rest/v1/servers?id=eq.{server_id}")
        if resp.status_code >= 400:
            raise AuthError(f"Failed to delete server: {resp.text}")

    async def close(self) -> None:
        await self._http.aclose()


_supabase: SupabaseService | None = None


def get_supabase() -> SupabaseService:
    global _supabase
    if _supabase is None:
        _supabase = SupabaseService()
    return _supabase
