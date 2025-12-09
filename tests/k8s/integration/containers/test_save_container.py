# builtins
from unittest import TestCase

# modules
from src.containers.containers import KubernetesContainerManager
from src.containers.dataclasses.create_container_dataclass import (
    CreateContainerDataClass,
    ExposureLevel,
    ResourceRequirementsDataClass,
)
from src.containers.dataclasses.save_container_dataclass import SaveContainerDataClass
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass
from src.resources.dataclasses.service.create_service_dataclass import PublishInformationDataClass


NAMESPACE_NAME: str = 'test-save-container-namespace'


class TestSaveContainer(TestCase):
    def setUp(self) -> None:
        '''
        Setup the container data.
        Here we will test saving a container of all exposure levels.
        Here are the tests:
        1. Internal - Pod Level
        2. Cluster Local - Internal Service Level
        3. Cluster External - Cluster External Service Level
        4. Exposed - Ingress Level
        5. Non-existent containers - Throws an exception.
        '''
        print('Test: setUp TestSaveContainer')
        self.container_name: str = 'test-container'
        self.namespace_name: str = NAMESPACE_NAME
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
        self.exposure_level: ExposureLevel = ExposureLevel.INTERNAL
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
        self.container_data: CreateContainerDataClass = CreateContainerDataClass(
            container_name=self.container_name,
            network_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=self.exposure_level,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
            resource_requirements=self.resource_requirements,
        )

    def test_a_save_container_internal(self) -> None:
        '''
        Test saving a container of internal exposure level.
        '''
        print('Test: test_a_save_container_internal')
        # create a container
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']
        # save the container
        saved_container: list[dict] = KubernetesContainerManager.save(SaveContainerDataClass(
            container_id=self.container_id,
            network_name=self.container_data.network_name,
        ))
        # verify the saved container
        self.assertEqual(len(saved_container), 1)
        self.assertEqual(saved_container[0]['pod_name'], f'{self.container_data.container_name}-pod')
        self.assertEqual(saved_container[0]['namespace_name'], self.container_data.network_name)
        self.assertEqual(saved_container[0]['image_name'], f'{self.container_data.container_name}-pod-image:latest')

    def test_b_save_container_cluster_local(self) -> None:
        '''
        Test saving a container of cluster local exposure level.
        '''
        print('Test: test_b_save_container_cluster_local')
        # create a container
        self.container_data.exposure_level = ExposureLevel.CLUSTER_LOCAL
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']
        # save the container
        saved_container: list[dict] = KubernetesContainerManager.save(SaveContainerDataClass(
            container_id=self.container_id,
            network_name=self.container_data.network_name,
        ))
        # verify the saved container
        self.assertEqual(len(saved_container), 1)
        self.assertEqual(saved_container[0]['pod_name'], f'{self.container_data.container_name}-pod')
        self.assertEqual(saved_container[0]['namespace_name'], self.container_data.network_name)
        self.assertEqual(saved_container[0]['image_name'], f'{self.container_data.container_name}-pod-image:latest')

    def test_c_save_container_cluster_external(self) -> None:
        '''
        Test saving a container of cluster external exposure level.
        '''
        print('Test: test_c_save_container_cluster_external')
        # create a container
        self.container_data.exposure_level = ExposureLevel.CLUSTER_EXTERNAL
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']
        # save the container
        saved_container: list[dict] = KubernetesContainerManager.save(SaveContainerDataClass(
            container_id=self.container_id,
            network_name=self.container_data.network_name,
        ))
        # verify the saved container
        self.assertEqual(len(saved_container), 1)
        self.assertEqual(saved_container[0]['pod_name'], f'{self.container_data.container_name}-pod')
        self.assertEqual(saved_container[0]['namespace_name'], self.container_data.network_name)
        self.assertEqual(saved_container[0]['image_name'], f'{self.container_data.container_name}-pod-image:latest')

    def test_d_save_container_exposed(self) -> None:
        '''
        Test saving a container of exposed exposure level.
        '''
        print('Test: test_d_save_container_exposed')
        # create a container
        self.container_data.exposure_level = ExposureLevel.EXPOSED
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']
        # save the container
        saved_container: list[dict] = KubernetesContainerManager.save(SaveContainerDataClass(
            container_id=self.container_id,
            network_name=self.container_data.network_name,
        ))
        # verify the saved container
        self.assertEqual(len(saved_container), 1)
        self.assertEqual(saved_container[0]['pod_name'], f'{self.container_data.container_name}-pod')
        self.assertEqual(saved_container[0]['namespace_name'], self.container_data.network_name)
        self.assertEqual(saved_container[0]['image_name'], f'{self.container_data.container_name}-pod-image:latest')

    def test_e_save_container_non_existent(self) -> None:
        '''
        Test saving a non-existent container.
        '''
        print('Test: test_e_save_container_non_existent')
        # save the container
        self.container_id: str = 'non-existent-container-id'
        try:
            KubernetesContainerManager.save(SaveContainerDataClass(
                container_id=self.container_id,
                network_name=self.container_data.network_name,
            ))
        except Exception as e:
            self.assertEqual(str(e), f'Cannot find, container_id=non-existent-container-id in namespace={self.container_data.network_name}')

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
