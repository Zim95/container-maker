# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# modules
from src.containers.containers import KubernetesContainerManager, KubernetesContainerHelper
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass


class TestFindPodByDbId(TestCase):
    '''
    Unit test for KubernetesContainerHelper.find_pod_by_db_id -- the resolution logic delete()
    now uses instead of a raw pod-UID equality check. No cluster: PodManager.list is mocked.
    '''

    def setUp(self) -> None:
        self.namespace_name: str = 'ns'

    def test_finds_pod_by_container_id_label(self) -> None:
        pods = [
            {'pod_name': 'a-pod-1', 'pod_id': 'uid-1', 'pod_labels': {'app': 'a', 'browseterm/container-id': 'db-id-a'}},
            {'pod_name': 'b-pod-1', 'pod_id': 'uid-2', 'pod_labels': {'app': 'b', 'browseterm/container-id': 'db-id-b'}},
        ]
        with patch('src.containers.containers.PodManager.list', return_value=pods):
            pod = KubernetesContainerHelper.find_pod_by_db_id(self.namespace_name, 'db-id-b')
        self.assertEqual(pod['pod_name'], 'b-pod-1')

    def test_resolves_even_when_pod_uid_differs_from_everything(self) -> None:
        '''The whole point: an arbitrary/stale UID never enters the comparison at all - only the
        label value matters.'''
        pods = [{'pod_name': 'a-pod-1', 'pod_id': 'some-random-uid-that-means-nothing',
                 'pod_labels': {'browseterm/container-id': 'db-id-a'}}]
        with patch('src.containers.containers.PodManager.list', return_value=pods):
            pod = KubernetesContainerHelper.find_pod_by_db_id(self.namespace_name, 'db-id-a')
        self.assertIsNotNone(pod)
        self.assertEqual(pod['pod_id'], 'some-random-uid-that-means-nothing')

    def test_no_match_returns_none(self) -> None:
        pods = [{'pod_name': 'a-pod-1', 'pod_id': 'uid-1', 'pod_labels': {'browseterm/container-id': 'db-id-a'}}]
        with patch('src.containers.containers.PodManager.list', return_value=pods):
            pod = KubernetesContainerHelper.find_pod_by_db_id(self.namespace_name, 'does-not-exist')
        self.assertIsNone(pod)

    def test_pod_with_no_labels_at_all_does_not_crash(self) -> None:
        pods = [{'pod_name': 'a-pod-1', 'pod_id': 'uid-1', 'pod_labels': None}]
        with patch('src.containers.containers.PodManager.list', return_value=pods):
            pod = KubernetesContainerHelper.find_pod_by_db_id(self.namespace_name, 'db-id-a')
        self.assertIsNone(pod)

    def test_ambiguous_label_refuses_to_guess(self) -> None:
        '''Should never happen (DB ids are unique) but if it somehow does, refuse rather than
        silently pick one and risk deleting the wrong container's pod.'''
        pods = [
            {'pod_name': 'a-pod-1', 'pod_id': 'uid-1', 'pod_labels': {'browseterm/container-id': 'dup-id'}},
            {'pod_name': 'a-pod-2', 'pod_id': 'uid-2', 'pod_labels': {'browseterm/container-id': 'dup-id'}},
        ]
        with patch('src.containers.containers.PodManager.list', return_value=pods):
            with self.assertRaises(Exception):
                KubernetesContainerHelper.find_pod_by_db_id(self.namespace_name, 'dup-id')


class TestFindServiceForPod(TestCase):
    '''
    Unit test for KubernetesContainerHelper.find_service_for_pod -- resolves via the pod<->service
    relationship ServiceManager already computes for every service's own associated_resources, no
    separate label needed on the Service itself. No cluster: ServiceManager.list is mocked.
    '''

    def setUp(self) -> None:
        self.namespace_name: str = 'ns'
        self.pod: dict = {'pod_name': 'a-pod-1', 'pod_id': 'uid-1'}

    def test_finds_the_service_routing_to_this_pod(self) -> None:
        services = [
            {'service_name': 'other-svc', 'associated_resources': [{'pod_id': 'uid-9'}]},
            {'service_name': 'a-svc', 'associated_resources': [{'pod_id': 'uid-1'}]},
        ]
        with patch('src.containers.containers.ServiceManager.list', return_value=services):
            service = KubernetesContainerHelper.find_service_for_pod(self.namespace_name, self.pod)
        self.assertEqual(service['service_name'], 'a-svc')

    def test_no_matching_service_returns_none(self) -> None:
        services = [{'service_name': 'other-svc', 'associated_resources': [{'pod_id': 'uid-9'}]}]
        with patch('src.containers.containers.ServiceManager.list', return_value=services):
            service = KubernetesContainerHelper.find_service_for_pod(self.namespace_name, self.pod)
        self.assertIsNone(service)


