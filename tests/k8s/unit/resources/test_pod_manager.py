# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# kubernetes
from kubernetes.client.rest import ApiException

# modules
from src.resources.pod_manager import PodManager


class TestPodManagerListPods(TestCase):

    @patch('kubernetes.client.CoreV1Api')
    def test_list_pod_success(self, mock_api) -> None:
        '''
        Successfully list pods.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_list_pod_api_exception(self, mock_api) -> None:
        '''
        ApiException while listing pods.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_list_pod_unsupported_runtime(self, mock_api) -> None:
        '''
        Unsupported Runtime Environment while listing pods.
        '''
        pass


class TestPodManagerCreatePod(TestCase):

    @patch('kubernetes.client.CoreV1Api')
    def test_create_pod_success(self, mock_api) -> None:
        '''
        Successfully create pod.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_create_pod_already_exists(self, mock_api) -> None:
        '''
        Pod already exists.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_create_pod_unsupported_runtime(self, mock_api) -> None:
        '''
        Unsupported Runtime Environment while creating pod.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_create_pod_api_exception(self, mock_api) -> None:
        '''
        ApiException while creating pod.
        '''
        pass


class TestPodManagerDeletePod(TestCase):

    @patch('kubernetes.client.CoreV1Api')
    def test_delete_pod_success(self, mock_api) -> None:
        '''
        Successfully delete pod.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_delete_pod_not_found(self, mock_api) -> None:
        '''
        Pod not found.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_delete_pod_unsupported_runtime(self, mock_api) -> None:
        '''
        Unsupported Runtime Environment while deleting pod.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_delete_pod_api_exception(self, mock_api) -> None:
        '''
        ApiException while deleting pod.
        '''
        pass
