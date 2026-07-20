'''
This module tests the saving of a pod's filesystem.
'''
# builtins
from unittest import TestCase

# modules
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.dataclasses.pod.save_pod_dataclass import SavePodDataClass
from src.resources.namespace_manager import NamespaceManager
from src.resources.pod_manager import PodManager, SaveUtility
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass, ResourceRequirementsDataClass
from src.resources.resource_config import SNAPSHOT_FILE_NAME


NAMESPACE_NAME: str = 'test-save-utility'


class TestSaveUtility(TestCase):
    '''
    This class tests the saving of a pod's filesystem.
    The save utility should:
        - Create a tar file of the pod's filesystem.
        - Write the snapshot tar to the configured storage layer.
    '''

    def setUp(self) -> None:
        '''
        Here we need to create a namespace and a pod.
        The pod will be used to test the saving of a pod's filesystem.
        '''
        print('Test: setUp TestSaveUtility')
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
        self.pod_name: str = 'test-ssh-pod'
        self.namespace_name: str = NAMESPACE_NAME
        self.target_ports: set = {22, 23}
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
        self.resource_requirements: ResourceRequirementsDataClass = ResourceRequirementsDataClass(
            cpu_request='100m',
            cpu_limit='1',
            memory_request='256Mi',
            memory_limit='1Gi',
            ephemeral_request='512Mi',
            ephemeral_limit='1Gi',
            snapshot_size_limit='2Gi',
        )
        self.create_pod_data: CreatePodDataClass = CreatePodDataClass(
            image_name=self.image_name,
            pod_name=self.pod_name,
            namespace_name=self.namespace_name,
            target_ports=self.target_ports,
            environment_variables=self.environment_variables,
            resource_requirements=self.resource_requirements,
        )
        NamespaceManager.create(CreateNamespaceDataClass(**{'namespace_name': self.namespace_name}))
        self.pod: dict = PodManager.create(self.create_pod_data)

        # save utility
        self.save_pod_data: SavePodDataClass = SavePodDataClass(
            pod_name=self.pod_name,
            namespace_name=self.namespace_name,
            environment_variables={},
        )

    def test_save_utility(self) -> None:
        '''
        - Check that the tar creation returns a snapshot path/key.
        '''
        print('Test: test_save_utility')
        snapshot_path = SaveUtility.build_tar(self.save_pod_data)
        self.assertEqual(self.namespace_name in snapshot_path, True)
        self.assertEqual(self.pod_name in snapshot_path, True)
        self.assertEqual(snapshot_path.endswith(f"{SNAPSHOT_FILE_NAME}.tar.gz"), True)
        print('Tar file created and stored via storage layer.')

    def tearDown(self) -> None:
        '''
        Delete the pod.
        '''
        print('Test: tearDown TestSaveUtility')
        PodManager.delete(DeletePodDataClass(**{
            'namespace_name': self.namespace_name,
            'pod_name': self.pod_name
        }))


class ZZZ_Cleanup(TestCase):
    '''
    Cleanup the namespace.
    '''
    def test_cleanup(self) -> None:
        '''
        Cleanup the namespace.
        '''
        print('Test: test_cleanup')
        NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': NAMESPACE_NAME}))