class TestDeleteResolvesByDbIdLabel(TestCase):
    '''
    Unit test for KubernetesContainerManager.delete() itself: the regression this whole change
    exists for. Live-confirmed bug (see delete()'s own docstring): the OLD code matched
    `data.container_id` against the pod's raw Kubernetes UID, which goes stale after any resume
    recreates the pod - resulting in a silent no-op that still reported {'status': 'Deleted'},
    orphaning the pod forever. No cluster: NamespaceManager/PodManager/ServiceManager/delete_pod/
    delete_service/delete_lingering_namespaces are all mocked.
    '''

    def setUp(self) -> None:
        self.namespace_name: str = 'ns'
        self.db_id: str = 'db-id-abc'

    def test_deletes_pod_and_its_service_by_db_id_label(self) -> None:
        pod = {'pod_name': 'my-pod-1', 'pod_id': 'live-uid-xyz',
               'pod_labels': {'browseterm/container-id': self.db_id}}
        service = {'service_name': 'my-svc-1', 'associated_resources': [{'pod_id': 'live-uid-xyz'}]}
        mock_delete_pod = MagicMock()
        mock_delete_service = MagicMock()
        with patch('src.containers.containers.NamespaceManager.get', return_value={'namespace_name': self.namespace_name}), \
             patch('src.containers.containers.PodManager.list', return_value=[pod]), \
             patch('src.containers.containers.ServiceManager.list', return_value=[service]), \
             patch('src.containers.containers.IngressManager.list', return_value=[]), \
             patch.object(KubernetesContainerHelper, 'delete_pod', mock_delete_pod), \
             patch.object(KubernetesContainerHelper, 'delete_service', mock_delete_service), \
             patch.object(KubernetesContainerHelper, 'delete_lingering_namespaces', MagicMock()):
            result = KubernetesContainerManager.delete(
                DeleteContainerDataClass(network_name=self.namespace_name, container_id=self.db_id)
            )
        mock_delete_pod.assert_called_once_with(namespace_name=self.namespace_name, pod_name='my-pod-1')
        mock_delete_service.assert_called_once_with(namespace_name=self.namespace_name, service_name='my-svc-1')
        self.assertEqual(result, {'container_id': self.db_id, 'status': 'Deleted'})

    def test_ignores_a_stale_kubernetes_id_entirely(self) -> None:
        '''The exact bug: passing the pod's OWN real uid as container_id (simulating what the old
        caller convention used to send) must NOT resolve anything now - only the DB-id label
        comparison matters, so a caller that (wrongly) still sent a raw pod UID finds nothing and
        deletes nothing, rather than accidentally working by coincidence.'''
        pod = {'pod_name': 'my-pod-1', 'pod_id': 'live-uid-xyz',
               'pod_labels': {'browseterm/container-id': self.db_id}}
        mock_delete_pod = MagicMock()
        with patch('src.containers.containers.NamespaceManager.get', return_value={'namespace_name': self.namespace_name}), \
             patch('src.containers.containers.PodManager.list', return_value=[pod]), \
             patch('src.containers.containers.ServiceManager.list', return_value=[]), \
             patch('src.containers.containers.IngressManager.list', return_value=[]), \
             patch.object(KubernetesContainerHelper, 'delete_pod', mock_delete_pod), \
             patch.object(KubernetesContainerHelper, 'delete_lingering_namespaces', MagicMock()):
            result = KubernetesContainerManager.delete(
                # caller sends the pod's raw UID instead of the DB id - must not match
                DeleteContainerDataClass(network_name=self.namespace_name, container_id='live-uid-xyz')
            )
        mock_delete_pod.assert_not_called()
        # Still reports "Deleted" (idempotent-delete philosophy preserved for a genuinely-absent
        # target) - the regression this guards against is a pod that DOES exist being silently
        # skipped, not this deliberately-not-found case.
        self.assertEqual(result['status'], 'Deleted')

    def test_missing_namespace_short_circuits_without_listing_pods(self) -> None:
        mock_pod_list = MagicMock()
        with patch('src.containers.containers.NamespaceManager.get', return_value={}), \
             patch('src.containers.containers.PodManager.list', mock_pod_list):
            result = KubernetesContainerManager.delete(
                DeleteContainerDataClass(network_name=self.namespace_name, container_id=self.db_id)
            )
        mock_pod_list.assert_not_called()
        self.assertIn('does not exist', result['status'])
