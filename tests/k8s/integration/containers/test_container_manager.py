# builtins
from unittest import TestCase

# modules
from src.containers.containers import ContainerManager
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass, ExposureLevel
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.dataclasses.service.create_service_dataclass import PublishInformationDataClass
from src.resources.ingress_manager import IngressManager
from src.resources.namespace_manager import NamespaceManager
from src.resources.pod_manager import PodManager
from src.resources.service_manager import ServiceManager


NAMESPACE_NAME: str = 'test-container-manager'


class TestContainerManager(TestCase):
    def setUp(self) -> None:
        '''
        Setup the container data.
        '''
        self.container_name: str = 'test-container'
        self.namespace_name: str = 'test-container-namespace'
        self.image_name: str = 'test-image'
        self.exposure_level: ExposureLevel = ExposureLevel.INTERNAL
        self.publish_information: list[PublishInformationDataClass] = [
            PublishInformationDataClass(publish_port=2222, target_port=22, protocol='TCP'),
        ]
        self.environment_variables: dict[str, str] = {
            'SSH_PASSWORD': '12345678',
            'SSH_USERNAME': 'test-user',
        }
        self.container_data: CreateContainerDataClass = CreateContainerDataClass(
            container_name=self.container_name,
            namespace_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=self.exposure_level,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
        )
        NamespaceManager.create(CreateNamespaceDataClass(namespace_name=self.namespace_name))

    def test_creation_and_removal_of_container_internal(self) -> None:
        '''
        Test the creation and removal of a container with an internal exposure level.
        Result: Only the pod is created.
        '''
        container: dict = ContainerManager.create(self.container_data)

        # list pods, services and ingresses.
        pods: list[dict] = PodManager.list(self.namespace_name)
        services: list[dict] = ServiceManager.list(self.namespace_name)
        ingresses: list[dict] = IngressManager.list(self.namespace_name)

        # assert the length of the lists.
        self.assertEqual(len(pods), 1)  # only the pod is created.
        self.assertEqual(len(services), 0)
        self.assertEqual(len(ingresses), 0)

        # validate container properties
        self.assertEqual(len(container['container_id']), 12)
        self.assertEqual(container['container_name'], f'{self.namespace_name}-{self.container_name}-pod')
        self.assertIsNotNone(container['container_ip'])
        self.assertEqual(container['container_network'], self.namespace_name)
        self.assertEqual(len(container['container_ports']), 1)
        self.assertEqual(container['container_ports'][0]['container_port'], 22)

    def test_creation_and_removal_of_container_cluster_local(self) -> None:
        pass

    def test_creation_and_removal_of_container_cluster_external(self) -> None:
        pass

    def test_creation_and_removal_of_container_exposed(self) -> None:
        pass

    def tearDown(self) -> None:
        '''
        Remove the container.
        This is experimental
        '''
        ContainerManager.delete(DeleteContainerDataClass(
            container_name=self.container_name,
            namespace_name=self.namespace_name,
        ))


class ZZZ_Cleanup(TestCase):

    def test_cleanup(self) -> None:
        '''
        Cleanup the test environment.
        '''
        print('Test: test_cleanup')
        NamespaceManager.delete(DeleteNamespaceDataClass(namespace_name=NAMESPACE_NAME))
