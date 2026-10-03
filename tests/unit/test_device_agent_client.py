from unittest import TestCase
from unittest.mock import patch, MagicMock

import grpc

from src.device_agent_client import DeviceAgentClient, DeviceAgentClientError


class _FakeRpcError(grpc.RpcError):
    def __init__(self, details: str):
        self._details = details

    def details(self):
        return self._details


class TestDeviceAgentClient(TestCase):
    '''Finishing Part 12: Containers.save()'s self-heal lookup, via Device Agent's local API -
    no cluster, no real Cloud, no real Device Agent.'''

    def setUp(self) -> None:
        self.client = DeviceAgentClient(target="fake-target:50061")

    def test_get_container_found(self) -> None:
        with patch("src.device_agent_client.grpc.insecure_channel") as insecure_channel, \
             patch("src.device_agent_client.local_device_agent_pb2_grpc.LocalDeviceAgentStub") as stub_cls:
            insecure_channel.return_value.__enter__.return_value = MagicMock()
            stub_cls.return_value.GetContainer.return_value = MagicMock(
                found=True, container_json='{"id": "c1", "name": "my-ws"}',
            )

            result = self.client.get_container("c1")

            self.assertEqual(result, {"id": "c1", "name": "my-ws"})
            request = stub_cls.return_value.GetContainer.call_args[0][0]
            self.assertEqual(request.container_id, "c1")

    def test_get_container_not_found_returns_none(self) -> None:
        with patch("src.device_agent_client.grpc.insecure_channel") as insecure_channel, \
             patch("src.device_agent_client.local_device_agent_pb2_grpc.LocalDeviceAgentStub") as stub_cls:
            insecure_channel.return_value.__enter__.return_value = MagicMock()
            stub_cls.return_value.GetContainer.return_value = MagicMock(found=False, container_json="")

            result = self.client.get_container("c1")

            self.assertIsNone(result)

    def test_get_container_rpc_error_is_wrapped(self) -> None:
        with patch("src.device_agent_client.grpc.insecure_channel") as insecure_channel, \
             patch("src.device_agent_client.local_device_agent_pb2_grpc.LocalDeviceAgentStub") as stub_cls:
            insecure_channel.return_value.__enter__.return_value = MagicMock()
            stub_cls.return_value.GetContainer.side_effect = _FakeRpcError("device agent unreachable")

            with self.assertRaises(DeviceAgentClientError):
                self.client.get_container("c1")

    def test_update_container_kubernetes_id_success(self) -> None:
        with patch("src.device_agent_client.grpc.insecure_channel") as insecure_channel, \
             patch("src.device_agent_client.local_device_agent_pb2_grpc.LocalDeviceAgentStub") as stub_cls:
            insecure_channel.return_value.__enter__.return_value = MagicMock()
            stub = stub_cls.return_value

            self.client.update_container_kubernetes_id("c1", "new-pod-uid")

            request = stub.UpdateContainerKubernetesId.call_args[0][0]
            self.assertEqual(request.container_id, "c1")
            self.assertEqual(request.kubernetes_id, "new-pod-uid")

    def test_update_container_kubernetes_id_rpc_error_is_wrapped(self) -> None:
        with patch("src.device_agent_client.grpc.insecure_channel") as insecure_channel, \
             patch("src.device_agent_client.local_device_agent_pb2_grpc.LocalDeviceAgentStub") as stub_cls:
            insecure_channel.return_value.__enter__.return_value = MagicMock()
            stub_cls.return_value.UpdateContainerKubernetesId.side_effect = _FakeRpcError("device agent unreachable")

            with self.assertRaises(DeviceAgentClientError):
                self.client.update_container_kubernetes_id("c1", "new-pod-uid")
