# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# third party
from kubernetes.client import V1Pod, V1ObjectMeta

# modules
from src.resources.pod_manager import PodManager
from src.resources.dataclasses.pod.create_pod_dataclass import (
    CreatePodDataClass, ResourceRequirementsDataClass,
)


class TestCreatePodRestartPolicy(TestCase):
    '''
    UNIT test (no cluster): fixed 2026-09-27. User pods have no PVC - the whole filesystem is the
    container's own writable layer - so restart_policy must be "Never", not Kubernetes' default
    "Always". Under "Always", kubelet silently restarts a crashed container in place, reinitializing
    that layer from whatever image is currently live, with no event status_monitor can observe.
    Under "Never" a crash instead leaves the pod in a real, watchable "Failed" phase, which
    status_monitor turns into a proper recovery (skip-save Hibernate -> Resume from saved_image)
    instead of silent, invisible data loss.
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

    def test_restart_policy_is_never(self) -> None:
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
        pod_manifest: V1Pod = mock_client.create_namespaced_pod.call_args.args[1]
        self.assertEqual(pod_manifest.spec.restart_policy, 'Never')
