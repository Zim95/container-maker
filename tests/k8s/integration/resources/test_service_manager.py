# builtins
from unittest import TestCase
import time

# modules
from src.resources.dataclasses.service.get_service_dataclass import GetServiceDataClass
from src.resources.service_manager import ServiceManager
from src.resources.pod_manager import PodManager
from src.resources.namespace_manager import NamespaceManager
from src.resources.dataclasses.service.create_service_dataclass import CreateServiceDataClass
from src.resources.dataclasses.service.delete_service_dataclass import DeleteServiceDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.dataclasses.service.get_service_dataclass import GetServiceDataClass

# third party
import paramiko


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
        self.service_port: int = 2222
        self.protocol: str = 'TCP'
        self.create_service_data: CreateServiceDataClass = CreateServiceDataClass(
            service_name=self.service_name,
            pod_name=self.pod_name,
            namespace_name=self.namespace_name,
            service_port=self.service_port,
            target_port=list(self.target_ports)[0], # take any one of the target ports
            protocol=self.protocol
        )
        NamespaceManager.create(CreateNamespaceDataClass(**{'namespace_name': self.namespace_name}))
        PodManager.create(self.create_pod_data)

    def test_creation_and_removal_of_services(self) -> None:
        '''
        Test the creation and removal of services.
        '''
        print('Test: test_creation_and_removal_of_services')

        # create a service
        service: dict = ServiceManager.create(self.create_service_data)

        # verify service properties
        self.assertEqual(service['service_name'], self.service_name)
        self.assertEqual(service['service_namespace'], self.namespace_name)
        self.assertEqual(service['service_port'], self.service_port)
        self.assertEqual(service['service_target_port'], list(self.target_ports)[0])
        self.assertEqual(service['service_ip'] is not None, True)
        # delete the service
        ServiceManager.delete(DeleteServiceDataClass(**{'namespace_name': self.namespace_name, 'service_name': self.service_name}))

        # verify service deletion
        service_deleted: dict = ServiceManager.get(GetServiceDataClass(**{'namespace_name': self.namespace_name, 'service_name': self.service_name}))
        self.assertEqual(service_deleted, {})

    def test_duplicate_service_creation(self) -> None:
        '''
        Test the creation of a service with the same name as an existing service.
        Result: Should return the existing service instead of creating a duplicate.
        '''
        print('Test: test_duplicate_service_creation')

        # create first service
        first_service: dict = ServiceManager.create(self.create_service_data)
        first_uid: str = first_service['service_id']
        # verify service properties
        self.assertEqual(first_service['service_name'], self.service_name)
        self.assertEqual(first_service['service_namespace'], self.namespace_name)
        self.assertEqual(first_service['service_port'], self.service_port)
        self.assertEqual(first_service['service_target_port'], list(self.target_ports)[0])
        self.assertEqual(first_service['service_ip'] is not None, True)

        # create second service
        second_service: dict = ServiceManager.create(self.create_service_data)
        second_uid: str = second_service['service_id']
        # verify service properties
        self.assertEqual(second_service['service_name'], self.service_name)
        self.assertEqual(second_service['service_namespace'], self.namespace_name)
        self.assertEqual(second_service['service_port'], self.service_port)
        self.assertEqual(second_service['service_target_port'], list(self.target_ports)[0])
        self.assertEqual(second_service['service_ip'] is not None, True)

        # verify that the services are the same
        self.assertEqual(first_uid, second_uid)

        # verify that only one service exists
        self.assertEqual(len(ServiceManager.list(ListServiceDataClass(**{'namespace_name': self.namespace_name}))), 1)

        # cleanup
        ServiceManager.delete(DeleteServiceDataClass(**{'namespace_name': self.namespace_name, 'service_name': self.service_name}))

        # verify service deletion
        service_deleted: dict = ServiceManager.get(GetServiceDataClass(**{'namespace_name': self.namespace_name, 'service_name': self.service_name}))
        self.assertEqual(service_deleted, {})

    def test_ssh_into_service(self) -> None:
        '''
        Test if you can ssh into the service.
        '''
        print('Test: test_ssh_into_service')

        # create a service
        service: dict = ServiceManager.create(self.create_service_data)

        print('Waiting for service to be ready')
        time.sleep(10)
        print('Service is ready')
        ssh: paramiko.SSHClient = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh.connect(
                hostname=service['service_ip'],
                username='ubuntu',
                password=self.environment_variables['SSH_PASSWORD'],
                port=self.service_port
            )
            _, stdout, _ = ssh.exec_command('echo "SSH test successful"')
            output = stdout.read().decode().strip()
            self.assertEqual(output, "SSH test successful")
        finally:
            ssh.close()
            ServiceManager.delete(DeleteServiceDataClass(**{'namespace_name': self.namespace_name, 'service_name': self.service_name}))

    def test_websocket_into_service(self) -> None:
        '''
        Test if you can connect to the websocket of the service.
        '''
        print('Test: test_websocket_into_service')


class ZZZ_Cleanup(TestCase):

    def test_cleanup(self) -> None:
        '''
        Delete the namespace.
        '''
        print('Cleanup: test_cleanup')
        PodManager.delete(DeletePodDataClass(**{'namespace_name': NAMESPACE_NAME, 'pod_name': POD_NAME}))
        NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': NAMESPACE_NAME}))

