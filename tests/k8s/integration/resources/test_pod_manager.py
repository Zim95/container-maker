# builtins
from unittest import TestCase

# modules
from src.resources.namespace_manager import NamespaceManager
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.pod_manager import PodManager
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass


class TestPodManager(TestCase):

    def setUp(self) -> None:
        '''
        Create a namespace.
        '''
        self.image_name: str = ''
        self.pod_name: str = ''
        self.namespace_name: str = 'test-namespace'
        self.target_ports: set = {}
        self.environment_variables: dict = {}
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
        # list all pods -> should return empty.
        pods: list[dict] = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        assert pods == []

        # create a pod -> dummy pod.
        PodManager.create()
        # list all pods -> should have a list.
        # delete the pod -> cleanup.

    def test_duplicate_pod_creation(self) -> None:
        pass

    def tearDown(self) -> None:
        '''
        Delete the created namespace.
        '''
        NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': self.namespace_name}))
