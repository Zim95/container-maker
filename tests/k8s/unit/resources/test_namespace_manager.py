# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# kubernetes
from kubernetes.client.rest import ApiException

# modules
from src.resources.namespace_manager import NamespaceManager



class TestNamespaceManagerListNamespaces(TestCase):

    @patch('kubernetes.client.CoreV1Api')
    def test_list_namespace_success(self, mock_api) -> None:
        '''
        Successfully list namespaces.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_list_namespace_api_exception(self, mock_api) -> None:
        '''
        ApiException while listing namespaces.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_list_namespace_unsupported_runtime(self, mock_api) -> None:
        '''
        Unsupported Runtime Environment while listing namespaces.
        '''
        pass


class TestNamespaceManagerCreateNamespace(TestCase):

    @patch('kubernetes.client.CoreV1Api')
    def test_create_namespace_success(self, mock_api) -> None:
        '''
        Successfully create namespace.
        '''
        pass


    @patch('kubernetes.client.CoreV1Api')
    def test_create_namespace_already_exists(self, mock_api) -> None:
        '''
        Namespace already exists.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_create_namespace_unsupported_runtime(self, mock_api) -> None:
        '''
        Unsupported Runtime Environment while creating namespace.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_create_namespace_api_exception(self, mock_api) -> None:
        '''
        ApiException while creating namespace.
        '''
        pass


class TestNamespaceManagerDeleteNamespace(TestCase):

    @patch('kubernetes.client.CoreV1Api')
    def test_delete_namespace_success(self, mock_api) -> None:
        '''
        Successfully delete namespace.
        '''
        pass


    @patch('kubernetes.client.CoreV1Api')
    def test_delete_namespace_not_found(self, mock_api) -> None:
        '''
        Namespace not found.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_delete_namespace_unsupported_runtime(self, mock_api) -> None:
        '''
        Unsupported Runtime Environment while deleting namespace.
        '''
        pass

    @patch('kubernetes.client.CoreV1Api')
    def test_delete_namespace_api_exception(self, mock_api) -> None:
        '''
        ApiException while deleting namespace.
        '''
        pass
