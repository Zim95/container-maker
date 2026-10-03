"""
The container-maker -> Cloud boundary.

Replaces container-maker's former direct Postgres access (ContainerOps/DBConfig, real DB_HOST/
DB_PASSWORD credentials) - Local-Mac-deployed components hold no Postgres/Redis credential of
their own anywhere else in this project (see p07.md's "Local services use scoped device/service
credentials, never DB/Redis credentials"); container-maker was the one remaining exception.

Deliberately minimal, same shape as status_monitor's/snapshot_job's/reaper's own cloud_client.py
(P09/P17/P18). Auth is the same interim internal-service-token shared secret every other
trusted-SYSTEM caller uses. Finishing Part 12 moved `get_container` and the `kubernetes_id` case
of `update_container` (containers.py's own save() self-heal) to Device Agent's local API instead
(src/device_agent_client.py) - what's left here (`update_container`'s save_status/save_error case,
`find_stuck_saves`) is save_reconciler.py's own genuinely cluster-wide sweep, which can't be
scoped to a single device's Bearer token the way the device-specific calls could.
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

    def update_container(self, container_id: str, fields: Dict[str, Any]) -> None:
        """POST /internal/containers/{container_id} - a strict server-side whitelist
        (save_status/save_error only - kubernetes_id was removed from it once containers.py's own
        save() self-heal moved to Device Agent's local API, finishing Part 12); see
        container_handlers.py's update_container_internal for exactly which fields it accepts."""
        self._post(f"/internal/containers/{container_id}", json_body=fields)

    def find_stuck_saves(self) -> List[Dict[str, Any]]:
        """GET /internal/containers/stuck-saves - containers whose save_status is currently
        Pending or Running, across ALL users (a cluster-wide sweep)."""
        return self._get("/internal/containers/stuck-saves")["containers"]
