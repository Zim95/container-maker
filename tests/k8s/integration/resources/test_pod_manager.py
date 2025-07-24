'''
IMPORTANT NOTE for namespaces:
- When old namespace is not deleted, it will cause an exception when we try creating a new namespace with the same name.
- So we need to wait for the old namespace to be deleted before creating a new namespace with the same name.

# Issue 1: Namespace name conflict between test suites.
- If all test suits use the same namespace, we will need to wait for the termination of the old namespace from the previous test suite,
    until we can create a new namespace with the same name for another test suite.
- To avoid this, we create a new namespace for every test suite. For example, for test suite TestPodManager will have test-pod-manager as the namespace.

# Issue 2: Namespace name conflict between tests within the same test suite.
- setUp and tearDown run after each test.
- If we delete the namespace in tearDown, it will be triggered after each test.
- So, when setup tries to create a namespace for the new test, it will cause a conflict because the namespace is still getting deleted from the previous test.
- When this happens, it will cause an exception when we try creating a new namespace with the same name.
- If we create a namespace in setUp, it will cause a conflict with the other tests within the same test suite.
- To avoid this, we don't delete the namespace in tearDown.

# Issue 3: How to delete lingering namespaces?
- Since, we don't delete the namespace in tearDown, it will remain in the cluster after all tests are done.
- We need to delete these lingering namespaces after all tests are done.
- We can do this by using a separate test suite for deleting namespaces.

# Issue 4: How to make sure the cleanup suite runs last?
- We can use the prefix 'ZZZ_' to the test suite name to make sure it runs last.
- So our cleanup test suite name will be 'ZZZ_Cleanup'.
'''

# builtins
from unittest import TestCase
import time
import paramiko

# modules
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.namespace_manager import NamespaceManager
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.pod_manager import PodManager
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass
from src.common.config import REPO_NAME
from src.resources.resource_config import SNAPSHOT_SIDECAR_NAME, SNAPSHOT_SIDECAR_IMAGE_NAME

NAMESPACE_NAME: str = 'test-pod-manager'

