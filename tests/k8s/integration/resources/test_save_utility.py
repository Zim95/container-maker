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
from src.resources.pod_manager import PodManager, SaveUtility, ExecUtility
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass
from src.resources.resource_config import SNAPSHOT_SIDECAR_NAME, SNAPSHOT_DIR, SNAPSHOT_FILE_NAME
from src.common.config import REPO_NAME, REPO_PASSWORD


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

    def test_save_utility(self) -> None:
        '''
        - Check if the sidecar and main pod share a volume.
        - Check if the tar file is created in the volume.
        '''
        print('Test: test_save_utility')
        # check if the sidecar and main pod share a volume
        is_shared: bool = SaveUtility.check_shared_volume(self.save_pod_data)
        self.assertEqual(is_shared, True)
        print('Sidecar and main pod share a volume.')

        # create a tar file of the pod's filesystem.
        SaveUtility.build_tar(self.save_pod_data)
        # check tar file in the volume.
        check_tar_command: str = f"ls -l {SNAPSHOT_DIR}"
        tar_command_output: str = ExecUtility.run_command(self.pod_name, self.namespace_name, SNAPSHOT_SIDECAR_NAME, check_tar_command)
        self.assertEqual(SNAPSHOT_FILE_NAME in tar_command_output, True)
        print('Tar file created in the volume.')

        # unpack the tar file into a sidecar pod.
        SaveUtility.unpack_tar(self.save_pod_data)
        # check tar
        check_directory_command: str = f"ls -l {SNAPSHOT_DIR}/rootfs"
        check_directory_output: str = ExecUtility.run_command(self.pod_name, self.namespace_name, SNAPSHOT_SIDECAR_NAME, check_directory_command)
        self.assertEqual(int(check_directory_output.split("\n")[0].split(" ")[-1]) > 0, True)
        print('Tar file unpacked into a sidecar pod.')

        # create a test file. This test file should be present in the pod that is created using this image.
        test_file_command: str = f"echo 'test' > {SNAPSHOT_DIR}/rootfs/test.txt"
        ExecUtility.run_command(self.pod_name, self.namespace_name, SNAPSHOT_SIDECAR_NAME, test_file_command)
        # check if the test file is present in the pod.
        check_test_file_command: str = f"ls -l {SNAPSHOT_DIR}/rootfs/test.txt"
        check_test_file_output: str = ExecUtility.run_command(self.pod_name, self.namespace_name, SNAPSHOT_SIDECAR_NAME, check_test_file_command)
        self.assertEqual('test.txt' in check_test_file_output, True)
        print('Test file created in the sidecar pod.')

        # create a Dockerfile from the unpacked files.
        SaveUtility.create_dockerfile(self.save_pod_data)
        # check if the Dockerfile is created in the volume.
        check_dockerfile_command: str = f"ls -l {SNAPSHOT_DIR}/rootfs/Dockerfile"
        check_dockerfile_output: str = ExecUtility.run_command(self.pod_name, self.namespace_name, SNAPSHOT_SIDECAR_NAME, check_dockerfile_command)
        self.assertEqual('Dockerfile' in check_dockerfile_output, True)
        print('Dockerfile created in the volume.')

        # build the image from the Dockerfile.
        image_data: dict = SaveUtility.build_image(self.save_pod_data)
        # check if the image is built.
        check_image_command: str = f"docker images"
        check_image_output: str = ExecUtility.run_command(self.pod_name, self.namespace_name, SNAPSHOT_SIDECAR_NAME, check_image_command)
        self.assertEqual(f'{self.pod_name}-image' in check_image_output, True)
        self.assertEqual(image_data['image_name'], f'{self.pod_name}-image:latest')
        self.assertEqual('Successfully built' in image_data['build_output'], True)
        print('Image built from the Dockerfile.')

        # tag the image.
        SaveUtility.tag_image(self.save_pod_data, image_data['image_name'], REPO_NAME)
        # check if the image is tagged.
        check_tagged_image_command: str = f"docker images"
        check_tagged_image_output: str = ExecUtility.run_command(self.pod_name, self.namespace_name, SNAPSHOT_SIDECAR_NAME, check_tagged_image_command)
        self.assertEqual(f'{REPO_NAME}/{image_data["image_name"].split(":")[0]}' in check_tagged_image_output, True)
        print('Image tagged.')

        # test docker login
        is_logged_in: bool = SaveUtility.docker_login(self.save_pod_data, REPO_NAME, REPO_PASSWORD)
        self.assertEqual(is_logged_in, True)
        print('Docker registry logged in.')

        # test docker push
        is_pushed: bool = SaveUtility.docker_push(self.save_pod_data, image_data['image_name'], REPO_NAME)
        self.assertEqual(is_pushed, True)
        print('Image pushed to docker registry.')

        # create new pod from the new image.
        new_pod_data: CreatePodDataClass = CreatePodDataClass(
            image_name=f'{REPO_NAME}/{image_data["image_name"].split(":")[0]}',
            pod_name='new-test-pod',
            namespace_name=self.namespace_name,
            target_ports=self.target_ports,
            environment_variables=self.environment_variables,
        )
        new_pod: dict = PodManager.create(new_pod_data)
        # check if test file exists in the Pod
        check_test_file_new_pod_command: str = f"ls -l /test.txt"
        check_test_file_output_new_pod: str = ExecUtility.run_command(new_pod['pod_name'], self.namespace_name, new_pod["pod_name"], check_test_file_new_pod_command)
        self.assertEqual('test.txt' in check_test_file_output_new_pod, True)
        print('Test file created in the new pod.')
        # delete the new pod
        print('Deleting the new pod.')
        PodManager.delete(DeletePodDataClass(**{
            'namespace_name': self.namespace_name,
            'pod_name': new_pod['pod_name']
        }))

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
