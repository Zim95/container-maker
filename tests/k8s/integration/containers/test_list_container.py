# builtins
from unittest import TestCase

# modules
from src.containers.containers import KubernetesContainerManager
from src.containers.dataclasses.create_container_dataclass import (
    CreateContainerDataClass,
    ExposureLevel,
    ResourceRequirementsDataClass,
)
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass
from src.containers.dataclasses.list_container_dataclass import ListContainerDataClass
from src.resources.dataclasses.ingress.list_ingress_dataclass import ListIngressDataClass
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.service.create_service_dataclass import PublishInformationDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources.ingress_manager import IngressManager
from src.resources.pod_manager import PodManager
from src.resources.service_manager import ServiceManager


NAMESPACE_NAME: str = 'test-list-container'


class TestListContainer(TestCase):
    def setUp(self) -> None:
        '''
        Setup the container data.
        '''
        print('Test: setUp TestListContainer')
        self.container_name: str = 'test-container'
        self.namespace_name: str = NAMESPACE_NAME
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
        self.resource_requirements: ResourceRequirementsDataClass = ResourceRequirementsDataClass(
            cpu_request='100m',
            cpu_limit='1',
            memory_request='256Mi',
            memory_limit='1Gi',
            ephemeral_request='512Mi',
            ephemeral_limit='1Gi',
            snapshot_size_limit='2Gi',
        )
        self.publish_information: list[PublishInformationDataClass] = [
            PublishInformationDataClass(publish_port=2222, target_port=22, protocol='TCP'),
        ]
        self.environment_variables: dict = {
            "SSH_USERNAME": "ubuntu",
            "SSH_PASSWORD": "testpwd",
            "CONTAINER_ID": "1234567890",
            "DB_USERNAME": "testuser",
            "DB_PASSWORD": "testpassword",
            "DB_NAME": "testdb",
            "DB_HOST": "testhost",
            "DB_PORT": "5432",
            "DB_DATABASE": "testdatabase",
        }
        self.pod_container_data: CreateContainerDataClass = CreateContainerDataClass(
            container_name=f'{self.container_name}-internal',
            network_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=ExposureLevel.INTERNAL,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
            resource_requirements=self.resource_requirements,
        )
        self.service_container_data: CreateContainerDataClass = CreateContainerDataClass(
            container_name=f'{self.container_name}-cluster-local',
            network_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=ExposureLevel.CLUSTER_LOCAL,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
            resource_requirements=self.resource_requirements,
        )
        self.ingress_container_data: CreateContainerDataClass = CreateContainerDataClass(
            container_name=f'{self.container_name}-exposed',
            network_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=ExposureLevel.EXPOSED,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
            resource_requirements=self.resource_requirements,
        )

    def test_list_container(self) -> None:
        '''
        Create all the containers.
        List the resources.
        1. There should be 3 pods.
        2. There should be 2 services.
        3. There should be 1 ingress.
        4. List all containers. There should only be 3 containers.
        '''
        print('Test: test_list_container')
        pod_container: dict = KubernetesContainerManager.create(self.pod_container_data)
        service_container: dict = KubernetesContainerManager.create(self.service_container_data)
        ingress_container: dict = KubernetesContainerManager.create(self.ingress_container_data)
        self.pod_container_id: str = pod_container['container_id']
        self.service_container_id: str = service_container['container_id']
        self.ingress_container_id: str = ingress_container['container_id']

        # list all resources
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        ingresses: list[dict] = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))

        # assert the length of the lists
        self.assertEqual(len(pods), 3)
        self.assertEqual(len(services), 2)
        self.assertEqual(len(ingresses), 1)

        # list the containers
        containers: list[dict] = KubernetesContainerManager.list(ListContainerDataClass(network_name=self.namespace_name))
        self.assertEqual(len(containers), 3)

    def tearDown(self) -> None:
        '''
        Delete the containers.
        '''
        if self.pod_container_id:
            KubernetesContainerManager.delete(DeleteContainerDataClass(
                container_id=self.pod_container_id,
                network_name=self.namespace_name
            ))
        if self.service_container_id:
            KubernetesContainerManager.delete(DeleteContainerDataClass(
                container_id=self.service_container_id,
                network_name=self.namespace_name
            ))
        if self.ingress_container_id:
            KubernetesContainerManager.delete(DeleteContainerDataClass(
                container_id=self.ingress_container_id,
                network_name=self.namespace_name
            ))
