# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# third party
from kubernetes.client import V1Pod, V1ObjectMeta

# modules
from src.resources.pod_manager import (
    PodManager,
    SIDECAR_ONLY_ENV_PREFIXES,
    USER_POD_MANAGED_LABEL_KEY,
    USER_POD_MANAGED_LABEL_VALUE,
    USER_POD_CONTAINER_ID_LABEL,
)
from src.resources.dataclasses.pod.create_pod_dataclass import (
    CreatePodDataClass, ResourceRequirementsDataClass,
)


class TestUserPodShape(TestCase):
    '''
    UNIT test (no cluster): the shape of the user pod after the sidecar removal + central
    status_monitor.

    Guarantees:
      1. The pod is a SINGLE container (the untrusted user shell) — no status/snapshot sidecar.
      2. That container carries NO credential-shaped env (DB_* / MINIO_*), so the root shell cannot
         `printenv` database/object-store credentials.
      3. The pod is labelled for the central status_monitor: browseterm/managed=user-pod (the watch
         selector) and browseterm/container-id=<uuid> (the DB row the monitor updates).
    '''

    def setUp(self) -> None:
        print('Test: setUp TestUserPodShape')
        self.namespace_name: str = 'test-namespace'
        self.pod_name: str = 'testc-pod-123'
        self.container_id: str = 'db-id-1'
        # Mix of sensitive (should never reach the shell) and non-sensitive keys.
        self.env: dict = {
            'CONTAINER_ID': self.container_id,   # rides to the pod label; non-sensitive
            'SSH_USERNAME': 'ubuntu',            # non-sensitive
            'DB_PASSWORD': 'super-secret',       # sensitive — must be stripped
            'MINIO_SECRET_KEY': 'minio-secret',  # sensitive — must be stripped
        }
        self.data: CreatePodDataClass = CreatePodDataClass(
            image_name='myrepo/testc:latest',
            pod_name=self.pod_name,
            container_name='testc',
            namespace_name=self.namespace_name,
            target_ports={22},
            environment_variables=self.env,
            resource_requirements=ResourceRequirementsDataClass(),
        )

    def _created_pod(self) -> V1Pod:
        '''Run PodManager.create with the cluster mocked out; return the built V1Pod manifest.'''
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

    @staticmethod
    def _env_dict(container) -> dict:
        return {e.name: e.value for e in (container.env or [])}

    def test_pod_is_single_container(self) -> None:
        print('Test: test_pod_is_single_container')
        containers = self._created_pod().spec.containers
        self.assertEqual([c.name for c in containers], [self.pod_name])

    def test_main_container_has_no_credential_env(self) -> None:
        print('Test: test_main_container_has_no_credential_env')
        main = self._created_pod().spec.containers[0]
        main_env = self._env_dict(main)
        leaked = [k for k in main_env if k.startswith(SIDECAR_ONLY_ENV_PREFIXES)]
        self.assertEqual(leaked, [], f'credentials leaked into user container: {leaked}')
        # non-sensitive keys still threaded through
        self.assertEqual(main_env.get('SSH_USERNAME'), 'ubuntu')

    def test_pod_carries_monitor_labels(self) -> None:
        print('Test: test_pod_carries_monitor_labels')
        labels = self._created_pod().metadata.labels
        self.assertEqual(labels.get(USER_POD_MANAGED_LABEL_KEY), USER_POD_MANAGED_LABEL_VALUE)
        self.assertEqual(labels.get(USER_POD_CONTAINER_ID_LABEL), self.container_id)

    def test_user_pod_has_no_api_token(self) -> None:
        print('Test: test_user_pod_has_no_api_token')
        # The untrusted shell must not carry a ServiceAccount API token.
        self.assertFalse(self._created_pod().spec.automount_service_account_token)
