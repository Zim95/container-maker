# builtins
from unittest import TestCase


# local
from src.containers.containers import KubernetesContainerManager
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass, ExposureLevel
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass
from src.resources.dataclasses.ingress.list_ingress_dataclass import ListIngressDataClass
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.service.create_service_dataclass import PublishInformationDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources.ingress_manager import IngressManager
from src.resources.pod_manager import PodManager
from src.resources.service_manager import ServiceManager


NAMESPACE_NAME: str = 'test-get-container'


class TestGetContainer(TestCase):

    def setUp(self) -> None:
        '''
        Setup the container data.
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

    def test_get_pod(self) -> None:
        '''
        Create the container with exposure level internal.
        Get the container.
        List the pods.
        List the services.
        List the ingresses.
        The container should be in the list of pods.
        '''
        print('Test: test_get_pod')
        self.container_data.exposure_level = ExposureLevel.INTERNAL
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']

        # list all resources
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        ingresses: list[dict] = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))

        # check if the container is in the list of pods
        self.assertIn(container['container_id'], [pod['pod_id'] for pod in pods])
        self.assertNotIn(container['container_id'], [service['service_id'] for service in services])
        self.assertNotIn(container['container_id'], [ingress['ingress_id'] for ingress in ingresses])

    def test_get_service(self) -> None:
        '''
        Create the container with exposure level cluster_local.
        Get the container.
        List the pods.
        List the services.
        List the ingresses.
        The container should be in the list of services.
        '''
        print('Test: test_get_service')
        self.container_data.exposure_level = ExposureLevel.CLUSTER_LOCAL
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']

        # list all resources
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        ingresses: list[dict] = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))

        # check if the container is in the list of pods
        self.assertNotIn(container['container_id'], [pod['pod_id'] for pod in pods])
        self.assertIn(container['container_id'], [service['service_id'] for service in services])
        self.assertNotIn(container['container_id'], [ingress['ingress_id'] for ingress in ingresses])

    def test_get_ingress(self) -> None:
        '''
        Create the container with exposure level exposed.
        Get the container.
        List the pods.
        List the services.
        List the ingresses.
        The container should be in the list of ingresses.
        '''
        print('Test: test_get_ingress')
        self.container_data.exposure_level = ExposureLevel.EXPOSED
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']

        # list all resources
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        ingresses: list[dict] = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))

        # check if the container is in the list of pods
        self.assertNotIn(container['container_id'], [pod['pod_id'] for pod in pods])
        self.assertNotIn(container['container_id'], [service['service_id'] for service in services])
        self.assertIn(container['container_id'], [ingress['ingress_id'] for ingress in ingresses])

    def tearDown(self) -> None:
        '''
        Delete the container.
        '''
        if self.container_id:
            KubernetesContainerManager.delete(
                DeleteContainerDataClass(
                    container_id=self.container_id,
                    network_name=self.namespace_name,
                )
            )
