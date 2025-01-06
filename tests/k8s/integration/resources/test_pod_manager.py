# builtins
from unittest import TestCase

# modules
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
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
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
        self.pod_name: str = 'test-ssh-pod'
        self.namespace_name: str = 'test-namespace'
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
        # list all pods -> should return empty.
        pods: list[dict] = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        assert pods == []

        # create a pod -> dummy pod.
        pod: dict = PodManager.create(self.create_pod_data)
        breakpoint()
        # verify pod properties
        # self.assertEqual(pod['metadata']['name'], self.pod_name)
        # self.assertEqual(pod['metadata']['namespace'], self.namespace_name)
        # self.assertEqual(pod['spec']['containers'][0]['image'], self.image_name)

        # list all pods -> should have a list.
        pods: list[dict] = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        assert len(pods) == 1

        # delete the pod -> cleanup.
        PodManager.delete(DeletePodDataClass(**{'namespace_name': self.namespace_name, 'pod_name': self.pod_name}))
        pods: list[dict] = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        assert pods == []

    # def test_duplicate_pod_creation(self) -> None:
    #     '''
    #     Test the creation of a pod with the same name as an existing pod.
    #     '''
    #     # Create the first pod
    #     PodManager.create(self.create_pod_data)
        
    #     # Attempt to create a second pod with the same name
    #     with self.assertRaises(Exception) as context:
    #         PodManager.create(self.create_pod_data)
        
    #     # Verify error message (optional, depending on your error handling)
    #     self.assertIn('already exists', str(context.exception))

    #     # Cleanup
    #     PodManager.delete(DeletePodDataClass(**{
    #         'namespace_name': self.namespace_name, 
    #         'pod_name': self.pod_name
    #     }))

    def tearDown(self) -> None:
        '''
        Delete the created namespace.
        '''
        NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': self.namespace_name}))