class TestPodManager(TestCase):

    def setUp(self) -> None:
        '''
        Create a namespace.
        '''
        print('Setup: setUp')
        self.image_name: str = f'{REPO_NAME}/ssh_ubuntu:latest'
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

    def test_a_creation_and_removal_of_pods(self) -> None:
        '''
        Test the creation of pods and their removal.
        Runs: list, create and delete methods to test behavior.
        '''
        print('Test: test_creation_and_removal_of_pods')
        # list all pods -> should return empty.
        pods_old: list[dict] = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        assert pods_old == []

        # create a pod -> dummy pod.
        pod: dict = PodManager.create(self.create_pod_data)

        # verify pod properties
        self.assertEqual(pod['pod_name'], self.pod_name)
        self.assertEqual(pod['pod_namespace'], self.namespace_name)
        self.assertEqual(pod['pod_ip'] is not None, True)
        self.assertEqual(len(pod['pod_ports']), 2)  # since we have 2 target ports.
        self.assertEqual(pod['pod_labels'].get('app'), self.pod_name) # we have only one label, the app label which is the pod name
        self.assertEqual(len(pod['pod_containers']), 2)  # there should be 2 containers in the pod: main, sidecar.

        # pod container names
        pod_container_names: list[str] = [container['container_name'] for container in pod['pod_containers']]
        self.assertEqual(SNAPSHOT_SIDECAR_NAME in pod_container_names, True)
        self.assertEqual(self.pod_name in pod_container_names, True)

        # pod container images
        pod_container_images: list[str] = [container['container_image'] for container in pod['pod_containers']]
        self.assertEqual(SNAPSHOT_SIDECAR_IMAGE_NAME in pod_container_images, True)
        self.assertEqual(self.image_name in pod_container_images, True)

        # list all pods -> should have a list.
        pods_new: list[dict] = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        assert len(pods_new) == 1

        # delete the pod -> cleanup.
        PodManager.delete(DeletePodDataClass(**{'namespace_name': self.namespace_name, 'pod_name': self.pod_name}))
        pods_last: list[dict] = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        assert pods_last == []

    def test_b_duplicate_pod_creation(self) -> None:
        '''
        Test the creation of a pod with the same name as an existing pod.
        Result: Should return the existing pod instead of creating a duplicate.
        '''
        print('Test: test_duplicate_pod_creation')
        
        # Create first pod and get its UID
        first_pod = PodManager.create(self.create_pod_data)
        first_uid = first_pod['pod_id']
        self.assertEqual(first_pod['pod_ip'] is not None, True)
        self.assertEqual(len(first_pod['pod_ports']), 2)  # since we have 2 target ports.
        
        # Try to create "duplicate" pod
        second_pod = PodManager.create(self.create_pod_data)
        second_uid = second_pod['pod_id']
        self.assertEqual(second_pod['pod_ip'] is not None, True)
        self.assertEqual(len(second_pod['pod_ports']), 2)  # since we have 2 target ports.
        # Verify it's the same pod (ids should match)
        assert first_uid == second_uid
        
        # Verify only one pod exists
        pods: list[dict] = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        assert len(pods) == 1

        # Cleanup
        PodManager.delete(DeletePodDataClass(**{
            'namespace_name': self.namespace_name, 
            'pod_name': self.pod_name
        }))

    def test_c_ssh_into_pod(self) -> None:
        '''
        Test if you can ssh into the pod.
        Result: Should get the output "SSH test successful".
        '''
        print('Test: test_ssh_into_pod')

        # Create the pod first
        pod: dict = PodManager.create(self.create_pod_data)

        # Wait for pod to be ready (give it time to start SSH server)
        print('Waiting for pod to be ready')
        time.sleep(10)
        print('Pod is ready')

        # Setup SSH client
        ssh: paramiko.SSHClient = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Connect to the pod
            ssh.connect(
                hostname=pod['pod_ip'],
                username=self.environment_variables['SSH_USERNAME'],
                password=self.environment_variables['SSH_PASSWORD'],
                port=22
            )

            # Execute a simple command to test connection
            _, stdout, _ = ssh.exec_command('echo "SSH test successful"')
            output = stdout.read().decode().strip()

            # Verify the output
            self.assertEqual(output, "SSH test successful")
        finally:
            # Clean up SSH connection
            ssh.close()
            # Delete the pod
            PodManager.delete(DeletePodDataClass(**{
                'namespace_name': self.namespace_name,
                'pod_name': self.pod_name
            }))

    def test_d_pod_status_timeout(self) -> None:
        '''
        Test if the pod status timeout is working.
        '''
        print('Test: test_pod_status_timeout')
        try:
            self.create_pod_data.image_name = 'test-image'
            PodManager.create(self.create_pod_data)
        except TimeoutError as e:
            self.assertEqual(str(e), f"Timeout waiting for pod {self.pod_name} to reach status Running after {20.0} seconds")
            self.create_pod_data.image_name = f'{REPO_NAME}/ssh_ubuntu:latest'  # set it back to the normal image for the rest of the tests.
        # delete the existing pod. Otherwise the new pod will not be created. it will simply fetch the existing pod.
        # the existing pod will have the same image error and the rest of the tests will not work.
        PodManager.delete(DeletePodDataClass(**{
            'namespace_name': self.namespace_name,
            'pod_name': self.pod_name
        }))

    def test_e_save_pod(self) -> None:
        '''
        Test the save pod method.
        '''
        print('Test: test_save_pod')
        # create a pod
        pod: dict = PodManager.create(self.create_pod_data)



class ZZZ_Cleanup(TestCase):

    def test_cleanup(self) -> None:
        '''
        Delete the namespace.
        '''
        print('Cleanup: test_cleanup')
        NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': NAMESPACE_NAME}))
