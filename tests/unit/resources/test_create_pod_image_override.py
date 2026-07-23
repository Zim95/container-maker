# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# third party
from kubernetes.client import V1Pod, V1ObjectMeta

# modules
from src.resources.pod_manager import PodManager
from src.resources.resource_config import STATUS_SIDECAR_NAME, STATUS_SIDECAR_IMAGE_NAME
from src.resources.dataclasses.pod.create_pod_dataclass import (
    CreatePodDataClass, ResourceRequirementsDataClass,
)


class TestCreatePodImageOverride(TestCase):
    '''
    UNIT test (no cluster): the RESUME path. browseterm-server resumes a hibernated
    container by calling createContainer with image_name set to the saved image; that
    image_name is threaded onto the pod's MAIN container (name == pod_name). Here we assert
    PodManager.create builds the pod spec with the overridden image on the main container,
    leaving the status sidecar on its own image.
    '''

    def setUp(self) -> None:
        print('Test: setUp TestCreatePodImageOverride')
        self.namespace_name: str = 'test-namespace'
        self.pod_name: str = 'testc-pod-123'
        self.saved_image: str = 'myrepo/testc-pod-123-image:latest'  # image override on resume
        self.data: CreatePodDataClass = CreatePodDataClass(
            image_name=self.saved_image,
            pod_name=self.pod_name,
            container_name='testc',
            namespace_name=self.namespace_name,
            target_ports={22},
            environment_variables={'SSH_USERNAME': 'ubuntu'},
            resource_requirements=ResourceRequirementsDataClass(),
        )

    def test_created_pod_main_container_uses_overridden_image(self) -> None:
        print('Test: test_created_pod_main_container_uses_overridden_image')
        mock_client = MagicMock()
        mock_client.create_namespaced_pod.return_value = V1Pod(
            metadata=V1ObjectMeta(name=self.pod_name, namespace=self.namespace_name),
        )
        with patch.object(PodManager, 'client', mock_client), \
             patch.object(PodManager, 'check_kubernetes_client', return_value=None), \
             patch.object(PodManager, 'get', return_value={}), \
             patch.object(PodManager, '_ensure_status_sidecar_rbac', return_value=None), \
             patch.object(PodManager, 'poll_status', return_value=None), \
             patch.object(PodManager, 'get_pod_response', return_value={'pod_name': self.pod_name}):
            PodManager.create(self.data)

        mock_client.create_namespaced_pod.assert_called_once()
        args = mock_client.create_namespaced_pod.call_args.args
        pod_manifest: V1Pod = args[1]
        by_name = {c.name: c.image for c in pod_manifest.spec.containers}
        self.assertEqual(by_name[self.pod_name], self.saved_image)                  # main = saved image
        self.assertEqual(by_name[STATUS_SIDECAR_NAME], STATUS_SIDECAR_IMAGE_NAME)   # sidecar unchanged
