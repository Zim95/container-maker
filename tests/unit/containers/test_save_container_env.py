# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# modules
from src.containers.containers import KubernetesContainerManager, KubernetesContainerHelper
from src.containers.dataclasses.save_container_dataclass import SaveContainerDataClass


class TestSaveContainerEnvFromEnviron(TestCase):
    '''
    Unit test for KubernetesContainerManager.save().

    This is a UNIT test: no cluster, no Cloud. The namespace lookup, the container lookup
    (CloudClient.get_container/update_container), the pod listing (PodManager.list) and
    PodManager.save are all mocked.

    Guards:
      1. The request's container_id is the DB id. save() resolves the LIVE pod from the container's
         own row (exact pod name in associated_resources) -- NOT from the unreliable
         kubernetes_id -- and snapshots that pod.
      2. The pod's real current uid is written back via Cloud (self-heal of kubernetes_id).
      3. CONTAINER_ID stays the DB id (so the Job updates the right row). No DB credentials of any
         kind are forwarded to the Job any more (container-maker holds none itself, P17+this
         migration - see p.md's writeup).
    '''

    def setUp(self) -> None:
        print('Test: setUp TestSaveContainerEnvFromEnviron')
        self.container_id: str = 'test-db-id'            # DB id (what the request carries)
        self.stale_uid: str = 'stale-uid-xyz'            # wrong kubernetes_id stored in the DB
        self.real_uid: str = 'real-uid-abc'              # the live pod's actual uid
        self.pod_name: str = 'testc-pod-999'             # exact pod name stored for this container
        self.namespace_name: str = 'test-namespace'
        self.data: SaveContainerDataClass = SaveContainerDataClass(
            container_id=self.container_id,
            network_name=self.namespace_name,
        )
        # DB row: correct pod name in associated_resources, but a WRONG kubernetes_id.
        self.row_data: dict = {
            'id': self.container_id,
            'name': 'test_c',
            'kubernetes_id': self.stale_uid,
            'associated_resources': [
                {'resource_type': 'pod', 'resource_name': self.pod_name},
            ],
        }

    def _mock_cloud_client(self):
        '''CloudClient(...) -> instance whose get_container returns the row; update_container is captured.'''
        client_instance = MagicMock()
        client_instance.get_container.return_value = self.row_data
        return MagicMock(return_value=client_instance), client_instance

    def _pods(self):
        '''PodManager.list output: the target pod PLUS a decoy pod that shares the app label.'''
        return [
            {'pod_name': self.pod_name, 'pod_id': self.real_uid, 'pod_labels': {'app': 'test-c'}},
            # decoy: same base name/label, different pod (proves we do NOT resolve by label here)
            {'pod_name': 'testc-pod-111', 'pod_id': 'other-uid', 'pod_labels': {'app': 'test-c'}},
        ]

    def test_resolves_pod_by_name_and_selfheals_uid_via_cloud(self) -> None:
        print('Test: test_resolves_pod_by_name_and_selfheals_uid_via_cloud')
        mock_client_cls, client_instance = self._mock_cloud_client()
        mock_save = MagicMock(return_value={'pod_name': self.pod_name})
        with patch('src.containers.containers.CloudClient', mock_client_cls), \
             patch('src.containers.containers.NamespaceManager.get', return_value={'namespace_name': self.namespace_name}), \
             patch('src.containers.containers.PodManager.list', return_value=self._pods()), \
             patch('src.containers.containers.PodManager.save', mock_save):
            result: list = KubernetesContainerManager.save(self.data)

        # returns the saved pod wrapped in a list
        self.assertEqual(result, [{'pod_name': self.pod_name}])

        # PodManager.save was called for the EXACT pod (by name), not the label decoy
        self.assertTrue(mock_save.called)
        save_pod_data = mock_save.call_args.args[0]
        self.assertEqual(save_pod_data.pod_name, self.pod_name)
        self.assertEqual(save_pod_data.namespace_name, self.namespace_name)

        # self-heal: kubernetes_id updated to the pod's REAL uid, via Cloud, id-scoped only
        client_instance.update_container.assert_called_once_with(
            self.container_id, {'kubernetes_id': self.real_uid}
        )

        # No DB credentials of any kind forwarded to the Job; CONTAINER_ID stays the DB id
        env = save_pod_data.environment_variables
        self.assertNotIn('DB_HOST', env)
        self.assertNotIn('DB_PASSWORD', env)
        self.assertEqual(env['CONTAINER_ID'], self.container_id)


