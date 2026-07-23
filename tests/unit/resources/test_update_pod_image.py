# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# third party
from kubernetes.client import V1Pod, V1PodSpec, V1Container, V1ObjectMeta

# modules
from src.resources.pod_manager import PodManager
from src.resources.resource_config import STATUS_SIDECAR_NAME, STATUS_SIDECAR_IMAGE_NAME


class TestUpdatePodImage(TestCase):
    '''
    UNIT test (no cluster): _update_pod_image is the in-place CRASH RECOVERY seam.
    It must repoint ONLY the main container (name == pod_name) at the saved image and
    leave the status sidecar untouched, so the kubelet restarts a crashed container
    from the snapshot without disturbing the sidecar.
    '''

    def setUp(self) -> None:
        print('Test: setUp TestUpdatePodImage')
        self.namespace_name: str = 'test-namespace'
        self.pod_name: str = 'testc-pod-123'
        self.old_main_image: str = 'zim95/ssh_ubuntu:latest'
        self.new_image: str = 'myrepo/testc-pod-123-image:latest'
        self.fake_pod: V1Pod = V1Pod(
            metadata=V1ObjectMeta(name=self.pod_name, namespace=self.namespace_name),
            spec=V1PodSpec(containers=[
                V1Container(name=self.pod_name, image=self.old_main_image),             # main
                V1Container(name=STATUS_SIDECAR_NAME, image=STATUS_SIDECAR_IMAGE_NAME),  # sidecar
            ]),
        )

    def _invoke(self):
        mock_client = MagicMock()
        mock_client.read_namespaced_pod.return_value = self.fake_pod
        with patch.object(PodManager, 'client', mock_client):
            PodManager._update_pod_image(
                namespace_name=self.namespace_name,
                pod_name=self.pod_name,
                image_name=self.new_image,
            )
        return mock_client

    def test_main_container_image_updated_sidecar_untouched(self) -> None:
        print('Test: test_main_container_image_updated_sidecar_untouched')
        mock_client = self._invoke()
        mock_client.patch_namespaced_pod.assert_called_once()
        kwargs = mock_client.patch_namespaced_pod.call_args.kwargs
        self.assertEqual(kwargs['name'], self.pod_name)
        self.assertEqual(kwargs['namespace'], self.namespace_name)
        patched = kwargs['body']
        by_name = {c.name: c.image for c in patched.spec.containers}
        self.assertEqual(by_name[self.pod_name], self.new_image)                    # main updated
        self.assertEqual(by_name[STATUS_SIDECAR_NAME], STATUS_SIDECAR_IMAGE_NAME)   # sidecar untouched
