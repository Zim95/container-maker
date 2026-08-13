# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# third party
from kubernetes.client import V1Pod, V1ObjectMeta

# modules
from src.resources import pod_manager
from src.resources.pod_manager import PodManager
from src.resources.dataclasses.pod.create_pod_dataclass import (
    CreatePodDataClass, ResourceRequirementsDataClass,
)


class TestCreatePodRuntimeClass(TestCase):
    '''
    UNIT test (no cluster): the untrusted user shell must be sandboxed. container-maker stamps
    `runtimeClassName` on the USER pod from USER_POD_RUNTIME_CLASS so it runs under gVisor (runsc)
    instead of sharing the host kernel. When the env is unset (e.g. docker-desktop dev, where gVisor
    isn't installed) the field must be omitted (None) so the pod falls back to the node default
    runtime (runc) and still schedules. pod_manager binds USER_POD_RUNTIME_CLASS at import time, so
    we patch it on the pod_manager module (not resource_config).
    '''

    def setUp(self) -> None:
        self.namespace_name: str = 'test-namespace'
        self.pod_name: str = 'testc-pod-123'
        self.data: CreatePodDataClass = CreatePodDataClass(
            image_name='myrepo/ssh_ubuntu:latest',
            pod_name=self.pod_name,
            container_name='testc',
            namespace_name=self.namespace_name,
            target_ports={22},
            environment_variables={'SSH_USERNAME': 'ubuntu'},
            resource_requirements=ResourceRequirementsDataClass(),
        )

    def _create_and_capture(self) -> V1Pod:
        mock_client = MagicMock()
        mock_client.create_namespaced_pod.return_value = V1Pod(
            metadata=V1ObjectMeta(name=self.pod_name, namespace=self.namespace_name),
        )
        with patch.object(PodManager, 'client', mock_client), \
             patch.object(PodManager, 'check_kubernetes_client', return_value=None), \
             patch.object(PodManager, 'get', return_value={}), \
             patch.object(PodManager, 'poll_status', return_value=None), \
             patch.object(PodManager, 'get_pod_response', return_value={'pod_name': self.pod_name}):
            PodManager.create(self.data)
        mock_client.create_namespaced_pod.assert_called_once()
        return mock_client.create_namespaced_pod.call_args.args[1]

    def test_runtime_class_stamped_when_set(self) -> None:
        with patch.object(pod_manager, 'USER_POD_RUNTIME_CLASS', 'gvisor'):
            pod_manifest = self._create_and_capture()
        self.assertEqual(pod_manifest.spec.runtime_class_name, 'gvisor')

    def test_runtime_class_omitted_when_unset(self) -> None:
        with patch.object(pod_manager, 'USER_POD_RUNTIME_CLASS', None):
            pod_manifest = self._create_and_capture()
        self.assertIsNone(pod_manifest.spec.runtime_class_name)