class TestFindContainerPod(TestCase):
    '''
    Unit test for KubernetesContainerHelper.find_container_pod -- the resolution logic itself.
    No cluster: PodManager.list is mocked.
    '''

    def setUp(self) -> None:
        print('Test: setUp TestFindContainerPod')
        self.namespace_name: str = 'ns'

    def test_exact_pod_name_wins_over_shared_label(self) -> None:
        print('Test: test_exact_pod_name_wins_over_shared_label')
        # two pods share the app label; only the exact stored name must be chosen
        pods = [
            {'pod_name': 'app-pod-1', 'pod_id': 'u1', 'pod_labels': {'app': 'app'}},
            {'pod_name': 'app-pod-2', 'pod_id': 'u2', 'pod_labels': {'app': 'app'}},
        ]
        row = {'id': 'x', 'name': 'app', 'associated_resources': [{'resource_type': 'pod', 'resource_name': 'app-pod-2'}]}
        with patch('src.containers.containers.PodManager.list', return_value=pods):
            pod = KubernetesContainerHelper.find_container_pod(namespace_name=self.namespace_name, container_row_data=row)
        self.assertEqual(pod['pod_name'], 'app-pod-2')

    def test_label_fallback_used_when_stored_name_gone_and_unique(self) -> None:
        print('Test: test_label_fallback_used_when_stored_name_gone_and_unique')
        # stored pod name no longer exists (recreated); exactly one pod carries the label -> use it
        pods = [{'pod_name': 'app-pod-new', 'pod_id': 'u9', 'pod_labels': {'app': 'app'}}]
        row = {'id': 'x', 'name': 'app', 'associated_resources': [{'resource_type': 'pod', 'resource_name': 'app-pod-old'}]}
        with patch('src.containers.containers.PodManager.list', return_value=pods):
            pod = KubernetesContainerHelper.find_container_pod(namespace_name=self.namespace_name, container_row_data=row)
        self.assertEqual(pod['pod_name'], 'app-pod-new')

    def test_ambiguous_label_without_exact_name_raises(self) -> None:
        print('Test: test_ambiguous_label_without_exact_name_raises')
        # stored name gone AND label matches >1 pod -> refuse to guess
        pods = [
            {'pod_name': 'app-pod-a', 'pod_id': 'ua', 'pod_labels': {'app': 'app'}},
            {'pod_name': 'app-pod-b', 'pod_id': 'ub', 'pod_labels': {'app': 'app'}},
        ]
        row = {'id': 'x', 'name': 'app', 'associated_resources': [{'resource_type': 'pod', 'resource_name': 'app-pod-gone'}]}
        with patch('src.containers.containers.PodManager.list', return_value=pods):
            with self.assertRaises(Exception):
                KubernetesContainerHelper.find_container_pod(namespace_name=self.namespace_name, container_row_data=row)

    def test_no_match_returns_none(self) -> None:
        print('Test: test_no_match_returns_none')
        pods = [{'pod_name': 'other-pod', 'pod_id': 'uo', 'pod_labels': {'app': 'other'}}]
        row = {'id': 'x', 'name': 'app', 'associated_resources': [{'resource_type': 'pod', 'resource_name': 'app-pod-gone'}]}
        with patch('src.containers.containers.PodManager.list', return_value=pods):
            pod = KubernetesContainerHelper.find_container_pod(namespace_name=self.namespace_name, container_row_data=row)
        self.assertIsNone(pod)
