"""
The container-maker -> Cloud boundary.

Replaces container-maker's former direct Postgres access (ContainerOps/DBConfig, real DB_HOST/
DB_PASSWORD credentials) - Local-Mac-deployed components hold no Postgres/Redis credential of
their own anywhere else in this project (see p07.md's "Local services use scoped device/service
credentials, never DB/Redis credentials"); container-maker was the one remaining exception.

Deliberately minimal, same shape as status_monitor's/snapshot_job's/reaper's own cloud_client.py
(P09/P17/P18). Auth is the same interim internal-service-token shared secret every other
trusted-SYSTEM caller uses - container-maker has no user_id of its own for either of these call
sites (both were already id-only, unscoped-by-user direct-DB lookups before this migration, so
this doesn't newly grant anything).
"""
from typing import Any, Dict, List, Optional

import httpx


class CloudClientError(Exception):
    """Raised for any non-2xx Cloud API response, or a transport-level failure (status_code=0)."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Cloud API error {status_code}: {message}")


class CloudClient:
    def __init__(self, base_url: str, internal_token: str, timeout: float = 15.0):
        self._base_url = base_url.rstrip("/")
        self._internal_token = internal_token
        self._timeout = timeout

    def _headers(self) -> dict:
        if not self._internal_token:
            return {}
        return {"X-Internal-Service-Token": self._internal_token}

    def _get(self, path: str, params: Optional[dict] = None) -> Dict[str, Any]:
        try:
            response = httpx.get(f"{self._base_url}{path}", params=params, headers=self._headers(), timeout=self._timeout)
        except httpx.HTTPError as e:
            raise CloudClientError(0, str(e)) from e
        if response.status_code < 200 or response.status_code >= 300:
            try:
                message = response.json().get("error", response.text)
            except Exception:
                message = response.text or response.reason_phrase
            raise CloudClientError(response.status_code, message)
        return response.json()

    def _post(self, path: str, json_body: Optional[dict] = None) -> Dict[str, Any]:
        try:
            response = httpx.post(f"{self._base_url}{path}", json=json_body, headers=self._headers(), timeout=self._timeout)
        except httpx.HTTPError as e:
            raise CloudClientError(0, str(e)) from e
        if response.status_code < 200 or response.status_code >= 300:
            try:
                message = response.json().get("error", response.text)
            except Exception:
                message = response.text or response.reason_phrase
            raise CloudClientError(response.status_code, message)
        return response.json()

    def get_container(self, container_id: str) -> Optional[Dict[str, Any]]:
        """GET /internal/containers/{container_id} - id-only, no user_id (mirrors the direct
        ContainerOps.find_one({"id": ...}) lookup this replaces). Returns None on a 404, matching
        the old direct-DB lookup's own "no row" contract, rather than raising."""
        try:
            return self._get(f"/internal/containers/{container_id}")["container"]
        except CloudClientError as e:
            if e.status_code == 404:
                return None
            raise

    def update_container(self, container_id: str, fields: Dict[str, Any]) -> None:
        """POST /internal/containers/{container_id} - a strict server-side whitelist
        (kubernetes_id/save_status/save_error only); see container_handlers.py's
        update_container_internal for exactly which fields it accepts."""
        self._post(f"/internal/containers/{container_id}", json_body=fields)

    def find_stuck_saves(self) -> List[Dict[str, Any]]:
        """GET /internal/containers/stuck-saves - containers whose save_status is currently
        Pending or Running, across ALL users (a cluster-wide sweep)."""
        return self._get("/internal/containers/stuck-saves")["containers"]
