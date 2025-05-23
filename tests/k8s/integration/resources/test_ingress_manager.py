# builtins
from unittest import TestCase
import time

# modules
from src.resources.dataclasses.ingress.create_ingress_dataclass import CreateIngressDataClass
from src.resources.dataclasses.ingress.delete_ingress_dataclass import DeleteIngressDataClass
from src.resources.dataclasses.ingress.list_ingress_dataclass import ListIngressDataClass
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.dataclasses.service.create_service_dataclass import CreateServiceDataClass, PublishInformationDataClass
from src.resources.dataclasses.service.delete_service_dataclass import DeleteServiceDataClass
from src.resources.ingress_manager import IngressManager
from src.resources.namespace_manager import NamespaceManager
from src.resources.pod_manager import PodManager
from src.resources.service_manager import ServiceManager

'''
NOTE:
Since ingress ip would be an ip outside the cluster, we cannot test ssh or connect-websocket into the ingress from within the cluster.
This test has to be done from outside the cluster.
'''


POD_NAME: str = 'test-ssh-pod'
NAMESPACE_NAME: str = 'test-ingress-manager'
SERVICE_NAME: str = 'test-ssh-service'


class TestIngressManager(TestCase):
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
            publish_information=[
                PublishInformationDataClass(
                    publish_port=self.service_port,
                    target_port=list(self.target_ports)[0],
                    protocol=self.protocol
                )
            ]
        )
        NamespaceManager.create(CreateNamespaceDataClass(**{'namespace_name': self.namespace_name}))
        PodManager.create(self.create_pod_data)
        ServiceManager.create(self.create_service_data)
        self.ingress_name: str = 'test-ingress'
        self.host: str = 'localhost'
        self.path: str = '/'
        self.ingress_data: CreateIngressDataClass = CreateIngressDataClass(
            namespace_name=self.namespace_name,
            ingress_name=self.ingress_name,
            service_name=self.service_name,
            host=self.host,
            service_ports=[
                {'container_port': self.service_port, 'protocol': self.protocol}
            ]
        )

    def test_a_ingress_creation_and_removal(self) -> None:
        '''
        Test the creation of ingress on a pod.
        '''
        print('Test: test_ingress_creation_and_removal')
        # list all ingress
        ingress_list_old: list = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))
        self.assertEqual(len(ingress_list_old), 0)

        # create ingress and wait for IP
        ingress: dict = IngressManager.create(self.ingress_data)
        
        self.assertEqual(ingress['ingress_name'], self.ingress_name)
        self.assertEqual(ingress['ingress_namespace'], self.namespace_name)
        self.assertIsNotNone(ingress['ingress_ip'])
        self.assertEqual(len(ingress['ingress_ports']), 2)  # we will always have 2 ingress ports, http and https.
        self.assertEqual(len(ingress['associated_services']), 1)

        # list all ingress
        ingress_list_new: list = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))
        self.assertEqual(len(ingress_list_new), 1)

    def test_b_duplicate_ingress_creation_fails(self) -> None:
        '''
        Test the creation of a duplicate ingress.
        Result: Should return the existing ingress instead of creating a duplicate.
        '''
        print('Test: test_duplicate_ingress_creation_fails')
        # create first ingress and wait for IP
        first_ingress: dict = IngressManager.create(self.ingress_data)
        first_uid: str = first_ingress['ingress_id']
        self.assertIsNotNone(first_ingress['ingress_ip'])
        self.assertEqual(len(first_ingress['ingress_ports']), 2)  # we will always have 2 ingress ports, http and https.
        self.assertEqual(len(first_ingress['associated_services']), 1)
        # create second ingress
        second_ingress: dict = IngressManager.create(self.ingress_data)
        second_uid: str = second_ingress['ingress_id']
        self.assertIsNotNone(second_ingress['ingress_ip'])
        self.assertEqual(len(second_ingress['ingress_ports']), 2)  # we will always have 2 ingress ports, http and https.
        self.assertEqual(len(second_ingress['associated_services']), 1)
        # verify that the ingress are the same
        self.assertEqual(first_uid, second_uid)
        self.assertEqual(first_ingress['ingress_ip'], second_ingress['ingress_ip'])

        # verify that only one ingress exists
        self.assertEqual(len(IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))), 1)

    def tearDown(self) -> None:
        print('Teardown: cleaning up after test')
        try:
            IngressManager.delete(DeleteIngressDataClass(
                namespace_name=self.namespace_name, 
                ingress_name=self.ingress_name
            ))
            # Wait a few seconds for cleanup
            time.sleep(30)
        except Exception:
            pass  # Ignore errors during cleanup


class ZZZ_Cleanup(TestCase):

    def test_cleanup(self) -> None:
        '''
        Cleanup the test environment.
        '''
        print('Test: test_cleanup')
        PodManager.delete(DeletePodDataClass(namespace_name=NAMESPACE_NAME, pod_name=POD_NAME))
        ServiceManager.delete(DeleteServiceDataClass(namespace_name=NAMESPACE_NAME, service_name=SERVICE_NAME))
        NamespaceManager.delete(DeleteNamespaceDataClass(namespace_name=NAMESPACE_NAME))
