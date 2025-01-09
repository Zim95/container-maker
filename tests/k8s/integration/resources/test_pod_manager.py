'''
IMPORTANT NOTE for namespaces:
- When old namespace is not deleted, it will cause an exception when we try creating a new namespace with the same name.
- So we need to wait for the old namespace to be deleted before creating a new namespace with the same name.

# Issue 1: Namespace name conflict between test suites.
- If all test suits use the same namespace, we will need to wait for the termination of the old namespace from the previous test suite,
    until we can create a new namespace with the same name for another test suite.
- To avoid this, we create a new namespace for every test suite. For example, for test suite TestPodManager will have test-pod-manager as the namespace.

# Issue 2: Namespace name conflict between tests within the same test suite.
- setUp and tearDown run after each test.
- If we delete the namespace in tearDown, it will be triggered after each test.
- So, when setup tries to create a namespace for the new test, it will cause a conflict because the namespace is still getting deleted from the previous test.
- When this happens, it will cause an exception when we try creating a new namespace with the same name.
- If we create a namespace in setUp, it will cause a conflict with the other tests within the same test suite.
- To avoid this, we don't delete the namespace in tearDown.

# Issue 3: How to delete lingering namespaces?
- Since, we don't delete the namespace in tearDown, it will remain in the cluster after all tests are done.
- We need to delete these lingering namespaces after all tests are done.
- We can do this by using a separate test suite for deleting namespaces.

# Issue 4: How to make sure the cleanup suite runs last?
- We can use the prefix 'ZZZ_' to the test suite name to make sure it runs last.
- So our cleanup test suite name will be 'ZZZ_Cleanup'.
'''

# builtins
from unittest import TestCase

# modules
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.namespace_manager import NamespaceManager
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.pod_manager import PodManager
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass

NAMESPACE_NAME: str = 'test-pod-manager'

class TestPodManager(TestCase):

    def setUp(self) -> None:
        '''
        Create a namespace.
        '''
        print('Setup: setUp')
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
        self.pod_name: str = 'test-ssh-pod'
        self.namespace_name: str = NAMESPACE_NAME
        self.target_ports: set = {22, 23}
        self.environment_variables: dict = {
            "SSH_PASSWORD": "testpwd"
        }
        self.create_pod_data: CreatePodDataClass = CreatePodDataClass(
            image_name=self.image_name,
            pod_name=self.pod_name,
            namespace_name=self.namespace_name,
            target_ports=self.target_ports,
            environment_variables=self.environment_variables,
        )
        NamespaceManager.create(CreateNamespaceDataClass(**{'namespace_name': self.namespace_name}))

    def test_creation_and_removal_of_pods(self) -> None:
        '''
        Test the creation of pods and their removal.
        Runs: list, create and delete methods to test behavior.
        '''
        print('Test: test_creation_and_removal_of_pods')
        # list all pods -> should return empty.
        pods_old: list[dict] = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        assert pods_old == []

        # create a pod -> dummy pod.
        pod: dict = PodManager.create(self.create_pod_data)

        # verify pod properties
        self.assertEqual(pod['pod_name'], self.pod_name)
        self.assertEqual(pod['pod_namespace'], self.namespace_name)

        # list all pods -> should have a list.
        pods_new: list[dict] = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        assert len(pods_new) == 1

        # delete the pod -> cleanup.
        PodManager.delete(DeletePodDataClass(**{'namespace_name': self.namespace_name, 'pod_name': self.pod_name}))
        pods_last: list[dict] = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        assert pods_last == []

    def test_duplicate_pod_creation(self) -> None:
        '''
        Test the creation of a pod with the same name as an existing pod.
        Result: There should be only one pod.
        '''
        print('Test: test_duplicate_pod_creation')
        PodManager.create(self.create_pod_data)
        PodManager.create(self.create_pod_data)

        # There should be only one pod.
        pods: list[dict] = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        assert len(pods) == 1

        # Cleanup
        PodManager.delete(DeletePodDataClass(**{
            'namespace_name': self.namespace_name, 
            'pod_name': self.pod_name
        }))


class ZZZ_Cleanup(TestCase):

    def test_cleanup(self) -> None:
        '''
        Delete the namespace.
        '''
        print('Cleanup: test_cleanup')
        NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': NAMESPACE_NAME}))
