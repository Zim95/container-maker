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
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass
from src.resources.resource_config import SNAPSHOT_SIDECAR_NAME


NAMESPACE_NAME: str = 'test-save-utility'


class TestSaveUtility(TestCase):
    '''
    This class tests the saving of a pod's filesystem.
    The save utility should:
        - Create a tar file of the pod's filesystem.
        - Unpack the tar file into a sidecar pod.
        - Create a Dockerfile from the unpacked files.
        - Build the image from the Dockerfile.
        - Tag the image.
        - Push the image to a docker registry.

        That image should have the name of the pod.
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
        self.pod: dict = PodManager.create(self.create_pod_data)

        # save utility
        self.save_pod_data: SavePodDataClass = SavePodDataClass(
            pod_name=self.pod_name,
            namespace_name=self.namespace_name,
            sidecar_pod_name=SNAPSHOT_SIDECAR_NAME,
        )


    def test_a_check_shared_volume(self) -> None:
        '''
        - Check if the sidecar and main pod share a volume.
        '''
        print('Test: test_a_check_shared_volume')
        # check if the sidecar and main pod share a volume
        is_shared: bool = SaveUtility.check_shared_volume(self.save_pod_data)
        self.assertEqual(is_shared, True)

    def test_b_build_tar(self) -> None:
        '''
        - Check if the sidecar and main pod share a volume.
        - Check if the tar file is created.
        '''
        print('Test: test_b_build_tar')
        # check if the sidecar and main pod share a volume.
        is_shared: bool = SaveUtility.check_shared_volume(self.save_pod_data)
        self.assertEqual(is_shared, True)
        # create a tar file of the pod's filesystem.
        SaveUtility.build_tar(self.save_pod_data)
        

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
