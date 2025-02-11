# builtins
from unittest import TestCase

# modules
from src.containers.containers import KubernetesContainerManager
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass, ExposureLevel
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass
from src.resources.dataclasses.ingress.list_ingress_dataclass import ListIngressDataClass
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.service.create_service_dataclass import PublishInformationDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources.ingress_manager import IngressManager
from src.resources.namespace_manager import NamespaceManager
from src.resources.pod_manager import PodManager
from src.resources.service_manager import ServiceManager


NAMESPACE_NAME: str = 'test-container-manager'


class TestCreateContainer(TestCase):
    def setUp(self) -> None:
        '''
        Setup the container data.
        Note:
        1. We need the tests to be in order because we set the container_id accordingly.
        2. There is a chance of the internal container test running last.
        3. All other tests will atleast create a service. If the ingress test runs second last,
            it will create ingress, service and pod and set the container id.
        4. In the teardown, it deletes only the ingress, and when it tries to delete lingering services,
            the service will not be deleted because it is attached to a pod and therefore not lingering by nature.
        5. So when the internal container test runs last, it will fail because it expects len(services) == 0 but the
            service from previous test exists, so it will fail.
        6. Therefore we need to maintain the order of creation.
        7. The order is: internal -> cluster_local -> cluster_external -> exposed.
        '''
        print('Test: setUp TestCreateContainer')
        self.container_name: str = 'test-container'
        self.namespace_name: str = NAMESPACE_NAME
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
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
            network_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=self.exposure_level,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
        )

    def test_a_creation_of_container_internal(self) -> None:
        '''
        Test the creation of a container with an internal exposure level.
        Result: Only the pod is created.
        '''
        print('Test: test_creation_of_container_internal')
        self.container_data.exposure_level = ExposureLevel.INTERNAL
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']
        # list pods, services and ingresses.
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        ingresses: list[dict] = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))

        # assert the length of the lists.
        self.assertEqual(len(pods), 1)  # only the pod is created.
        self.assertEqual(len(services), 0)
        self.assertEqual(len(ingresses), 0)

        # validate container properties
        self.assertEqual(len(container['container_id']), 36)
        self.assertEqual(container['container_name'], f'{self.container_name}-pod')
        self.assertIsNotNone(container['container_ip'])
        self.assertEqual(container['container_network'], self.namespace_name)
        self.assertEqual(len(container['container_ports']), 1)
        self.assertEqual(container['container_ports'][0]['container_port'], 22)

    def test_b_creation_of_container_cluster_local(self) -> None:
        '''
        Test the creation of a container with an cluster local exposure level.
        Result: Service is created with a cluster local ip.
        '''
        print('Test: test_creation_of_container_cluster_local')
        self.container_data.exposure_level = ExposureLevel.CLUSTER_LOCAL
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']
        # list pods, services and ingresses.
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        ingresses: list[dict] = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))

        # assert the length of the lists.
        self.assertEqual(len(pods), 1)  # pod is created.
        self.assertEqual(len(services), 1)  # service of type cluster ip is created
        self.assertEqual(len(ingresses), 0)

        # validate container properties
        self.assertEqual(len(container['container_id']), 36)
        self.assertEqual(container['container_name'], f'{self.container_name}-service')
        self.assertIsNotNone(container['container_ip'])
        self.assertEqual(container['container_network'], self.namespace_name)
        self.assertEqual(len(container['container_ports']), 1)
        self.assertEqual(container['container_ports'][0]['container_port'], 2222)

    def test_c_creation_of_container_cluster_external(self) -> None:
        '''
        Test the creation of a container with an cluster external exposure level.
        Result: Service is created with a cluster external ip.
        '''
        print('Test: test_creation_of_container_cluster_external')
        self.container_data.exposure_level = ExposureLevel.CLUSTER_EXTERNAL
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']
        # list pods, services and ingresses.
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        ingresses: list[dict] = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))

        # assert the length of the lists.
        self.assertEqual(len(pods), 1)  # pod is created.
        self.assertEqual(len(services), 1)  # service of type load balancer is created
        self.assertEqual(len(ingresses), 0)

        # validate container properties
        self.assertEqual(len(container['container_id']), 36)
        self.assertEqual(container['container_name'], f'{self.container_name}-service')
        self.assertIsNotNone(container['container_ip'])
        self.assertEqual(container['container_network'], self.namespace_name)
        self.assertEqual(len(container['container_ports']), 1)
        self.assertEqual(container['container_ports'][0]['container_port'], 2222)

    def test_d_creation_of_container_exposed(self) -> None:
        '''
        Test the creation of a container with an exposed exposure level.
        Result: Ingress is created with a cluster external ip.
        '''
        print('Test: test_creation_of_container_exposed')
        self.container_data.exposure_level = ExposureLevel.EXPOSED
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']
        # list pods, services and ingresses.
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        ingresses: list[dict] = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))

        # assert the length of the lists.
        self.assertEqual(len(pods), 1)  # pod is created.
        self.assertEqual(len(services), 1)  # service of type load balancer is created
        self.assertEqual(len(ingresses), 1)  # ingress is created

        # validate container properties
        self.assertEqual(len(container['container_id']), 36)
        self.assertEqual(container['container_name'], f'{self.container_name}-ingress')
        self.assertIsNotNone(container['container_ip'])
        self.assertEqual(container['container_network'], self.namespace_name)
        self.assertEqual(len(container['container_ports']), 2)

    def tearDown(self) -> None:
        '''
        Remove the container after every test.
        This deletes lingering namespaces as well. So no need for cleanup.
        '''
        if self.container_id:
            KubernetesContainerManager.delete(DeleteContainerDataClass(
                container_id=self.container_id,
                network_name=self.namespace_name,
            ))
