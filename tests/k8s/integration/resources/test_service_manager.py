# builtins
from unittest import TestCase

# modules
from src.resources.service_manager import ServiceManager
from src.resources.pod_manager import PodManager
from src.resources.namespace_manager import NamespaceManager
from src.resources.dataclasses.service.create_service_dataclass import CreateServiceDataClass
from src.resources.dataclasses.service.delete_service_dataclass import DeleteServiceDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass

NAMESPACE_NAME: str = 'test-service-manager'
POD_NAME: str = 'test-ssh-pod'

class TestServiceManager(TestCase):
    def setUp(self) -> None:
        print('Setup: setUp')
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
        self.pod_name: str = POD_NAME
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
        self.service_name: str = 'test-ssh-service'
        self.service_port: int = 22
        self.protocol: str = 'TCP'
        self.create_service_data: CreateServiceDataClass = CreateServiceDataClass(
            service_name=self.service_name,
            namespace_name=self.namespace_name,
            service_port=self.service_port,
            target_port=self.target_ports[0], # take any one of the target ports
            protocol=self.protocol,
        )
        NamespaceManager.create(CreateNamespaceDataClass(**{'namespace_name': self.namespace_name}))
        PodManager.create(self.create_pod_data)

    def test_creation_and_removal_of_services(self) -> None:
        '''
        Test the creation and removal of services.
        '''
        print('Test: test_creation_and_removal_of_services')
        pass

    def test_duplicate_service_creation(self) -> None:
        '''
        Test the creation of a service with the same name as an existing service.
        Result: Should return the existing service instead of creating a duplicate.
        '''
        print('Test: test_duplicate_service_creation')
        pass

    def test_ssh_into_service(self) -> None:
        '''
        Test if you can ssh into the service.
        '''
        print('Test: test_ssh_into_service')
        pass


class ZZZ_Cleanup(TestCase):

    def test_cleanup(self) -> None:
        '''
        Delete the namespace.
        '''
        print('Cleanup: test_cleanup')
        NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': NAMESPACE_NAME}))
        PodManager.delete(DeletePodDataClass(**{'namespace_name': NAMESPACE_NAME, 'pod_name': POD_NAME}))