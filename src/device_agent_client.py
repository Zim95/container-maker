"""
The container-maker -> Device Agent local API boundary (migration Part 12, completed).

Replaces `Containers.save()`'s former direct, internal-token-credentialed Cloud HTTP calls
(cloud_client.py's `get_container`/`update_container`) with gRPC calls to Device Agent's private,
ClusterIP-only `LocalDeviceAgent` service - container-maker holds no Cloud credential for this
call any more; NetworkPolicy (browseterm-device-agent/infra/deployment.yaml), not authentication,
is what restricts who may reach it.

Deliberately synchronous (grpc.insecure_channel, not grpc.aio) and with no retry logic, matching
the exact behavior of the cloud_client.py methods this replaces (container-maker's own
`get_container`/`update_container` never retried either, unlike status_monitor/reaper/
snapshot_job's own equivalents) - this is a one-for-one transport swap, not a reliability change.
"""
import json
from typing import Optional

import grpc
from device_control_spec import local_device_agent_pb2_grpc
from device_control_spec.local_device_agent_pb2 import GetContainerRequest, UpdateKubernetesIdRequest

from src.common.config import DEVICE_AGENT_LOCAL_API_URL
from src.common.logging_setup import get_logger

logger = get_logger("device_agent_client")


class DeviceAgentClientError(Exception):
    """Raised for any gRPC-level failure talking to Device Agent's local API."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Device Agent local API error: {message}")


class DeviceAgentClient:
    def __init__(self, target: str = DEVICE_AGENT_LOCAL_API_URL, timeout: float = 15.0):
        self._target = target
        self._timeout = timeout

    def get_container(self, container_id: str) -> Optional[dict]:
        """Calls LocalDeviceAgent.GetContainer. Returns None when Cloud has no such row (matches
        the old direct-HTTP lookup's own "no row" contract), or the full container row (decoded
        from the response's opaque container_json - see GetContainerResponse's own proto
        docstring for why it's a JSON blob rather than a hand-enumerated message)."""
        request = GetContainerRequest(container_id=container_id)
        try:
            with grpc.insecure_channel(self._target) as channel:
                stub = local_device_agent_pb2_grpc.LocalDeviceAgentStub(channel)
                response = stub.GetContainer(request, timeout=self._timeout)
        except grpc.RpcError as e:
            raise DeviceAgentClientError(e.details() or str(e)) from e
        if not response.found:
            return None
        return json.loads(response.container_json)

    def update_container_kubernetes_id(self, container_id: str, kubernetes_id: str) -> None:
        """Calls LocalDeviceAgent.UpdateContainerKubernetesId."""
        request = UpdateKubernetesIdRequest(container_id=container_id, kubernetes_id=kubernetes_id)
        try:
            with grpc.insecure_channel(self._target) as channel:
                stub = local_device_agent_pb2_grpc.LocalDeviceAgentStub(channel)
                stub.UpdateContainerKubernetesId(request, timeout=self._timeout)
        except grpc.RpcError as e:
            raise DeviceAgentClientError(e.details() or str(e)) from e
